#!/usr/bin/env python3
"""
VITAMAN — Facebook Campaign Manager CLI

Create, manage, and monitor Facebook ad campaigns from the command line.
Includes A/B testing support and automatic audience creation.

Usage:
    python fb_campaign_manager.py create-campaign --name "Spring Sale"
    python fb_campaign_manager.py create-full --budget 50
    python fb_campaign_manager.py report
    python fb_campaign_manager.py list
    python fb_campaign_manager.py create-audience --source bot_users
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import cfg
from facebook.client import FacebookClient, FacebookAPIError

logging.basicConfig(
    format="%(asctime)s %(levelname)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

# ─── Ad Copy Templates ────────────────────────────────────────

AD_VARIATIONS = [
    {
        "name": "Direct — Telegram CTA",
        "message": (
            "מחפש פתרון דיסקרטי, מקורי ואמין?\n\n"
            "הכירו את DrViagra Shop — מוצרים מקוריים, משלוח דיסקרטי, "
            "ומענה מהיר.\n\n"
            "✔️ מקורי\n✔️ דיסקרטי\n✔️ הזמנה מהירה דרך טלגרם\n\n"
            "👇 לחץ להזמנה"
        ),
        "headline": "DrViagra Shop — מקורי ודיסקרטי",
        "description": "הזמנה מהירה דרך טלגרם. משלוח דיסקרטי.",
        "cta": "SEND_MESSAGE",
    },
    {
        "name": "Premium — Trust",
        "message": (
            "לא כל חנות היא אותו דבר.\n\n"
            "DrViagra Shop — מוצרים מקוריים בלבד, "
            "אריזה דיסקרטית, ותהליך קנייה קצר וברור.\n\n"
            "💊 Kamagra · 🐎 Vidalista · 💪 חבילת הגבר\n\n"
            "לחץ, בחר מוצר, ודבר עם נציג."
        ),
        "headline": "מוצרים מקוריים — DrViagra Shop",
        "description": "חנות מקוונת דיסקרטית. משלוח לכל הארץ.",
        "cta": "LEARN_MORE",
    },
    {
        "name": "Bundle Offer",
        "message": (
            "רוצה להתחיל נכון?\n\n"
            "עם חבילת הגבר אתה מקבל Kamagra + Vidalista "
            "יחד במחיר משתלם.\n\n"
            "📦 משלוח דיסקרטי\n"
            "⚡ מענה תוך שעות\n"
            "💰 חוסכים ₪19\n\n"
            "👇 לחנות בטלגרם"
        ),
        "headline": "חבילת הגבר — ₪169",
        "description": "Kamagra + Vidalista יחד. משלוח דיסקרטי.",
        "cta": "SHOP_NOW",
    },
]

# ─── Targeting Presets ─────────────────────────────────────────

TARGETING_PRESETS = {
    "broad_men_30_55": {
        "name": "Men 30-55 Israel — Broad",
        "geo_locations": {"countries": ["IL"]},
        "age_min": 30,
        "age_max": 55,
        "genders": [1],
        "publisher_platforms": ["facebook", "instagram"],
        "facebook_positions": ["feed", "story", "marketplace"],
        "instagram_positions": ["stream", "story", "reels"],
    },
    "health_interest": {
        "name": "Men 30-55 Israel — Health Interest",
        "geo_locations": {"countries": ["IL"]},
        "age_min": 30,
        "age_max": 55,
        "genders": [1],
        "flexible_spec": [
            {
                "interests": [
                    {"id": "6003107902433", "name": "Health"},
                    {"id": "6003012347806", "name": "Dietary supplement"},
                    {"id": "6003020834693", "name": "Fitness"},
                ]
            }
        ],
        "publisher_platforms": ["facebook", "instagram"],
        "facebook_positions": ["feed", "story"],
        "instagram_positions": ["stream", "story"],
    },
    "lookalike": {
        "name": "Lookalike from purchases",
        "geo_locations": {"countries": ["IL"]},
        "age_min": 25,
        "age_max": 60,
        "genders": [1],
        "publisher_platforms": ["facebook", "instagram"],
    },
    "retarget_visitors": {
        "name": "Retarget — Website + Bot visitors",
        "geo_locations": {"countries": ["IL"]},
        "age_min": 25,
        "age_max": 60,
        "genders": [1],
        "publisher_platforms": ["facebook", "instagram"],
    },
}


def get_client() -> FacebookClient:
    return FacebookClient.from_config(cfg)


# ─── Commands ─────────────────────────────────────────────────

def cmd_create_campaign(args):
    """Create a single campaign."""
    client = get_client()
    campaign_id = client.create_campaign(
        name=args.name,
        objective=args.objective,
        status="PAUSED",
        daily_budget=int(args.budget * 100),
    )
    print(f"✅ Campaign created: {campaign_id}")
    print(f"   Name: {args.name}")
    print(f"   Budget: ₪{args.budget}/day")
    print(f"   Status: PAUSED (activate in Ads Manager)")
    return campaign_id


def cmd_create_full(args):
    """Create a full campaign with A/B ad variations."""
    client = get_client()
    budget_agorot = int(args.budget * 100)

    date_str = datetime.now().strftime("%Y%m%d")
    campaign_name = f"VITAMAN Auto — {date_str}"

    print(f"\n🚀 Creating full campaign: {campaign_name}")
    print(f"   Daily budget: ₪{args.budget}")
    print(f"   Ad variations: {len(AD_VARIATIONS)}")
    print()

    # 1. Campaign
    campaign_id = client.create_campaign(
        name=campaign_name,
        objective="OUTCOME_TRAFFIC",
        status="PAUSED",
        daily_budget=budget_agorot,
    )
    print(f"✅ Campaign: {campaign_id}")

    # 2. Targeting
    targeting_key = args.targeting or "health_interest"
    targeting = TARGETING_PRESETS.get(targeting_key, TARGETING_PRESETS["health_interest"])
    targeting_clean = {k: v for k, v in targeting.items() if k != "name"}

    # 3. Ad Set per variation (A/B test)
    results = []
    per_variation_budget = max(budget_agorot // len(AD_VARIATIONS), 500)

    for i, variation in enumerate(AD_VARIATIONS, 1):
        adset_name = f"{campaign_name} — AdSet {i}: {variation['name']}"

        ad_set_id = client.create_ad_set(
            campaign_id=campaign_id,
            name=adset_name,
            daily_budget=per_variation_budget,
            targeting=targeting_clean,
            optimization_goal="LINK_CLICKS",
            status="PAUSED",
        )
        print(f"  ✅ Ad Set {i}: {ad_set_id} ({variation['name']})")

        # 4. Creative
        link = cfg.TELEGRAM_BOT_URL or "https://t.me/your_bot"
        creative_id = client.create_ad_creative(
            name=f"Creative — {variation['name']}",
            message=variation["message"],
            link=link,
            headline=variation["headline"],
            description=variation["description"],
        )
        print(f"     Creative: {creative_id}")

        # 5. Ad
        ad_id = client.create_ad(
            ad_set_id=ad_set_id,
            creative_id=creative_id,
            name=f"Ad — {variation['name']}",
            status="PAUSED",
        )
        print(f"     Ad: {ad_id}")

        results.append({
            "variation": variation["name"],
            "ad_set_id": ad_set_id,
            "creative_id": creative_id,
            "ad_id": ad_id,
        })

    # Save results
    os.makedirs(DATA_DIR, exist_ok=True)
    result_file = os.path.join(DATA_DIR, f"campaign_{date_str}.json")
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump({
            "campaign_id": campaign_id,
            "campaign_name": campaign_name,
            "created_at": datetime.now().isoformat(),
            "budget_daily_ils": args.budget,
            "targeting": targeting_key,
            "variations": results,
        }, f, ensure_ascii=False, indent=2)

    print(f"\n📁 Results saved to: {result_file}")
    print(f"\n⚠️  All ads are PAUSED. Review in Ads Manager and activate when ready.")


def cmd_report(args):
    """Show performance report for active campaigns."""
    client = get_client()

    campaigns = client.list_campaigns()
    if not campaigns:
        print("No campaigns found.")
        return

    print(f"\n📊 Campaign Performance Report — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)

    for camp in campaigns:
        print(f"\n🏷  {camp.get('name', 'Unknown')}")
        print(f"   ID: {camp.get('id')} | Status: {camp.get('status')}")
        print(f"   Objective: {camp.get('objective')} | Budget: {camp.get('daily_budget', 'N/A')}")

        # Try to get insights
        try:
            insights = client.get_ad_insights(camp["id"], date_preset=args.period or "last_7d")
            data = insights.get("data", [])
            if data:
                d = data[0]
                print(f"   Impressions: {d.get('impressions', 'N/A')}")
                print(f"   Clicks: {d.get('clicks', 'N/A')}")
                print(f"   CTR: {d.get('ctr', 'N/A')}%")
                print(f"   Spend: ₪{d.get('spend', 'N/A')}")
                print(f"   Reach: {d.get('reach', 'N/A')}")
            else:
                print("   No data for this period.")
        except FacebookAPIError as e:
            print(f"   ⚠️  Could not fetch insights: {e}")

    print("\n" + "=" * 70)


def cmd_list(args):
    """List all campaigns."""
    client = get_client()
    campaigns = client.list_campaigns()

    if not campaigns:
        print("No campaigns found.")
        return

    print(f"\n📋 Campaigns ({len(campaigns)}):")
    for camp in campaigns:
        status_icon = "🟢" if camp.get("status") == "ACTIVE" else "⏸️"
        print(f"  {status_icon} {camp.get('name')} (ID: {camp.get('id')}) — {camp.get('status')}")


def cmd_create_audience(args):
    """Create custom audience from bot users for retargeting."""
    client = get_client()

    if args.source == "bot_users":
        # Load users from bot data
        users_file = os.path.join(DATA_DIR, "users.json")
        if not os.path.exists(users_file):
            print("❌ No users.json found. Run the bot first to collect users.")
            return

        with open(users_file, "r", encoding="utf-8") as f:
            db = json.load(f)

        users = db.get("users", [])
        if not users:
            print("❌ No users in database.")
            return

        # Extract phone numbers for matching
        phones = []
        for u in users:
            # Try to find phone from orders
            pass  # Phone data comes from orders

        orders_file = os.path.join(DATA_DIR, "orders.json")
        if os.path.exists(orders_file):
            with open(orders_file, "r", encoding="utf-8") as f:
                orders_db = json.load(f)
            for order in orders_db.get("orders", []):
                phone = order.get("phone", "")
                if phone:
                    phones.append(phone)

        print(f"📱 Found {len(phones)} phone numbers from orders")
        print(f"👥 Found {len(users)} Telegram users")

        # Create custom audience via API
        if not cfg.FB_AD_ACCOUNT_ID:
            print("❌ FB_AD_ACCOUNT_ID not configured")
            return

        import hashlib
        hashed_phones = []
        for p in phones:
            clean = p.replace("-", "").replace(" ", "")
            if not clean.startswith("+"):
                clean = "+972" + clean.lstrip("0")
            hashed_phones.append(hashlib.sha256(clean.encode()).hexdigest())

        payload = {
            "name": f"Bot Customers — {datetime.now().strftime('%Y-%m-%d')}",
            "subtype": "CUSTOM",
            "description": "Customers from Telegram bot orders",
            "customer_file_source": "USER_PROVIDED_ONLY",
        }

        try:
            result = client._post(f"{cfg.FB_AD_ACCOUNT_ID}/customaudiences", data=payload)
            audience_id = result.get("id", "")
            print(f"✅ Custom audience created: {audience_id}")

            # Add users
            if hashed_phones:
                users_payload = {
                    "payload": json.dumps({
                        "schema": ["PHONE"],
                        "data": [[ph] for ph in hashed_phones],
                    }),
                }
                client._post(f"{audience_id}/users", data=users_payload)
                print(f"   Added {len(hashed_phones)} hashed phone numbers")

            print(f"\n💡 Use this audience for retargeting or create a Lookalike in Ads Manager.")
        except FacebookAPIError as e:
            print(f"❌ Error creating audience: {e}")

    elif args.source == "purchasers":
        print("Creating purchaser audience from CAPI events...")
        print("💡 Facebook automatically builds this from your Pixel Purchase events.")
        print("   Go to Audiences → Custom Audience → Website → Purchase event")
    else:
        print(f"Unknown source: {args.source}")


def cmd_post_organic(args):
    """Post organic content to Facebook page."""
    client = get_client()

    post_id = client.post_to_page(
        message=args.message,
        link=args.link,
    )
    print(f"✅ Posted to page: {post_id}")


# ─── CLI Setup ─────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="VITAMAN — Facebook Campaign Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python fb_campaign_manager.py create-full --budget 50
  python fb_campaign_manager.py report --period last_7d
  python fb_campaign_manager.py list
  python fb_campaign_manager.py create-audience --source bot_users
  python fb_campaign_manager.py post --message "מבצע חדש!" --link https://t.me/bot
        """,
    )
    sub = parser.add_subparsers(dest="command")

    # create-campaign
    p1 = sub.add_parser("create-campaign", help="Create a single campaign")
    p1.add_argument("--name", required=True, help="Campaign name")
    p1.add_argument("--budget", type=float, default=50, help="Daily budget in ILS")
    p1.add_argument("--objective", default="OUTCOME_TRAFFIC", help="Campaign objective")

    # create-full
    p2 = sub.add_parser("create-full", help="Create full A/B test campaign")
    p2.add_argument("--budget", type=float, default=50, help="Total daily budget in ILS")
    p2.add_argument("--targeting", choices=list(TARGETING_PRESETS.keys()), default="health_interest")

    # report
    p3 = sub.add_parser("report", help="Show performance report")
    p3.add_argument("--period", default="last_7d", choices=["today", "yesterday", "last_7d", "last_30d", "this_month"])

    # list
    sub.add_parser("list", help="List all campaigns")

    # create-audience
    p5 = sub.add_parser("create-audience", help="Create custom audience")
    p5.add_argument("--source", required=True, choices=["bot_users", "purchasers"])

    # post
    p6 = sub.add_parser("post", help="Post organic content")
    p6.add_argument("--message", required=True, help="Post text")
    p6.add_argument("--link", default=None, help="Optional link")

    args = parser.parse_args()

    if args.command == "create-campaign":
        cmd_create_campaign(args)
    elif args.command == "create-full":
        cmd_create_full(args)
    elif args.command == "report":
        cmd_report(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "create-audience":
        cmd_create_audience(args)
    elif args.command == "post":
        cmd_post_organic(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
