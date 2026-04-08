#!/usr/bin/env python3
"""
VITAMAN — Bot Analytics & Enhanced Stats

Provides detailed analytics for the bot:
- Conversion funnel (views → cart → checkout → purchase)
- Daily/weekly/monthly sales reports
- Product breakdown
- Customer retention

Usage (as module):
    from bot_analytics import get_full_stats, get_funnel_report

Usage (standalone):
    python bot_analytics.py
"""

import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
ORDERS_FILE = os.path.join(DATA_DIR, "orders.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
REVIEWS_FILE = os.path.join(DATA_DIR, "reviews.json")


def _load(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def get_orders() -> List[Dict]:
    return _load(ORDERS_FILE, {"orders": []}).get("orders", [])


def get_users() -> List[Dict]:
    return _load(USERS_FILE, {"users": []}).get("users", [])


def get_reviews() -> List[Dict]:
    return _load(REVIEWS_FILE, {"reviews": []}).get("reviews", [])


def get_orders_in_range(days: int = 7) -> List[Dict]:
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    return [o for o in get_orders() if o.get("created_at", "") >= cutoff]


# ─── Sales Reports ──────────────────────────────────────────

def sales_summary(days: int = 7) -> Dict[str, Any]:
    orders = get_orders_in_range(days)
    total_revenue = sum(o.get("total", 0) for o in orders)
    total_orders = len(orders)
    avg_order = total_revenue / total_orders if total_orders else 0

    # Product breakdown
    product_counts: Counter = Counter()
    product_revenue: Counter = Counter()
    for o in orders:
        items = o.get("items", {})
        if isinstance(items, dict):
            for key, qty in items.items():
                product_counts[key] += qty
                # Estimate revenue per product
        product_revenue[o.get("product", "unknown")] += o.get("total", 0)

    # Daily breakdown
    daily: Dict[str, int] = defaultdict(int)
    for o in orders:
        date = o.get("created_at", "")[:10]
        if date:
            daily[date] += o.get("total", 0)

    # Payment methods
    payment_methods: Counter = Counter()
    for o in orders:
        payment_methods[o.get("payment", "unknown")] += 1

    return {
        "period_days": days,
        "total_orders": total_orders,
        "total_revenue": total_revenue,
        "avg_order_value": round(avg_order),
        "product_counts": dict(product_counts),
        "daily_revenue": dict(daily),
        "payment_methods": dict(payment_methods),
    }


def conversion_funnel() -> Dict[str, Any]:
    """Estimate conversion funnel from available data."""
    users = get_users()
    orders = get_orders()

    total_users = len(users)
    total_orders = len(orders)
    unique_buyers = len(set(o.get("user_id") for o in orders if o.get("user_id")))
    repeat_buyers = len([
        uid for uid, count in Counter(o.get("user_id") for o in orders).items()
        if count > 1
    ])

    conversion_rate = (unique_buyers / total_users * 100) if total_users else 0
    repeat_rate = (repeat_buyers / unique_buyers * 100) if unique_buyers else 0

    return {
        "total_visitors": total_users,
        "unique_buyers": unique_buyers,
        "repeat_buyers": repeat_buyers,
        "total_orders": total_orders,
        "conversion_rate": round(conversion_rate, 1),
        "repeat_rate": round(repeat_rate, 1),
    }


def top_products(days: int = 30) -> List[Tuple[str, int]]:
    orders = get_orders_in_range(days)
    product_counts: Counter = Counter()
    for o in orders:
        cart = o.get("cart", {})
        if isinstance(cart, dict):
            for key, qty in cart.items():
                product_counts[key] += int(qty)
        elif o.get("product"):
            product_counts[o["product"]] += 1
    return product_counts.most_common(10)


def customer_retention() -> Dict[str, Any]:
    """Analyze customer retention."""
    orders = get_orders()
    user_orders: Dict[int, List[str]] = defaultdict(list)
    for o in orders:
        uid = o.get("user_id")
        date = o.get("created_at", "")[:10]
        if uid and date:
            user_orders[uid].append(date)

    one_time = sum(1 for dates in user_orders.values() if len(dates) == 1)
    returning = sum(1 for dates in user_orders.values() if len(dates) > 1)
    total = len(user_orders)

    return {
        "total_customers": total,
        "one_time_buyers": one_time,
        "returning_buyers": returning,
        "retention_rate": round(returning / total * 100, 1) if total else 0,
    }


# ─── Formatted Reports ──────────────────────────────────────

def format_stats_report(days: int = 7) -> str:
    """Generate formatted stats report for Telegram /stats command."""
    sales = sales_summary(days)
    funnel = conversion_funnel()
    retention = customer_retention()
    reviews = get_reviews()

    avg_rating = 0
    if reviews:
        ratings = [r.get("rating", 0) for r in reviews if r.get("rating")]
        avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else 0

    report = (
        f"📊 *דוח סטטיסטיקות — {days} ימים אחרונים*\n"
        f"{'═'*30}\n\n"
        f"💰 *מכירות:*\n"
        f"  📦 הזמנות: {sales['total_orders']}\n"
        f"  💵 הכנסות: ₪{sales['total_revenue']:,}\n"
        f"  📈 ממוצע הזמנה: ₪{sales['avg_order_value']}\n\n"
        f"👥 *לקוחות:*\n"
        f"  🆕 סה\"כ משתמשים: {funnel['total_visitors']}\n"
        f"  🛒 קונים: {funnel['unique_buyers']}\n"
        f"  🔄 חוזרים: {funnel['repeat_buyers']}\n"
        f"  📊 המרה: {funnel['conversion_rate']}%\n"
        f"  🔁 שימור: {retention['retention_rate']}%\n\n"
        f"⭐ *ביקורות:*\n"
        f"  דירוג ממוצע: {'⭐' * round(avg_rating)} ({avg_rating}/5)\n"
        f"  סה\"כ ביקורות: {len(reviews)}\n\n"
    )

    # Payment methods
    if sales["payment_methods"]:
        report += "💳 *אמצעי תשלום:*\n"
        for method, count in sales["payment_methods"].items():
            report += f"  {method}: {count}\n"
        report += "\n"

    # Daily revenue
    if sales["daily_revenue"]:
        report += "📅 *הכנסה יומית:*\n"
        for date, rev in sorted(sales["daily_revenue"].items())[-7:]:
            report += f"  {date}: ₪{rev:,}\n"

    return report


def format_quick_stats() -> str:
    """Quick one-line stats for splash screens."""
    orders = get_orders()
    users = get_users()
    revenue = sum(o.get("total", 0) for o in orders)
    return f"👥 {len(users)} | 📦 {len(orders)} | 💰 ₪{revenue:,}"


# ─── Standalone Usage ─────────────────────────────────────────

def main():
    print(format_stats_report(30))
    print("\n" + "=" * 40)
    print("\n📈 Conversion Funnel:")
    funnel = conversion_funnel()
    for k, v in funnel.items():
        print(f"  {k}: {v}")

    print("\n🏆 Top Products (30 days):")
    for product, count in top_products(30):
        print(f"  {product}: {count}")

    print("\n🔁 Retention:")
    ret = customer_retention()
    for k, v in ret.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
