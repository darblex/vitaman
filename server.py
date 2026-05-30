#!/usr/bin/env python3
"""Unified web server: landing page, health, Telegram webhook."""
from __future__ import annotations

import logging
from pathlib import Path

from aiohttp import web
from telegram import Update

import config
from bot_new import build_application

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("vitaman.server")

BASE = Path(__file__).parent
INDEX_PATH = BASE / "index.html"

tg_application = None


def render_landing() -> str:
    html = INDEX_PATH.read_text(encoding="utf-8")
    bot = config.TELEGRAM_BOT_USERNAME.lstrip("@")
    replacements = {
        "{{SHOP_NAME}}": config.SHOP_NAME,
        "{{TELEGRAM_BOT}}": bot,
        "{{TELEGRAM_URL}}": f"https://t.me/{bot}",
        "{{WHATSAPP_NUMBER}}": config.WHATSAPP_NUMBER,
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
    data_dir = Path(config.DATA_DIR)
    return web.json_response(
        {
            "ok": True,
            "service": "vitaman",
            "shop": config.SHOP_NAME,
            "bot_mode": mode,
            "bot_username": config.TELEGRAM_BOT_USERNAME,
            "webhook_path": None if config.USE_POLLING else config.WEBHOOK_PATH,
            "data_dir_ready": data_dir.exists() and data_dir.is_dir(),
        }
    )


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

    update = Update.de_json(payload, tg_application.bot)
    await tg_application.process_update(update)
    return web.Response(text="ok")


async def on_startup(_app: web.Application) -> None:
    global tg_application
    tg_application = build_application()
    await tg_application.initialize()
    await tg_application.start()

    if config.USE_POLLING:
        await tg_application.updater.start_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
        )
        logger.info("Bot started in polling mode (dev)")
        return

    webhook_url = f"{config.WEBHOOK_BASE.rstrip('/')}{config.WEBHOOK_PATH}"
    await tg_application.bot.set_webhook(
        url=webhook_url,
        secret_token=config.WEBHOOK_SECRET or None,
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
    )
    logger.info("Webhook registered at %s", webhook_url)


async def on_cleanup(_app: web.Application) -> None:
    if not tg_application:
        return
    if config.USE_POLLING:
        await tg_application.updater.stop()
    else:
        await tg_application.bot.delete_webhook(drop_pending_updates=False)
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
