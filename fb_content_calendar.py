#!/usr/bin/env python3
"""
VITAMAN — Facebook Content Calendar & Auto-Poster

Schedule organic posts, promotional content, and manage ad rotation.

Usage:
    python fb_content_calendar.py post-next        # Post next scheduled item
    python fb_content_calendar.py list              # Show upcoming posts
    python fb_content_calendar.py add --message "..." --date "2026-04-15 10:00"
    python fb_content_calendar.py generate-week     # Auto-generate a week of posts
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

logger = logging.getLogger(__name__)

logging.basicConfig(format="%(asctime)s %(levelname)s: %(message)s", level=logging.INFO)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
CALENDAR_FILE = os.path.join(DATA_DIR, "content_calendar.json")

# ─── Post Templates ──────────────────────────────────────────

POST_TEMPLATES = [
    {
        "type": "product_highlight",
        "messages": [
            "💊 *Kamagra Oral Jelly 100mg*\n\nפעולה מהירה תוך 15 דקות. טעמים מגוונים.\nמשלוח דיסקרטי לכל הארץ.\n\n👉 להזמנה: {bot_link}",
            "🐎 *Vidalista 40mg*\n\nפעיל עד 36 שעות — גמישות מלאה.\nמוצר מקורי, משלוח דיסקרטי.\n\n👉 להזמנה: {bot_link}",
            "💪 *חבילת הגבר*\n\nKamagra + Vidalista יחד — ₪169\nחוסכים ₪19 + משלוח דיסקרטי.\n\n👉 להזמנה: {bot_link}",
        ],
    },
    {
        "type": "trust_building",
        "messages": [
            "✅ למה אלפי גברים סומכים עלינו?\n\n• מוצרים מקוריים בלבד\n• משלוח דיסקרטי ללא סימון\n• מענה מהיר תוך שעות\n• 100% פרטיות\n\n👉 {bot_link}",
            "🔒 דיסקרטיות מלאה.\n\nמהרגע שאתה מזמין ועד שהחבילה מגיעה — אף אחד לא יודע.\n\nאריזה חלקה, ללא סימונים.\n\n👉 {bot_link}",
        ],
    },
    {
        "type": "educational",
        "messages": [
            "💡 ידעת?\n\nSildenafil (Kamagra) פועל תוך 15-30 דקות ונשאר פעיל 4-6 שעות.\nTadalafil (Vidalista) פועל עד 36 שעות.\n\nלא בטוח מה מתאים לך? הנציג שלנו ישמח לעזור.\n\n👉 {bot_link}",
            "❓ שאלה נפוצה: מה ההבדל בין Kamagra ל-Vidalista?\n\n💊 Kamagra — מהיר, לערב ספציפי\n🐎 Vidalista — ארוך טווח, גמישות\n💪 לא בטוח? קח את שניהם בחבילת הגבר\n\n👉 {bot_link}",
        ],
    },
    {
        "type": "offer",
        "messages": [
            "🔥 מבצע השבוע!\n\nחבילת הגבר — ₪169 במקום ₪188\n\nKamagra Jelly + Vidalista 40 יחד.\nמשלוח דיסקרטי חינם מעל ₪150!\n\n👉 {bot_link}",
            "💰 קוד הנחה: SAVE10\n\n10% הנחה על כל ההזמנות השבוע.\nתקף גם על חבילת הגבר!\n\n👉 {bot_link}",
        ],
    },
]


def load_calendar() -> list:
    if not os.path.exists(CALENDAR_FILE):
        return []
    try:
        with open(CALENDAR_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load calendar: %s", e)
        return []


def save_calendar(cal: list):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(CALENDAR_FILE, "w", encoding="utf-8") as f:
        json.dump(cal, f, ensure_ascii=False, indent=2)


def cmd_generate_week(args):
    """Generate a week of scheduled posts."""
    cal = load_calendar()
    bot_link = cfg.TELEGRAM_BOT_URL or "https://t.me/your_bot"

    start_date = datetime.now() + timedelta(days=1)
    post_times = ["10:00", "14:00", "19:00"]

    import random
    all_messages = []
    for template in POST_TEMPLATES:
        for msg in template["messages"]:
            all_messages.append({
                "type": template["type"],
                "message": msg.format(bot_link=bot_link),
            })

    random.shuffle(all_messages)

    new_posts = []
    msg_idx = 0

    # 2 posts per day, 7 days
    for day in range(7):
        date = start_date + timedelta(days=day)
        times_today = random.sample(post_times, 2)
        for t in sorted(times_today):
            if msg_idx >= len(all_messages):
                msg_idx = 0
                random.shuffle(all_messages)

            post = {
                "scheduled_at": f"{date.strftime('%Y-%m-%d')} {t}",
                "type": all_messages[msg_idx]["type"],
                "message": all_messages[msg_idx]["message"],
                "status": "scheduled",
                "created_at": datetime.now().isoformat(),
            }
            new_posts.append(post)
            msg_idx += 1

    cal.extend(new_posts)
    save_calendar(cal)

    print(f"✅ Generated {len(new_posts)} posts for the next 7 days:")
    for p in new_posts:
        print(f"  📅 {p['scheduled_at']} — [{p['type']}] {p['message'][:50]}...")


def cmd_list(args):
    """List upcoming scheduled posts."""
    cal = load_calendar()
    pending = [p for p in cal if p.get("status") == "scheduled"]

    if not pending:
        print("📅 No scheduled posts.")
        return

    pending.sort(key=lambda x: x.get("scheduled_at", ""))
    print(f"\n📅 Upcoming Posts ({len(pending)}):\n")
    for i, p in enumerate(pending, 1):
        print(f"  {i}. [{p.get('type')}] {p['scheduled_at']}")
        print(f"     {p['message'][:80]}...")
        print()


def cmd_post_next(args):
    """Post the next scheduled item."""
    cal = load_calendar()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Find posts due
    due = [p for p in cal if p.get("status") == "scheduled" and p.get("scheduled_at", "9999") <= now]

    if not due:
        print("No posts due right now.")
        return

    client = FacebookClient.from_config(cfg)

    for post in due:
        try:
            post_id = client.post_to_page(message=post["message"])
            post["status"] = "posted"
            post["post_id"] = post_id
            post["posted_at"] = datetime.now().isoformat()
            print(f"✅ Posted: {post_id} — {post['message'][:50]}...")
        except FacebookAPIError as e:
            post["status"] = "failed"
            post["error"] = str(e)
            print(f"❌ Failed: {e}")

    save_calendar(cal)


def cmd_add(args):
    """Add a custom post to calendar."""
    cal = load_calendar()
    cal.append({
        "scheduled_at": args.date,
        "type": "custom",
        "message": args.message,
        "status": "scheduled",
        "created_at": datetime.now().isoformat(),
    })
    save_calendar(cal)
    print(f"✅ Post scheduled for {args.date}")


def main():
    parser = argparse.ArgumentParser(description="VITAMAN Content Calendar")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("generate-week", help="Generate a week of posts")
    sub.add_parser("list", help="List upcoming posts")
    sub.add_parser("post-next", help="Post due items now")

    p_add = sub.add_parser("add", help="Add a custom post")
    p_add.add_argument("--message", required=True)
    p_add.add_argument("--date", required=True, help="YYYY-MM-DD HH:MM")

    args = parser.parse_args()

    if args.command == "generate-week":
        cmd_generate_week(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "post-next":
        cmd_post_next(args)
    elif args.command == "add":
        cmd_add(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
