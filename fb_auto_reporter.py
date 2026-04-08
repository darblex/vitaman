#!/usr/bin/env python3
"""
VITAMAN — Facebook Auto-Reporter

Sends daily/weekly performance reports to the seller via Telegram.
Run with cron or scheduled task:
    python fb_auto_reporter.py --period daily
    python fb_auto_reporter.py --period weekly
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import cfg
from facebook.client import FacebookClient, FacebookAPIError

logging.basicConfig(format="%(asctime)s %(levelname)s: %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")


def get_bot_stats() -> dict:
    """Load bot statistics from data files."""
    stats = {"total_orders": 0, "total_revenue": 0, "total_users": 0, "recent_orders": []}

    orders_file = os.path.join(DATA_DIR, "orders.json")
    if os.path.exists(orders_file):
        with open(orders_file, "r", encoding="utf-8") as f:
            db = json.load(f)
        orders = db.get("orders", [])
        stats["total_orders"] = len(orders)
        stats["total_revenue"] = sum(o.get("total", 0) for o in orders)
        stats["recent_orders"] = orders[-5:]

    users_file = os.path.join(DATA_DIR, "users.json")
    if os.path.exists(users_file):
        with open(users_file, "r", encoding="utf-8") as f:
            db = json.load(f)
        stats["total_users"] = len(db.get("users", []))

    return stats


def get_fb_report(period: str = "last_7d") -> str:
    """Generate Facebook ads performance report text."""
    try:
        client = FacebookClient.from_config(cfg)
        campaigns = client.list_campaigns()
    except Exception as e:
        return f"⚠️ לא ניתן למשוך נתוני פייסבוק: {e}"

    if not campaigns:
        return "אין קמפיינים פעילים."

    lines = []
    total_spend = 0
    total_clicks = 0
    total_impressions = 0

    for camp in campaigns:
        if camp.get("status") != "ACTIVE":
            continue
        try:
            insights = client.get_ad_insights(camp["id"], date_preset=period)
            data = insights.get("data", [])
            if data:
                d = data[0]
                spend = float(d.get("spend", 0))
                clicks = int(d.get("clicks", 0))
                impressions = int(d.get("impressions", 0))
                ctr = d.get("ctr", "0")

                total_spend += spend
                total_clicks += clicks
                total_impressions += impressions

                lines.append(
                    f"📢 *{camp['name']}*\n"
                    f"   הוצאה: ₪{spend:.0f} | קליקים: {clicks} | CTR: {ctr}%\n"
                    f"   חשיפות: {impressions:,}"
                )
        except Exception as e:
            logger.debug("Skipping campaign %s: %s", camp.get("id"), e)
            continue

    if not lines:
        return "אין נתונים לקמפיינים פעילים."

    summary_lines = [
        f"💰 סה\"כ הוצאה: ₪{total_spend:.0f}",
        f"👆 סה\"כ קליקים: {total_clicks:,}",
        f"👁 סה\"כ חשיפות: {total_impressions:,}",
    ]
    if total_impressions > 0:
        ctr = total_clicks / total_impressions * 100
        summary_lines.append(f"📊 CTR ממוצע: {ctr:.2f}%")
    summary = "\n".join(summary_lines) + "\n"

    return "\n\n".join(lines) + f"\n\n{'─'*30}\n{summary}"


def generate_report(period: str = "daily") -> str:
    """Generate full combined report."""
    date_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    period_label = "יומי" if period == "daily" else "שבועי"
    fb_period = "today" if period == "daily" else "last_7d"

    bot_stats = get_bot_stats()
    fb_report = get_fb_report(fb_period)

    report = (
        f"📊 *דוח {period_label} — VITAMAN*\n"
        f"📅 {date_str}\n"
        f"{'═'*30}\n\n"
        f"🤖 *בוט טלגרם:*\n"
        f"👥 משתמשים: {bot_stats['total_users']}\n"
        f"📦 הזמנות (סה\"כ): {bot_stats['total_orders']}\n"
        f"💰 הכנסות (סה\"כ): ₪{bot_stats['total_revenue']}\n\n"
        f"{'─'*30}\n\n"
        f"📱 *פייסבוק:*\n"
        f"{fb_report}\n\n"
        f"{'═'*30}\n"
        f"🔗 דוח אוטומטי — VITAMAN Marketing"
    )

    return report


def send_to_telegram(text: str) -> None:
    """Send report to seller via Telegram (sync, uses requests)."""
    import requests as _requests

    url = f"https://api.telegram.org/bot{cfg.BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": cfg.SELLER_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
    }
    resp = _requests.post(url, json=payload, timeout=10)
    if resp.status_code == 200:
        logger.info("Report sent to Telegram")
    else:
        logger.error("Failed to send report: %s", resp.text)


def main():
    parser = argparse.ArgumentParser(description="VITAMAN Auto Reporter")
    parser.add_argument("--period", choices=["daily", "weekly"], default="daily")
    parser.add_argument("--print-only", action="store_true", help="Print report without sending")
    args = parser.parse_args()

    report = generate_report(args.period)

    if args.print_only:
        print(report)
    else:
        send_to_telegram(report)
        print("✅ Report sent to Telegram!")


if __name__ == "__main__":
    main()
