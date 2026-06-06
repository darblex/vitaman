#!/usr/bin/env python3
"""Unified web server: landing page, health, Telegram webhook."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from aiohttp import web
from telegram import Update

import config
from automation import AutomationService, MarketingConfig, ReportConfig
from bot_new import build_application

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("vitaman.server")

BASE = Path(__file__).parent
INDEX_PATH = BASE / "index.html"

tg_application = None
automation_service: AutomationService | None = None
webhook_guard_task: asyncio.Task | None = None
webhook_expected_url = ""


def render_landing() -> str:
    html = INDEX_PATH.read_text(encoding="utf-8")
    bot = config.TELEGRAM_BOT_USERNAME.lstrip("@")
    replacements = {
        "{{SHOP_NAME}}": config.SHOP_NAME,
        "{{TELEGRAM_BOT}}": bot,
        "{{TELEGRAM_URL}}": f"https://t.me/{bot}",
        "{{FB_PIXEL_ID}}": config.FB_PIXEL_ID,
        "{{DISCOUNT_PCT}}": str(config.DISCOUNT_PCT),
        "{{DISCOUNT_THRESHOLD}}": str(config.DISCOUNT_THRESHOLD),
        "{{LANDING_URL}}": config.LANDING_PAGE_URL.rstrip("/"),
    }
    for key, value in replacements.items():
        html = html.replace(key, value)
    return html


async def handle_index(_request: web.Request) -> web.Response:
    return web.Response(text=render_landing(), content_type="text/html", charset="utf-8")


async def handle_health(_request: web.Request) -> web.Response:
    mode = "polling" if config.USE_POLLING else "webhook"
    return web.json_response({"ok": True, "service": "vitaman", "bot_mode": mode})


async def handle_webhook(request: web.Request) -> web.Response:
    if config.WEBHOOK_SECRET:
        secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if secret != config.WEBHOOK_SECRET:
            logger.warning("Webhook rejected: bad secret token")
            return web.Response(status=403, text="forbidden")

    try:
        payload = await request.json()
    except Exception:
        return web.Response(status=400, text="bad json")

    try:
        update = Update.de_json(payload, tg_application.bot)
    except Exception:
        logger.exception("Failed to parse incoming update")
        return web.Response(text="ok")
    try:
        await tg_application.process_update(update)
    except Exception:
        logger.exception("Failed to process update")
    return web.Response(text="ok")


async def ensure_webhook_registered() -> None:
    if config.USE_POLLING or not tg_application or not webhook_expected_url:
        return
    try:
        info = await tg_application.bot.get_webhook_info()
    except Exception:
        logger.exception("Could not read webhook info")
        return
    if info.url == webhook_expected_url:
        return
    logger.warning("Webhook drift detected (current=%s). Re-registering.", info.url or "<empty>")
    await tg_application.bot.set_webhook(
        url=webhook_expected_url,
        secret_token=config.WEBHOOK_SECRET or None,
        drop_pending_updates=False,
        allowed_updates=Update.ALL_TYPES,
    )
    logger.info("Webhook restored at %s", webhook_expected_url)


async def webhook_guard_loop() -> None:
    while True:
        try:
            await asyncio.sleep(20)
            await ensure_webhook_registered()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Webhook guard check failed")


async def on_startup(_app: web.Application) -> None:
    global tg_application
    global automation_service
    global webhook_guard_task
    global webhook_expected_url
    tg_application = build_application()
    await tg_application.initialize()
    await tg_application.start()

    automation_service = AutomationService(
        bot=tg_application.bot,
        marketing=MarketingConfig(
            enabled=config.AUTO_POST_ENABLED,
            channel_id=config.AUTO_POST_CHANNEL_ID,
            times=config.AUTO_POST_TIMES,
            timezone=config.AUTO_POST_TIMEZONE,
            bot_username=config.TELEGRAM_BOT_USERNAME,
            source_tag=config.AUTO_POST_SOURCE_TAG,
            posts_path=Path(config.AUTO_POSTS_FILE),
        ),
        report=ReportConfig(
            enabled=config.AUTO_REPORT_ENABLED,
            chat_id=config.AUTO_REPORT_CHAT_ID,
            time=config.AUTO_REPORT_TIME,
            timezone=config.AUTO_REPORT_TIMEZONE,
            orders_path=Path(config.DATA_DIR) / "orders.json",
        ),
    )
    await automation_service.start()

    if config.USE_POLLING:
        await tg_application.updater.start_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
        )
        logger.info("Bot started in polling mode (dev)")
        return

    webhook_url = f"{config.WEBHOOK_BASE.rstrip('/')}{config.WEBHOOK_PATH}"
    webhook_expected_url = webhook_url
    await tg_application.bot.set_webhook(
        url=webhook_url,
        secret_token=config.WEBHOOK_SECRET or None,
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
    )
    logger.info("Webhook registered at %s", webhook_url)
    webhook_guard_task = asyncio.create_task(webhook_guard_loop())



async def on_cleanup(_app: web.Application) -> None:
    global webhook_guard_task
    if webhook_guard_task:
        webhook_guard_task.cancel()
        try:
            await webhook_guard_task
        except (asyncio.CancelledError, Exception):
            pass
        webhook_guard_task = None
    if automation_service:
        await automation_service.stop()
    if not tg_application:
        return
    if config.USE_POLLING:
        await tg_application.updater.stop()
    # NOTE: intentionally NOT deleting the webhook here.
    # During redeploys the old container's cleanup would otherwise wipe the
    # webhook that the new container already registered, killing the bot.
    await tg_application.stop()
    await tg_application.shutdown()


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/index.html", handle_index)
    if not config.USE_POLLING:
        app.router.add_post(config.WEBHOOK_PATH, handle_webhook)
    static_dir = BASE / "static"
    if static_dir.is_dir():
        app.router.add_static("/static/", static_dir, show_index=False)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app


def main() -> None:
    web.run_app(create_app(), host="0.0.0.0", port=config.PORT)


if __name__ == "__main__":
    main()
