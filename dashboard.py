#!/usr/bin/env python3
"""
VITAMAN — Admin Dashboard

Unified view of all business metrics in the terminal.
Combines bot stats, Facebook ads, and sales data.

Usage:
    python dashboard.py              # Full dashboard
    python dashboard.py --quick      # Quick summary
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot_analytics import (
    sales_summary,
    conversion_funnel,
    customer_retention,
    top_products,
    get_orders,
    get_users,
    get_reviews,
)

logging.basicConfig(level=logging.WARNING)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def header(text: str):
    width = 60
    print(f"\n{'━'*width}")
    print(f"  {text}")
    print(f"{'━'*width}")


def bar_chart(data: dict, max_width: int = 30):
    """Simple horizontal bar chart in terminal."""
    if not data:
        print("  (אין נתונים)")
        return
    max_val = max(data.values()) if data.values() else 1
    for label, val in data.items():
        bar_len = int(val / max_val * max_width) if max_val else 0
        bar = "█" * bar_len
        print(f"  {label:>15} | {bar} {val}")


def dashboard_full():
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    print(f"""
╔══════════════════════════════════════════════════════════╗
║           📊 VITAMAN — Admin Dashboard                  ║
║           {now:>42}   ║
╚══════════════════════════════════════════════════════════╝""")

    # ─── Sales Summary (7 days) ───────────────────────────
    header("💰 מכירות — 7 ימים אחרונים")
    sales = sales_summary(7)
    print(f"  📦 הזמנות:        {sales['total_orders']}")
    print(f"  💵 הכנסות:        ₪{sales['total_revenue']:,}")
    print(f"  📈 ממוצע הזמנה:   ₪{sales['avg_order_value']}")

    # Monthly
    sales_30 = sales_summary(30)
    print(f"\n  📅 חודשי (30 יום):")
    print(f"     📦 {sales_30['total_orders']} הזמנות | 💵 ₪{sales_30['total_revenue']:,}")

    # ─── Daily Revenue Chart ──────────────────────────────
    if sales["daily_revenue"]:
        header("📅 הכנסה יומית")
        bar_chart(sales["daily_revenue"])

    # ─── Conversion Funnel ────────────────────────────────
    header("🔄 משפך המרה")
    funnel = conversion_funnel()
    print(f"  👥 מבקרים (סה\"כ):    {funnel['total_visitors']}")
    print(f"  🛒 קונים:             {funnel['unique_buyers']}")
    print(f"  🔄 חוזרים:            {funnel['repeat_buyers']}")
    print(f"  📊 שיעור המרה:        {funnel['conversion_rate']}%")
    print(f"  🔁 שיעור שימור:       {funnel['repeat_rate']}%")

    # ─── Top Products ─────────────────────────────────────
    header("🏆 מוצרים מובילים (30 יום)")
    products = top_products(30)
    if products:
        for i, (name, count) in enumerate(products, 1):
            medal = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f" {i}."
            print(f"  {medal} {name}: {count} מכירות")
    else:
        print("  (אין נתונים)")

    # ─── Payment Methods ──────────────────────────────────
    if sales["payment_methods"]:
        header("💳 אמצעי תשלום")
        bar_chart(sales["payment_methods"])

    # ─── Customer Retention ───────────────────────────────
    header("🔁 שימור לקוחות")
    ret = customer_retention()
    print(f"  סה\"כ לקוחות:   {ret['total_customers']}")
    print(f"  חד פעמיים:     {ret['one_time_buyers']}")
    print(f"  חוזרים:        {ret['returning_buyers']}")
    print(f"  שימור:         {ret['retention_rate']}%")

    # ─── Reviews ──────────────────────────────────────────
    header("⭐ ביקורות")
    reviews = get_reviews()
    if reviews:
        ratings = [r.get("rating", 0) for r in reviews if r.get("rating")]
        avg = round(sum(ratings) / len(ratings), 1) if ratings else 0
        print(f"  ⭐ דירוג ממוצע: {'⭐' * round(avg)} ({avg}/5)")
        print(f"  סה\"כ: {len(reviews)} ביקורות")
    else:
        print("  (אין ביקורות עדיין)")

    # ─── Facebook Ads ─────────────────────────────────────
    header("📱 פרסום בפייסבוק")
    try:
        from config import cfg
        from facebook.client import FacebookClient
        client = FacebookClient(
            page_access_token=cfg.FB_PAGE_ACCESS_TOKEN,
            page_id=cfg.FB_PAGE_ID,
            ad_account_id=cfg.FB_AD_ACCOUNT_ID,
        )
        campaigns = client.list_campaigns()
        active = [c for c in campaigns if c.get("status") == "ACTIVE"]
        print(f"  קמפיינים פעילים: {len(active)}")
        print(f"  סה\"כ קמפיינים:   {len(campaigns)}")

        for camp in active[:3]:
            try:
                insights = client.get_ad_insights(camp["id"], date_preset="last_7d")
                data = insights.get("data", [{}])
                if data:
                    d = data[0]
                    print(f"\n  📢 {camp['name']}:")
                    print(f"     הוצאה: ₪{d.get('spend', 'N/A')} | קליקים: {d.get('clicks', 'N/A')} | CTR: {d.get('ctr', 'N/A')}%")
            except Exception:
                pass
    except Exception as e:
        print(f"  ⚠️  לא ניתן להתחבר לפייסבוק: {e}")

    # ─── Referrals ────────────────────────────────────────
    header("🎁 הפניות")
    try:
        from bot_referral import _load_referrals
        ref_db = _load_referrals()
        referrals = ref_db.get("referrals", {})
        uses = ref_db.get("uses", [])
        print(f"  קודי הפניה פעילים: {len(referrals)}")
        print(f"  שימושים:            {len(uses)}")
    except Exception:
        print("  (מערכת הפניות לא מוגדרת)")

    print(f"\n{'═'*60}")
    print(f"  🔗 VITAMAN Dashboard — נוצר ב-{now}")
    print(f"{'═'*60}\n")


def dashboard_quick():
    """Quick one-liner stats."""
    sales = sales_summary(7)
    users = get_users()
    orders = get_orders()
    print(f"📊 VITAMAN Quick Stats: 👥 {len(users)} users | 📦 {len(orders)} orders | 💰 ₪{sales['total_revenue']:,} (7d)")


def main():
    parser = argparse.ArgumentParser(description="VITAMAN Admin Dashboard")
    parser.add_argument("--quick", action="store_true", help="Quick summary only")
    args = parser.parse_args()

    if args.quick:
        dashboard_quick()
    else:
        dashboard_full()


if __name__ == "__main__":
    main()
