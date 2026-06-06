"""Telegram marketing automation: scheduled channel posts and daily reports."""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger("vitaman.automation")


def _parse_hhmm(value: str) -> tuple[int, int]:
    parts = value.strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid time format: {value!r}")
    hour = int(parts[0])
    minute = int(parts[1])
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError(f"Invalid time value: {value!r}")
    return hour, minute


def _next_run_delta(now: datetime, hhmm: str) -> float:
    hour, minute = _parse_hhmm(hhmm)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def _load_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed reading %s: %s", path, exc)
        return default


@dataclass
class MarketingConfig:
    enabled: bool
    channel_id: str
    times: List[str]
    timezone: str
    bot_username: str
    source_tag: str
    posts_path: Path


@dataclass
class ReportConfig:
    enabled: bool
    chat_id: int
    time: str
    timezone: str
    orders_path: Path


class AutomationService:
    """Runs background automation loops for marketing and reporting."""

    def __init__(
        self,
        bot: Any,
        marketing: MarketingConfig,
        report: ReportConfig,
    ) -> None:
        self.bot = bot
        self.marketing = marketing
        self.report = report
        self._tasks: List[asyncio.Task] = []
        self._post_idx = 0
        self._stopping = False

    async def start(self) -> None:
        self._stopping = False
        if self.marketing.enabled and self.marketing.channel_id and self.marketing.times:
            self._tasks.append(asyncio.create_task(self._run_marketing_loop(), name="marketing-loop"))
            logger.info("Marketing automation enabled (times=%s)", ",".join(self.marketing.times))
        else:
            logger.info("Marketing automation disabled")

        if self.report.enabled and self.report.chat_id:
            self._tasks.append(asyncio.create_task(self._run_report_loop(), name="report-loop"))
            logger.info("Daily report automation enabled (%s)", self.report.time)
        else:
            logger.info("Daily report automation disabled")

    async def stop(self) -> None:
        self._stopping = True
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("Automation task ended with error")
        self._tasks.clear()

    def _tz(self, tz_name: str) -> ZoneInfo:
        try:
            return ZoneInfo(tz_name)
        except Exception:
            logger.warning("Invalid timezone %s, falling back to Asia/Jerusalem", tz_name)
            return ZoneInfo("Asia/Jerusalem")

    def _load_posts(self) -> List[Dict[str, str]]:
        default_posts = [
            {
                "id": "auto_p1",
                "text": (
                    "מחפש הזמנה קצרה ודיסקרטית?\n\n"
                    "בוחרים מוצר, משלימים פרטים, וממשיכים לנציג בטלגרם.\n"
                    "להזמנה: {bot_url}?start={source_tag}_p1"
                ),
            },
            {
                "id": "auto_p2",
                "text": (
                    "הזמנה מהירה בטלגרם בלבד.\n"
                    "מחירים מעודכנים ומבצעי כמות פעילים עכשיו.\n\n"
                    "כניסה: {bot_url}?start={source_tag}_p2"
                ),
            },
        ]
        data = _load_json(self.marketing.posts_path, {"posts": default_posts})
        posts = data.get("posts", [])
        cleaned: List[Dict[str, str]] = []
        for item in posts:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text", "")).strip()
            post_id = str(item.get("id", "")).strip() or f"post_{len(cleaned)+1}"
            if text:
                cleaned.append({"id": post_id, "text": text})
        return cleaned or default_posts

    async def _run_marketing_loop(self) -> None:
        tz = self._tz(self.marketing.timezone)
        while not self._stopping:
            now = datetime.now(tz)
            deltas = [(_next_run_delta(now, hhmm), hhmm) for hhmm in self.marketing.times]
            sleep_seconds, target_hhmm = min(deltas, key=lambda x: x[0])
            await asyncio.sleep(max(1.0, sleep_seconds))
            if self._stopping:
                return
            await self._send_next_post(target_hhmm)

    async def _send_next_post(self, target_hhmm: str) -> None:
        posts = self._load_posts()
        post = posts[self._post_idx % len(posts)]
        self._post_idx += 1
        bot_username = self.marketing.bot_username.lstrip("@")
        bot_url = f"https://t.me/{bot_username}"
        text = post["text"].format(
            bot_url=bot_url,
            source_tag=self.marketing.source_tag,
            post_id=post["id"],
        )
        try:
            await self.bot.send_message(
                chat_id=self.marketing.channel_id,
                text=text,
                disable_web_page_preview=True,
            )
            logger.info("Auto-post sent (%s @ %s)", post["id"], target_hhmm)
        except Exception:
            logger.exception("Failed sending auto-post (%s)", post["id"])

    async def _run_report_loop(self) -> None:
        tz = self._tz(self.report.timezone)
        while not self._stopping:
            now = datetime.now(tz)
            sleep_seconds = _next_run_delta(now, self.report.time)
            await asyncio.sleep(max(1.0, sleep_seconds))
            if self._stopping:
                return
            await self._send_daily_report(tz)

    async def _send_daily_report(self, tz: ZoneInfo) -> None:
        orders_data = _load_json(self.report.orders_path, {"orders": []})
        orders = orders_data.get("orders", [])
        if not isinstance(orders, list):
            orders = []

        since = datetime.now(tz) - timedelta(days=1)
        matched: List[Dict[str, Any]] = []
        for order in orders:
            ts = str(order.get("created_at", ""))
            try:
                created = datetime.fromisoformat(ts)
            except Exception:
                continue
            if created.tzinfo is None:
                created = created.replace(tzinfo=tz)
            if created.astimezone(tz) >= since:
                matched.append(order)

        total_orders = len(matched)
        revenue = sum(int(o.get("total", 0) or 0) for o in matched)
        by_payment: Dict[str, int] = {}
        by_product: Dict[str, int] = {}
        for order in matched:
            pay = str(order.get("payment_method", "לא ידוע"))
            by_payment[pay] = by_payment.get(pay, 0) + 1
            for item in order.get("items", []):
                name = str(item.get("product_name", "מוצר לא ידוע"))
                qty = int(item.get("qty", 0) or 0)
                by_product[name] = by_product.get(name, 0) + qty

        payment_lines = ", ".join(f"{k}: {v}" for k, v in sorted(by_payment.items(), key=lambda x: -x[1])) or "-"
        top_products = sorted(by_product.items(), key=lambda x: -x[1])[:3]
        product_lines = ", ".join(f"{name} x{qty}" for name, qty in top_products) or "-"

        text = (
            "📊 דוח אוטומטי - 24 שעות אחרונות\n\n"
            f"🧾 הזמנות: {total_orders}\n"
            f"💰 הכנסות: ₪{revenue}\n"
            f"💳 תשלומים: {payment_lines}\n"
            f"🏆 מובילים: {product_lines}\n"
        )

        try:
            await self.bot.send_message(chat_id=self.report.chat_id, text=text)
            logger.info("Daily report sent")
        except Exception:
            logger.exception("Failed sending daily report")

