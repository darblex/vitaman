#!/usr/bin/env python3
"""Lightweight web server: landing page + health for Railway."""
from __future__ import annotations

import os
from pathlib import Path

from aiohttp import web

import config

BASE = Path(__file__).parent
INDEX_PATH = BASE / "index.html"


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
    return web.json_response({"ok": True, "service": "vitaman"})


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/index.html", handle_index)
    static_dir = BASE / "static"
    if static_dir.is_dir():
        app.router.add_static("/static/", static_dir, show_index=False)
    return app


def main() -> None:
    web.run_app(create_app(), host="0.0.0.0", port=config.PORT)


if __name__ == "__main__":
    main()
