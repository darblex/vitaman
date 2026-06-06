#!/usr/bin/env python3
"""Manual trigger for one auto-post and one report (for smoke tests)."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from telegram import Bot

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config
from automation import AutomationService, MarketingConfig, ReportConfig


async def main() -> None:
    bot = Bot(token=config.BOT_TOKEN)
    service = AutomationService(
        bot=bot,
        marketing=MarketingConfig(
            enabled=True,
            channel_id=config.AUTO_POST_CHANNEL_ID,
            times=["00:00"],
            timezone=config.AUTO_POST_TIMEZONE,
            bot_username=config.TELEGRAM_BOT_USERNAME,
            source_tag=config.AUTO_POST_SOURCE_TAG,
            posts_path=Path(config.AUTO_POSTS_FILE),
        ),
        report=ReportConfig(
            enabled=True,
            chat_id=config.AUTO_REPORT_CHAT_ID,
            time="00:00",
            timezone=config.AUTO_REPORT_TIMEZONE,
            orders_path=Path(config.DATA_DIR) / "orders.json",
        ),
    )
    await service._send_next_post("manual")
    await service._send_daily_report(service._tz(config.AUTO_REPORT_TIMEZONE))
    print("Sent one auto-post + one daily report")


if __name__ == "__main__":
    asyncio.run(main())

