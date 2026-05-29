#!/usr/bin/env python3
"""DrViagra Shop Telegram Bot (upgraded)

Keeps existing features from bot.py:
- Order IDs (VT-xxxx) + persistence to data/*.json
- Admin: /orders, /broadcast, /statusupdate
- Abandoned-order reminders
- Review collection (stars)
- WhatsApp redirect after order

Adds:
- Shopping cart (multi-product)
- Back button on every screen
- /myorders command (last 5 orders)
- /stats admin command
- Coupon codes (data/coupons.json)
- Payment proof upload (photo/screenshot) for non-cash methods
- Upsell button to bundle on kamagra/vidalista product pages

Python-Telegram-Bot v20+
"""

import json
import logging
import os
import urllib.parse
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import (
    BASE_DIR,
    BOT_TOKEN,
    DATA_DIR,
    DISCOUNT_PCT,
    DISCOUNT_THRESHOLD,
    MAX_QTY,
    REMINDER_DELAY_SECONDS,
    SELLER_CHAT_ID,
    SELLER_USERNAME,
    WHATSAPP_NUMBER,
)
USERS_FILE = os.path.join(DATA_DIR, "users.json")
ORDERS_FILE = os.path.join(DATA_DIR, "orders.json")
REVIEWS_FILE = os.path.join(DATA_DIR, "reviews.json")
COUNTERS_FILE = os.path.join(DATA_DIR, "counters.json")
COUPONS_FILE = os.path.join(DATA_DIR, "coupons.json")

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ─── PRODUCTS ─────────────────────────────────────────────────
PRODUCTS: Dict[str, Dict[str, Any]] = {
    "kamagra": {
        "name": "Kamagra Oral Jelly 100mg",
        "emoji": "💊",
        "desc": "Sildenafil Oral Jelly 100mg\n\n⏱ פעולה מהירה תוך 15 דקות\n🍊 טעמים מגוונים, נוח לשימוש\n📦 משלוח דיסקרטי ללא סימון\n✅ מוצר מקורי — תוצאות מוכחות",
        "pills_per_pack": 7,
        "base_price": 89,
        "image": os.path.join(BASE_DIR, "images", "product1.jpg"),
    },
    "vidalista": {
        "name": "Vidalista 40mg (Tadalafil)",
        "emoji": "🐎",
        "desc": "Tadalafil 40mg\n\n⏳ פעיל עד *36 שעות* — גמישות מלאה\n💊 כדור קטן, קל לבליעה\n📦 משלוח דיסקרטי ללא סימון\n✅ מוצר מקורי — הפתרון האמין",
        "pills_per_pack": 10,
        "base_price": 99,
        "image": os.path.join(BASE_DIR, "images", "product2.jpg"),
    },
    "bundle": {
        "name": "חבילת הגבר — Kamagra + Vidalista",
        "emoji": "💪",
        "desc": "Kamagra Jelly + Vidalista 40 יחד\n\n✅ ניסוי מלא — פעולה מהירה + טווח ארוך\n💰 חוסכים ₪19 לעומת קנייה נפרדת\n📦 משלוח דיסקרטי ללא סימון\n🏆 החבילה הכי נמכרת",
        "pills_per_pack": 17,
        "base_price": 169,
        "image": os.path.join(BASE_DIR, "images", "product1.jpg"),
    },
}

PAYMENT_OPTIONS = ["מזומן", "ביט", "פייבוקס", "העברה בנקאית"]


# ─── ORDER FLOW STATES (required) ─────────────────────────────
QTY = 0
NAME = 1
CITY = 2
PHONE = 3
DELIVERY = 4
COUPON = 7  # kept for reference, not used in flow
PAYMENT = 5
PROOF = 6

BROADCAST_TEXT = 10
STATUS_ORDER_ID, STATUS_TEXT = range(20, 22)


# ─── TEXTS ────────────────────────────────────────────────────
SPLASH_TEXT = (
    "💊 *DrViagra Shop*\n\n"
    "_מקורי · דיסקרטי · מהימן_\n\n"
    "─────────────────\n"
    "✅ מוצרים מקוריים בלבד\n"
    "📦 משלוח דיסקרטי לכל הארץ\n"
    "🔒 100% פרטיות מובטחת\n"
    "⚡ מענה תוך שעות\n"
    "─────────────────\n\n"
    "{rating_line}\n\n"
    "לחץ כדי להיכנס לחנות 👇"
)

STORE_TEXT = "🛍 *בחר מוצר:*"

def build_splash_text() -> str:
    stats = get_review_stats()
    if stats["count"] > 0:
        stars_str = '⭐' * round(stats['avg'])
        rating_line = f"{stars_str} *{stats['avg']}/5* — {stats['count']} לקוחות מרוצים"
    else:
        rating_line = "⭐ חנות חדשה — הצטרף ללקוחות הראשונים!"
    return SPLASH_TEXT.format(rating_line=rating_line)

def build_welcome_text() -> str:
    return build_splash_text()


# ─── DATA HELPERS ─────────────────────────────────────────────

def ensure_data_files() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)

    defaults = {
        USERS_FILE: {"users": []},
        ORDERS_FILE: {"orders": []},
        REVIEWS_FILE: {"reviews": []},
        COUNTERS_FILE: {"last_order_seq": 0},
        COUPONS_FILE: {
            "codes": {
                "SAVE10": {"type": "percent", "value": 10},
                "VIP20": {"type": "percent", "value": 20},
            }
        },
    }

    for path, default in defaults.items():
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                json.dump(default, f, ensure_ascii=False, indent=2)


def load_json(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Failed reading %s: %s", path, e)
        return default


def save_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def is_admin(user_id: int) -> bool:
    return user_id == SELLER_CHAT_ID


def register_user(user) -> None:
    db = load_json(USERS_FILE, {"users": []})
    users = db.get("users", [])
    uid = user.id
    existing = next((u for u in users if u.get("id") == uid), None)

    payload = {
        "id": uid,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "last_seen": now_iso(),
    }

    if existing:
        existing.update(payload)
    else:
        payload["joined_at"] = now_iso()
        users.append(payload)

    db["users"] = users
    save_json(USERS_FILE, db)


def get_all_user_ids() -> List[int]:
    db = load_json(USERS_FILE, {"users": []})
    return [u["id"] for u in db.get("users", []) if u.get("id")]


def next_order_id() -> str:
    counters = load_json(COUNTERS_FILE, {"last_order_seq": 0})
    seq = int(counters.get("last_order_seq", 0)) + 1
    counters["last_order_seq"] = seq
    save_json(COUNTERS_FILE, counters)
    return f"VT-{seq:04d}"


def save_order(order: Dict[str, Any]) -> None:
    db = load_json(ORDERS_FILE, {"orders": []})
    db.setdefault("orders", []).append(order)
    save_json(ORDERS_FILE, db)


def get_orders() -> List[Dict[str, Any]]:
    db = load_json(ORDERS_FILE, {"orders": []})
    return db.get("orders", [])


def get_order(order_id: str) -> Optional[Dict[str, Any]]:
    for order in get_orders():
        if order.get("order_id") == order_id:
            return order
    return None


def update_order_status(order_id: str, status_text: str) -> Optional[Dict[str, Any]]:
    db = load_json(ORDERS_FILE, {"orders": []})
    for order in db.get("orders", []):
        if order.get("order_id") == order_id:
            order["status"] = status_text
            order["status_updated_at"] = now_iso()
            save_json(ORDERS_FILE, db)
            return order
    return None


def save_review(review: Dict[str, Any]) -> None:
    db = load_json(REVIEWS_FILE, {"reviews": []})
    reviews = db.setdefault("reviews", [])
    existing = next((r for r in reviews if r.get("order_id") == review.get("order_id")), None)
    if existing:
        existing.update(review)
    else:
        reviews.append(review)
    save_json(REVIEWS_FILE, db)


def get_review_stats() -> Dict[str, Any]:
    db = load_json(REVIEWS_FILE, {"reviews": []})
    reviews = db.get("reviews", [])
    if not reviews:
        return {"count": 0, "avg": 0}
    total = sum(int(r.get("rating", 0)) for r in reviews if r.get("rating"))
    count = len([r for r in reviews if r.get("rating")])
    if count == 0:
        return {"count": 0, "avg": 0}
    return {"count": count, "avg": round(total / count, 1)}


# ─── BUSINESS LOGIC ───────────────────────────────────────────


def stars(n: int) -> str:
    return "⭐" * max(1, min(5, n))


def calc_auto_discount(subtotal: int, total_packs: int) -> Tuple[int, int]:
    """Returns (total_after_discount, auto_discount_amount)."""
    if total_packs >= DISCOUNT_THRESHOLD:
        disc = round(subtotal * DISCOUNT_PCT / 100)
        return subtotal - disc, disc
    return subtotal, 0


def load_coupons() -> Dict[str, Any]:
    ensure_data_files()
    db = load_json(COUPONS_FILE, {"codes": {}})
    if not isinstance(db, dict):
        return {"codes": {}}
    codes = db.get("codes")
    if not isinstance(codes, dict):
        return {"codes": {}}
    return db


def coupon_percent_value(code: str) -> Optional[int]:
    coupons = load_coupons().get("codes", {})
    if not code:
        return None
    cfg = coupons.get(code.strip().upper())
    if not cfg or not isinstance(cfg, dict):
        return None
    if cfg.get("type") != "percent":
        return None
    try:
        return int(float(cfg.get("value")))
    except Exception:
        return None


def apply_coupon(code: str, total: int) -> Tuple[int, int, Optional[str]]:
    """Returns (new_total, coupon_discount, normalized_code_if_valid)."""
    coupons = load_coupons().get("codes", {})
    if not code:
        return total, 0, None
    norm = code.strip().upper()
    cfg = coupons.get(norm)
    if not cfg or not isinstance(cfg, dict):
        return total, 0, None

    ctype = cfg.get("type")
    value = cfg.get("value")
    try:
        value_num = float(value)
    except Exception:
        return total, 0, None

    if ctype == "percent":
        disc = round(total * value_num / 100)
        return max(0, total - disc), disc, norm

    return total, 0, None


def cart_get(context: ContextTypes.DEFAULT_TYPE) -> Dict[str, int]:
    cart = context.user_data.get("cart")
    if isinstance(cart, dict):
        # sanitize ints
        out: Dict[str, int] = {}
        for k, v in cart.items():
            if k in PRODUCTS:
                try:
                    q = int(v)
                except Exception:
                    continue
                if q > 0:
                    out[k] = min(MAX_QTY, q)
        context.user_data["cart"] = out
        return out
    context.user_data["cart"] = {}
    return {}


def cart_add(context: ContextTypes.DEFAULT_TYPE, product_key: str, qty: int) -> None:
    cart = cart_get(context)
    qty = max(1, min(MAX_QTY, int(qty)))
    cart[product_key] = min(MAX_QTY, cart.get(product_key, 0) + qty)
    context.user_data["cart"] = cart


def cart_remove(context: ContextTypes.DEFAULT_TYPE, product_key: str) -> None:
    cart = cart_get(context)
    cart.pop(product_key, None)
    context.user_data["cart"] = cart


def cart_clear(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["cart"] = {}


@dataclass
class CartTotals:
    subtotal: int
    total: int
    total_pills: int
    total_packs: int
    auto_discount: int
    coupon_discount: int
    coupon_code: Optional[str]


def cart_calculate_totals(cart: Dict[str, int], coupon_code: Optional[str] = None) -> CartTotals:
    subtotal = 0
    total_pills = 0
    total_packs = 0

    for key, qty in cart.items():
        p = PRODUCTS[key]
        subtotal += int(p["base_price"]) * int(qty)
        total_pills += int(p["pills_per_pack"]) * int(qty)
        total_packs += int(qty)

    after_auto, auto_disc = calc_auto_discount(subtotal, total_packs)
    after_coupon, coupon_disc, valid_code = apply_coupon(coupon_code or "", after_auto)

    return CartTotals(
        subtotal=subtotal,
        total=after_coupon,
        total_pills=total_pills,
        total_packs=total_packs,
        auto_discount=auto_disc,
        coupon_discount=coupon_disc,
        coupon_code=valid_code,
    )


def cart_items_to_lines(cart: Dict[str, int]) -> List[str]:
    lines: List[str] = []
    for key, qty in cart.items():
        p = PRODUCTS[key]
        line_total = p["base_price"] * qty
        lines.append(
            f"✅ {p['emoji']} {p['name']} — {qty} חבילות — ₪{line_total}"
        )
    return lines


def items_compact_summary(cart: Dict[str, int]) -> str:
    parts: List[str] = []
    for key, qty in cart.items():
        p = PRODUCTS[key]
        parts.append(f"{p['emoji']} {p['name']} x{qty}")
    return " | ".join(parts)


# ─── KEYBOARDS ────────────────────────────────────────────────

def splash_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 כניסה לחנות", callback_data="store")],
        [InlineKeyboardButton("ℹ️ איך זה עובד?", callback_data="howitworks"),
         InlineKeyboardButton("⭐ ביקורות", callback_data="testimonials")],
        [InlineKeyboardButton("📞 דבר עם נציג", callback_data="contact")],
    ])


def main_menu_kb(context: Optional[ContextTypes.DEFAULT_TYPE] = None) -> InlineKeyboardMarkup:
    cart = {}
    if context is not None:
        cart = cart_get(context)
    cart_count = sum(cart.values()) if cart else 0
    cart_label = "🛒 סל הקניות שלי"
    if cart_count:
        cart_label += f" ({cart_count})"

    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💊 Kamagra Oral Jelly", callback_data="prod_kamagra")],
            [InlineKeyboardButton("🐎 Vidalista 40mg", callback_data="prod_vidalista")],
            [InlineKeyboardButton("💪 Bundle — Kamagra + Vidalista", callback_data="prod_bundle")],
            [InlineKeyboardButton(cart_label, callback_data="cart")],
            [InlineKeyboardButton("❓ שאלות", callback_data="faq"),
             InlineKeyboardButton("📞 צור קשר", callback_data="contact")],
        ]
    )


def back_to_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏪 חזרה לחנות", callback_data="menu")],
        [InlineKeyboardButton("🏠 חזרה לדף הראשי", callback_data="store")],
    ])


def product_kb(key: str, context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
    p = PRODUCTS[key]
    rows: List[List[InlineKeyboardButton]] = []
    rows.append([InlineKeyboardButton(f"🛒 הזמן עכשיו — ₪{p['base_price']}", callback_data=f"qty_{key}")])
    rows.append([InlineKeyboardButton("🛒 לסל הקניות שלי", callback_data="cart")])

    # Upsell
    if key in ("kamagra", "vidalista"):
        rows.append(
            [
                InlineKeyboardButton(
                    "💰 קנה את השניים יחד וחסוך! → חבילת הגבר ₪169",
                    callback_data="prod_bundle",
                )
            ]
        )

    rows.append([InlineKeyboardButton("🏪 חזרה לחנות", callback_data="menu")])
    return InlineKeyboardMarkup(rows)


def quantity_kb(key: str) -> InlineKeyboardMarkup:
    p = PRODUCTS[key]
    rows: List[List[InlineKeyboardButton]] = []
    for qty in range(1, MAX_QTY + 1):
        pills = p["pills_per_pack"] * qty
        line_total = p["base_price"] * qty
        label = f"{qty} חבילות — {pills} כדורים — ₪{line_total}"
        if qty == 1:
            label = f"חבילה אחת — {pills} כדורים — ₪{line_total}"
        rows.append([InlineKeyboardButton(label, callback_data=f"addcart_{key}_{qty}")])

    # Required: back to product on qty screen, plus back to menu
    rows.append([InlineKeyboardButton("◀️ חזרה למוצר", callback_data=f"prod_{key}")])
    rows.append([InlineKeyboardButton("🏪 חזרה לחנות", callback_data="menu")])
    return InlineKeyboardMarkup(rows)


def cart_kb(context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
    cart = cart_get(context)
    rows: List[List[InlineKeyboardButton]] = []

    if cart:
        rows.append([InlineKeyboardButton("💳 לתשלום", callback_data="checkout")])

    rows.append([InlineKeyboardButton("🏠 חזרה לחנות", callback_data="menu")])
    return InlineKeyboardMarkup(rows)


DELIVERY_COST = 30

def delivery_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚚 משלוח עד הבית (+₪30)", callback_data="delivery_ship")],
        [InlineKeyboardButton("🏪 איסוף עצמי — בחינם", callback_data="delivery_pickup")],
        [InlineKeyboardButton("✖️ ביטול", callback_data="cancel_order")],
    ])


def cancel_order_kb() -> InlineKeyboardMarkup:
    # Every screen should have back-to-menu. We also give a cancel button.
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✖️ ביטול", callback_data="cancel_order")],
            [InlineKeyboardButton("🏪 חזרה לחנות", callback_data="menu")],
        ]
    )


def coupon_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("דלג", callback_data="coupon_skip")],
            [InlineKeyboardButton("✖️ ביטול", callback_data="cancel_order")],
            [InlineKeyboardButton("🏪 חזרה לחנות", callback_data="menu")],
        ]
    )


PAYMENT_ICONS = {"מזומן": "💵", "ביט": "📲", "פייבוקס": "💸", "העברה בנקאית": "🏦"}

def payment_kb() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(f"{PAYMENT_ICONS.get(opt,'💳')} {opt}", callback_data=f"pay_{opt}")] for opt in PAYMENT_OPTIONS]
    rows.append([InlineKeyboardButton("✖️ ביטול", callback_data="cancel_order")])
    return InlineKeyboardMarkup(rows)


def proof_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✖️ ביטול", callback_data="cancel_order")],
            [InlineKeyboardButton("🏪 חזרה לחנות", callback_data="menu")],
        ]
    )


def review_kb(order_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("⭐", callback_data=f"review_{order_id}_1"),
                InlineKeyboardButton("⭐⭐", callback_data=f"review_{order_id}_2"),
                InlineKeyboardButton("⭐⭐⭐", callback_data=f"review_{order_id}_3"),
                InlineKeyboardButton("⭐⭐⭐⭐", callback_data=f"review_{order_id}_4"),
                InlineKeyboardButton("⭐⭐⭐⭐⭐", callback_data=f"review_{order_id}_5"),
            ],
            [InlineKeyboardButton("אולי אחר כך", callback_data=f"review_skip_{order_id}")],
            [InlineKeyboardButton("🏪 חזרה לחנות", callback_data="menu")],
        ]
    )


# ─── RENDER HELPERS (required) ────────────────────────────────


async def render_text_from_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    parse_mode: Optional[str] = None,
) -> None:
    query = update.callback_query
    try:
        await query.edit_message_text(text=text, parse_mode=parse_mode, reply_markup=reply_markup)
        return
    except BadRequest:
        pass
    except Exception:
        pass

    try:
        await query.message.delete()
    except Exception:
        pass

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        parse_mode=parse_mode,
        reply_markup=reply_markup,
    )


async def render_photo_from_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    photo_path: str,
    caption: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    parse_mode: Optional[str] = None,
) -> None:
    query = update.callback_query
    try:
        await query.message.delete()
    except Exception:
        pass

    with open(photo_path, "rb") as img_file:
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=img_file,
            caption=caption,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )


# ─── REMINDERS ────────────────────────────────────────────────


def cancel_reminder(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    if not context.job_queue:
        return
    for job in context.job_queue.get_jobs_by_name(f"order_reminder_{user_id}"):
        job.schedule_removal()


async def reminder_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    data = job.data or {}
    user_id = data.get("user_id")
    hint = data.get("hint") or "העגלה שלך"

    if not user_id:
        return

    text = (
        "היי 👋\n\n"
        f"ראיתי שהוספת פריטים ל{hint} ולא סיימת הזמנה.\n"
        "אם תרצה, פשוט לחץ /start ונמשיך משם."
    )
    try:
        await context.bot.send_message(chat_id=user_id, text=text)
    except Exception as e:
        logger.warning("Failed sending reminder to %s: %s", user_id, e)


def schedule_cart_reminder(context: ContextTypes.DEFAULT_TYPE, user_id: int, cart: Dict[str, int]) -> None:
    cancel_reminder(context, user_id)
    if not context.job_queue:
        return

    hint = "עגלה"
    # use first product name as a nicer hint
    if cart:
        first_key = next(iter(cart.keys()))
        hint = f"עגלה ({PRODUCTS[first_key]['name']})"

    context.job_queue.run_once(
        reminder_callback,
        when=REMINDER_DELAY_SECONDS,
        name=f"order_reminder_{user_id}",
        data={"user_id": user_id, "hint": hint},
    )


# ─── BOT COMMANDS ─────────────────────────────────────────────


async def post_init(app: Application) -> None:
    ensure_data_files()
    commands = [
        BotCommand("start", "פתיחת התפריט הראשי"),
        BotCommand("help", "עזרה"),
        BotCommand("faq", "שאלות נפוצות"),
        BotCommand("contact", "יצירת קשר עם נציג"),
        BotCommand("myorders", "ההזמנות האחרונות שלי"),
        BotCommand("orders", "אדמין: צפייה בהזמנות האחרונות"),
        BotCommand("stats", "אדמין: סטטיסטיקות"),
        BotCommand("broadcast", "אדמין: שליחה לכל המשתמשים"),
        BotCommand("statusupdate", "אדמין: עדכון סטטוס הזמנה"),
    ]
    await app.bot.set_my_commands(commands)


def _resolve_start_product(args: List[str]) -> Optional[str]:
    if not args:
        return None
    payload = args[0].lower().strip()
    for prefix in ("fb_", "ig_", "lp_", "ad_", "src_"):
        if payload.startswith(prefix):
            payload = payload[len(prefix):]
    payload = payload.replace("prod_", "")
    return payload if payload in PRODUCTS else None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    register_user(update.effective_user)

    # Keep cart; clear transient flow data
    cart = cart_get(context)
    context.user_data.clear()
    context.user_data["cart"] = cart

    product_key = _resolve_start_product(context.args or [])
    if product_key:
        p = PRODUCTS[product_key]
        caption = (
            f"{p['emoji']} *{p['name']}*\n\n"
            f"{p['desc']}\n\n"
            f"💊 חבילה אחת = *{p['pills_per_pack']} יחידות*\n"
            f"💰 מחיר: *₪{p['base_price']}*\n\n"
            f"🏷 *קונים {DISCOUNT_THRESHOLD}+ חבילות? {DISCOUNT_PCT}% הנחה!*"
        )
        img_path = p.get("image", "")
        if img_path and os.path.exists(img_path):
            with open(img_path, "rb") as img_file:
                await update.message.reply_photo(
                    photo=img_file,
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=product_kb(product_key, context),
                )
        else:
            await update.message.reply_text(
                caption,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=product_kb(product_key, context),
            )
        return

    await update.message.reply_text(
        build_splash_text(),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=splash_kb(),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    register_user(update.effective_user)
    await update.message.reply_text(
        "אפשר להשתמש ב- /start כדי לפתוח את התפריט, /faq לשאלות נפוצות, /contact ליצירת קשר, ו- /myorders לצפייה בהזמנות האחרונות שלך.",
        reply_markup=back_to_menu_kb(),
    )


async def faq_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    register_user(update.effective_user)
    stats = get_review_stats()
    rating_block = ""
    if stats["count"]:
        rounded = round(stats["avg"])
        rating_block = (
            f"\n\n⭐ דירוג לקוחות ממוצע: {stats['avg']} / 5 ({stats['count']} ביקורות) {stars(rounded)}"
        )

    text = (
        "❓ שאלות נפוצות\n\n"
        "מה יש בחנות?\n"
        "Kamagra Oral Jelly 100mg, Vidalista 40mg, וחבילת שילוב משתלמת.\n\n"
        "כמה יחידות יש במוצר?\n"
        "Kamagra: 7 יחידות | Vidalista: 10 כדורים | חבילת הגבר: 17 יחידות סה״כ.\n\n"
        "יש הנחה?\n"
        "כן — מ-3 חבילות ומעלה יש 10% הנחה אוטומטית.\n\n"
        "איך מזמינים?\n"
        "בוחרים מוצר → מוסיפים לעגלה → עוברים לקופה → משאירים פרטים → עוברים לנציג בוואטסאפ.\n\n"
        "יש משלוח?\n"
        f"כן — משלוח לבית +₪{DELIVERY_COST}, או איסוף עצמי בחינם.\n\n"
        "איך משלמים?\n"
        "מזומן, ביט, פייבוקס או העברה בנקאית."
        f"{rating_block}"
    )
    await update.message.reply_text(text, reply_markup=back_to_menu_kb())


async def contact_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    register_user(update.effective_user)
    text = (
        "📞 צור קשר\n\n"
        f"💬 טלגרם: @{SELLER_USERNAME}\n"
        f"📱 וואטסאפ: https://wa.me/{WHATSAPP_NUMBER}\n\n"
        "נציג יחזור אליך בהקדם."
    )
    await update.message.reply_text(text, reply_markup=back_to_menu_kb())


# ─── CALLBACK FLOWS ───────────────────────────────────────────


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    register_user(update.effective_user)
    query = update.callback_query
    await query.answer()
    await render_text_from_callback(
        update,
        context,
        STORE_TEXT,
        reply_markup=main_menu_kb(context),
        parse_mode=ParseMode.MARKDOWN,
    )


async def store_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    register_user(update.effective_user)
    query = update.callback_query
    await query.answer()
    await render_text_from_callback(
        update,
        context,
        STORE_TEXT,
        reply_markup=main_menu_kb(context),
        parse_mode=ParseMode.MARKDOWN,
    )


async def product_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    register_user(update.effective_user)
    query = update.callback_query
    await query.answer()

    key = query.data.replace("prod_", "")
    p = PRODUCTS[key]
    bundle_upsell = ""
    if key == "bundle":
        saved = PRODUCTS["kamagra"]["base_price"] + PRODUCTS["vidalista"]["base_price"] - p["base_price"]
        bundle_upsell = f"\n\n💰 *חוסכים ₪{saved} לעומת קנייה נפרדת!*"
    caption = (
        f"{p['emoji']} *{p['name']}*\n\n"
        f"{p['desc']}\n\n"
        f"📦 חבילה אחת = *{p['pills_per_pack']} יחידות*\n"
        f"💳 מחיר: *₪{p['base_price']}*"
        f"{bundle_upsell}\n\n"
        f"🏷 *3+ חבילות → {DISCOUNT_PCT}% הנחה!*"
    )

    img_path = p.get("image", "")
    if img_path and os.path.exists(img_path):
        await render_photo_from_callback(
            update,
            context,
            img_path,
            caption,
            reply_markup=product_kb(key, context),
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        await render_text_from_callback(
            update,
            context,
            caption,
            reply_markup=product_kb(key, context),
            parse_mode=ParseMode.MARKDOWN,
        )


async def qty_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    register_user(update.effective_user)
    query = update.callback_query
    await query.answer()

    key = query.data.replace("qty_", "")
    p = PRODUCTS[key]
    text = (
        f"📦 *בחר כמות להוספה לעגלה — {p['name']}*\n\n"
        f"💊 כל חבילה = {p['pills_per_pack']} יחידות\n"
        f"🏷 מ-{DISCOUNT_THRESHOLD} חבילות (סה\"כ בעגלה) — {DISCOUNT_PCT}% הנחה!\n\n"
        "בחר כמות:"
    )
    await render_text_from_callback(
        update,
        context,
        text,
        reply_markup=quantity_kb(key),
        parse_mode=ParseMode.MARKDOWN,
    )


async def add_to_cart_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    register_user(update.effective_user)
    query = update.callback_query
    await query.answer()

    _, key, qty_s = query.data.split("_", 2)
    qty = int(qty_s)
    cart_add(context, key, qty)
    cart = cart_get(context)

    schedule_cart_reminder(context, update.effective_user.id, cart)

    p = PRODUCTS[key]
    text = (
        "✅ נוסף לסל!\n\n"
        f"{p['emoji']} {p['name']} — {qty} חבילות\n\n"
        "מה תרצה לעשות עכשיו?"
    )

    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🛒 לסל הקניות", callback_data="cart")],
            [InlineKeyboardButton("🏠 חזרה לחנות", callback_data="menu")],
        ]
    )

    await render_text_from_callback(update, context, text, reply_markup=kb)


async def cart_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    register_user(update.effective_user)
    query = update.callback_query
    await query.answer()

    cart = cart_get(context)
    if not cart:
        text = (
            "🛒 *הסל שלך ריק*\n\n"
            "בחר מוצר מהחנות כדי להתחיל.\n\n"
            "💡 _חבילת הגבר — הכי משתלם!_"
        )
        await render_text_from_callback(update, context, text, reply_markup=back_to_menu_kb(), parse_mode=ParseMode.MARKDOWN)
        return

    totals = cart_calculate_totals(cart)
    lines = cart_items_to_lines(cart)

    upsell_hint = ""
    if totals.total_packs < 3 and "bundle" not in cart:
        upsell_hint = "\n\n💡 _קנה 3+ חבילות וחסוך 10%_"

    text = "🛒 *הסל שלך*\n\n" + "\n".join(lines)
    text += f"\n\n💰 סכום: *₪{totals.subtotal}*"
    if totals.auto_discount:
        text += f"\n🏷 הנחה: *-₪{totals.auto_discount}*"
    text += f"\n🚚 משלוח: *+{DELIVERY_COST}₪* / איסוף עצמי בחינם"
    total_with_delivery = totals.total + DELIVERY_COST
    text += f"\n\n💳 *סה\"כ עם משלוח: {total_with_delivery}₪*"
    text += upsell_hint

    await render_text_from_callback(
        update,
        context,
        text,
        reply_markup=cart_kb(context),
        parse_mode=ParseMode.MARKDOWN,
    )


async def remove_from_cart_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    register_user(update.effective_user)
    query = update.callback_query
    await query.answer()

    key = query.data.replace("rm_", "")
    cart_remove(context, key)
    cart = cart_get(context)

    if not cart:
        cancel_reminder(context, update.effective_user.id)
        await render_text_from_callback(
            update,
            context,
            "✅ הוסר. הסל שלך ריק עכשיו.",
            reply_markup=back_to_menu_kb(),
        )
        return

    schedule_cart_reminder(context, update.effective_user.id, cart)
    await cart_callback(update, context)


async def clear_cart_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    register_user(update.effective_user)
    query = update.callback_query
    await query.answer()

    cart_clear(context)
    cancel_reminder(context, update.effective_user.id)

    await render_text_from_callback(
        update,
        context,
        "✅ הסל רוקן. אפשר לחזור לבחור מוצרים.",
        reply_markup=back_to_menu_kb(),
    )


# ─── CHECKOUT / CONVERSATION HANDLER ─────────────────────────


async def checkout_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    register_user(update.effective_user)
    query = update.callback_query
    await query.answer()

    cart = cart_get(context)
    if not cart:
        await render_text_from_callback(update, context, "הסל שלך ריק — הוסף מוצרים כדי להמשיך.", reply_markup=back_to_menu_kb())
        return ConversationHandler.END

    cancel_reminder(context, update.effective_user.id)

    # Upsell: if only 1 pack total and no bundle, offer upgrade
    totals = cart_calculate_totals(cart)
    bundle_price = PRODUCTS["bundle"]["base_price"]
    if totals.total_packs == 1 and "bundle" not in cart:
        single_price = totals.subtotal
        saving = (PRODUCTS["kamagra"]["base_price"] + PRODUCTS["vidalista"]["base_price"]) - bundle_price
        upsell_text = (
            "💡 *רגע לפני שממשיכים...*\n\n"
            f"בחרת: {list(cart.keys())[0] and PRODUCTS[list(cart.keys())[0]]['emoji']} {PRODUCTS[list(cart.keys())[0]]['name']}\n"
            f"מחיר: *₪{single_price}*\n\n"
            "──────────────────\n"
            "👍 *חבילת הגבר* — Kamagra + Vidalista\n"
            f"₪{bundle_price} בלבד (חוסכ ₪{saving}!)\n\n"
            "משלוח ציוד להשוואה או להמשיך עם הבחירה הנוכחית:"
        )
        upsell_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💪 שדרג לחבילת הגבר — ₪{}".format(bundle_price), callback_data="upsell_bundle")],
            [InlineKeyboardButton("המשך עם הבחירה הנוכחית →", callback_data="checkout_confirm")],
        ])
        await render_text_from_callback(update, context, upsell_text, reply_markup=upsell_kb, parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END

    discount_line = f"\n🏷 חסכת: *-₪{totals.auto_discount}*" if totals.auto_discount else ""
    items_lines = "\n".join([f"  {PRODUCTS[k]['emoji']} {PRODUCTS[k]['name']} ×{q}" for k,q in cart.items()])
    summary = (
        "*סכום הזמנה*\n\n"
        f"{items_lines}\n\n"
        f"💳 סה\"כ מוצרים: *₪{totals.subtotal}*{discount_line}\n\n"
        "──────────────────\n"
        "✏️ *שלב 1/4* — מה השם המלא שלך?"
    )

    await render_text_from_callback(
        update,
        context,
        summary,
        reply_markup=cancel_order_kb(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["name"] = update.message.text.strip()
    await update.message.reply_text("🏙 *שלב 2/4* — באיזו עיר גרים?", reply_markup=cancel_order_kb(), parse_mode=ParseMode.MARKDOWN)
    return CITY


async def get_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["city"] = update.message.text.strip()
    await update.message.reply_text("📱 *שלב 3/4* — מספר טלפון לאישור ומעקב:", reply_markup=cancel_order_kb(), parse_mode=ParseMode.MARKDOWN)
    return PHONE


async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    phone = update.message.text.strip()
    clean = phone.replace("-", "").replace(" ", "").replace("+", "")
    if not clean.isdigit() or len(clean) < 9:
        await update.message.reply_text("❌ המספר לא נראה תקין. נסה שוב (לדוגמה: 0521234567)", reply_markup=cancel_order_kb())
        return PHONE
    context.user_data["phone"] = phone
    await update.message.reply_text(
        "🚚 *שלב 4/4* — איך תרצה לקבל את ההזמנה?",
        reply_markup=delivery_kb(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return DELIVERY


async def upsell_bundle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Replace cart with bundle and go to checkout."""
    query = update.callback_query
    await query.answer()
    cart_clear(context)
    cart_add(context, "bundle", 1)
    return await _do_checkout(update, context)


async def checkout_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Skip upsell and go straight to checkout."""
    return await _do_checkout(update, context)


async def _do_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    register_user(update.effective_user)
    query = update.callback_query
    if query:
        try:
            await query.answer()
        except Exception:
            pass
    cart = cart_get(context)
    cancel_reminder(context, update.effective_user.id)
    totals = cart_calculate_totals(cart)
    discount_line = f"\n🏷 חסכת: *-₪{totals.auto_discount}*" if totals.auto_discount else ""
    items_lines = "\n".join([f"  {PRODUCTS[k]['emoji']} {PRODUCTS[k]['name']} ×{q}" for k,q in cart.items()])
    summary = (
        "*סכום הזמנה*\n\n"
        f"{items_lines}\n\n"
        f"💳 סה\"כ: *₪{totals.subtotal}*{discount_line}\n\n"
        "──────────────────\n"
        "✏️ *שלב 1/4* — מה השם המלא שלך?"
    )
    await render_text_from_callback(
        update, context, summary,
        reply_markup=cancel_order_kb(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return NAME


async def delivery_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    choice = query.data  # "delivery_ship" or "delivery_pickup"

    if choice == "delivery_ship":
        context.user_data["delivery"] = "משלוח"
        context.user_data["delivery_fee"] = DELIVERY_COST
        label = f"🚚 משלוח עד הבית (+₪{DELIVERY_COST})"
    else:
        context.user_data["delivery"] = "איסוף עצמי"
        context.user_data["delivery_fee"] = 0
        label = "🏪 איסוף עצמי — חינם"

    await render_text_from_callback(
        update, context,
        f"✅ נבחר: *{label}*\n\n💳 בחר אמצעי תשלום:",
        reply_markup=payment_kb(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return PAYMENT


async def coupon_skip_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.pop("coupon_code", None)
    context.user_data.pop("coupon_discount", None)

    await render_text_from_callback(
        update,
        context,
        "המשך לתשלום 👇\n\n💳 איך תרצה לשלם?",
        reply_markup=payment_kb(),
    )
    return PAYMENT


async def get_coupon_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    code = (update.message.text or "").strip()
    if code.lower() in ("דלג", "skip", "no", "אין"):
        context.user_data.pop("coupon_code", None)
        context.user_data.pop("coupon_discount", None)
        await update.message.reply_text("ממשיכים ללא קוד.\n\n💳 איך תרצה לשלם?", reply_markup=payment_kb())
        return PAYMENT

    cart = cart_get(context)
    totals_before = cart_calculate_totals(cart)
    after, disc, valid = apply_coupon(code, totals_before.total)

    if valid:
        context.user_data["coupon_code"] = valid
        context.user_data["coupon_discount"] = disc
        pct = coupon_percent_value(valid) or ""
        await update.message.reply_text(
            f"✅ קוד {valid} הופעל — הנחה נוספת {pct}%!\n\n💳 איך תרצה לשלם?",
            reply_markup=payment_kb(),
        )
    else:
        context.user_data.pop("coupon_code", None)
        context.user_data.pop("coupon_discount", None)
        await update.message.reply_text(
            "❌ קוד לא תקין, ממשיכים ללא הנחה\n\n💳 איך תרצה לשלם?",
            reply_markup=payment_kb(),
        )
    return PAYMENT


def build_order_from_context(update: Update, context: ContextTypes.DEFAULT_TYPE, payment_method: str) -> Dict[str, Any]:
    cart = cart_get(context)
    coupon_code = context.user_data.get("coupon_code")
    totals = cart_calculate_totals(cart, coupon_code=coupon_code)

    delivery = context.user_data.get("delivery", "משלוח")
    delivery_fee = int(context.user_data.get("delivery_fee", DELIVERY_COST))
    grand_total = totals.total + delivery_fee

    items: List[Dict[str, Any]] = []
    for key, qty in cart.items():
        p = PRODUCTS[key]
        items.append({
            "product_key": key,
            "product_name": p["name"],
            "product_emoji": p["emoji"],
            "qty": qty,
            "unit_price": p["base_price"],
            "pills_per_pack": p["pills_per_pack"],
            "total_pills": p["pills_per_pack"] * qty,
            "line_total": p["base_price"] * qty,
        })

    order_id = next_order_id()
    order: Dict[str, Any] = {
        "order_id": order_id,
        "created_at": now_iso(),
        "status": "חדש",
        "customer": {
            "telegram_id": update.effective_user.id,
            "username": update.effective_user.username,
            "first_name": update.effective_user.first_name,
            "name": context.user_data.get("name"),
            "city": context.user_data.get("city"),
            "phone": context.user_data.get("phone"),
        },
        "items": items,
        "total_packs": totals.total_packs,
        "total_pills": totals.total_pills,
        "subtotal": totals.subtotal,
        "auto_discount": totals.auto_discount,
        "coupon_code": totals.coupon_code,
        "coupon_discount": totals.coupon_discount,
        "delivery": delivery,
        "delivery_fee": delivery_fee,
        "total": grand_total,
        "payment_method": payment_method,
    }

    if items:
        order["product_key"] = items[0]["product_key"]
        order["product_name"] = items[0]["product_name"]
        order["product_emoji"] = items[0]["product_emoji"]
        order["qty"] = items[0]["qty"]

    return order


def order_user_summary(order: Dict[str, Any]) -> str:
    items_lines = []
    for it in order.get("items", []):
        items_lines.append(f"  {it['product_emoji']} {it['product_name']} ×{it['qty']}")

    cust = order["customer"]
    lines = [
        "─────────────────────",
        "✅ *הזמנה התקבלה!*",
        "─────────────────────",
        "",
        f"🆔  *{order['order_id']}*",
        "",
        "🛎️  *הזמנתך:*"
    ] + items_lines + [
        "",
        f"💳  לתשלום: *₪{order['total']}*",
    ]

    if order.get("auto_discount"):
        lines.append(f"🏷  חסכת: ₪{order['auto_discount']}")

    delivery = order.get("delivery", "משלוח")
    delivery_fee = order.get("delivery_fee", DELIVERY_COST)
    if delivery_fee:
        lines.append(f"📦  משלוח: +₪{delivery_fee}")
    else:
        lines.append("🛋️  איסוף עצמי (חינם)")

    lines += [
        "",
        "─────────────────────",
        f"👤  {cust.get('name')}",
        f"📍  {cust.get('city')}",
        f"📱  {cust.get('phone')}",
        f"💴  {order['payment_method']}",
        "─────────────────────",
        "",
        "🕒  *מה קורה עכשיו?*",
        "1️⃣  נציג צור קשר אליך לאישור הזמנה",
        "2️⃣  נארז ושלח בדיסקרטיות",
        "3️⃣  תקבל סווס מספר מעקב",
        "",
        "תודה 🙏",
    ]
    return "\n".join(lines)


def order_seller_summary(order: Dict[str, Any]) -> str:
    cust = order["customer"]
    lines = [
        "🔔 הזמנה חדשה!",
        "",
        f"🆔 {order['order_id']}",
        "📦 פריטים:",
    ]
    for it in order.get("items", []):
        lines.append(f"- {it['product_emoji']} {it['product_name']} x{it['qty']} (₪{it['line_total']})")

    lines.append("")
    lines.append(f"💰 סה\"כ: ₪{order['total']}")
    if order.get("auto_discount"):
        lines.append(f"🏷 הנחת כמות: ₪{order['auto_discount']}")
    if order.get("coupon_discount"):
        lines.append(f"🎟 קופון {order.get('coupon_code')}: ₪{order['coupon_discount']}")

    lines.append(f"📦 איסוף/משלוח: {order.get('delivery', 'משלוח')} (+₪{order.get('delivery_fee', 0)})")
    lines.append(f"👤 {cust.get('name')}")
    lines.append(f"🏙 {cust.get('city')}")
    lines.append(f"📱 {cust.get('phone')}")
    lines.append(f"💳 {order.get('payment_method')}")
    lines.append(f"🆔 Telegram: {cust.get('telegram_id')}")
    return "\n".join(lines)


async def finalize_order(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    payment_method: str,
    proof: Optional[Dict[str, str]] = None,
) -> None:
    order = build_order_from_context(update, context, payment_method=payment_method)
    if proof:
        order["payment_proof"] = proof

    save_order(order)

    # Build WhatsApp URL
    wa_msg = (
        f"שלום, ביצעתי הזמנה {order['order_id']}.\n"
        f"פריטים: {items_compact_summary(cart_get(context))}\n"
        f"שם: {order['customer']['name']} | טל: {order['customer']['phone']} | עיר: {order['customer']['city']} | תשלום: {payment_method}"
    )
    wa_url = f"https://wa.me/{WHATSAPP_NUMBER}?text={urllib.parse.quote(wa_msg)}"

    # Single message — summary + WA + review in one
    summary_text = order_user_summary(order)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 סיום הזמנה עם נציג בוואטסאפ", url=wa_url)],
        [InlineKeyboardButton("← חזרה לחנות", callback_data="menu")],
    ])

    await context.bot.send_message(
        chat_id=update.effective_user.id,
        text=summary_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb,
    )

    # Seller notification
    seller_text = order_seller_summary(order)
    await context.bot.send_message(chat_id=SELLER_CHAT_ID, text=seller_text)

    # Forward proof to seller
    if proof and proof.get("type") and proof.get("file_id"):
        caption = f"🧾 הוכחת תשלום עבור {order['order_id']}"
        try:
            if proof["type"] == "photo":
                await context.bot.send_photo(chat_id=SELLER_CHAT_ID, photo=proof["file_id"], caption=caption)
            else:
                await context.bot.send_document(chat_id=SELLER_CHAT_ID, document=proof["file_id"], caption=caption)
        except Exception as e:
            logger.warning("Failed sending proof to seller for %s: %s", order["order_id"], e)

    # cleanup
    cart_clear(context)
    for k in ("name", "city", "phone", "coupon_code", "coupon_discount", "payment_method", "delivery", "delivery_fee"):
        context.user_data.pop(k, None)


async def payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    method = query.data.replace("pay_", "")

    # Store for proof step
    context.user_data["payment_method"] = method

    if method == "מזומן":
        await render_text_from_callback(
            update,
            context,
            "✅ קיבלתי! תשלום: 💵 מזומן. מייצר הזמנה...",
            reply_markup=back_to_menu_kb(),
        )
        await finalize_order(update, context, payment_method=method, proof=None)
        return ConversationHandler.END

    text = (
        "מעולה.\n\n"
        f"💳 תשלום: *{method}*\n\n"
        "שלח תמונה של אישור התשלום (צילום מסך מהאפליקציה) ונסגור."
    )
    await render_text_from_callback(
        update,
        context,
        text,
        reply_markup=proof_kb(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return PROOF


def extract_proof_from_message(update: Update) -> Optional[Dict[str, str]]:
    msg = update.message
    if not msg:
        return None

    if msg.photo:
        file_id = msg.photo[-1].file_id
        return {"type": "photo", "file_id": file_id}

    if msg.document:
        # allow image-like documents
        mime = (msg.document.mime_type or "").lower()
        if mime.startswith("image/") or (msg.document.file_name or "").lower().endswith(
            (".png", ".jpg", ".jpeg", ".webp")
        ):
            return {"type": "document", "file_id": msg.document.file_id}

    return None


async def proof_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    proof = extract_proof_from_message(update)
    if not proof:
        await update.message.reply_text(
            "לא קיבלתי תמונה 🤔\nשלח צילום מסך של האישור (ביט/פייבוקס/העברה) ונסגור.",
            reply_markup=proof_kb(),
        )
        return PROOF

    method = context.user_data.get("payment_method") or ""
    await update.message.reply_text("✅ קיבלתי! מייצר הזמנה...", reply_markup=back_to_menu_kb())

    await finalize_order(update, context, payment_method=method, proof=proof)
    return ConversationHandler.END


async def cancel_order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    cancel_reminder(context, update.effective_user.id)

    # Do not clear cart automatically on cancel; user can continue shopping
    for k in ("name", "city", "phone", "coupon_code", "coupon_discount", "payment_method", "delivery", "delivery_fee"):
        context.user_data.pop(k, None)

    await render_text_from_callback(
        update,
        context,
        "✅ ההזמנה בוטלה. תמיד אפשר לחזור ולהזמין.",
        reply_markup=main_menu_kb(context),
    )
    return ConversationHandler.END


# ─── REVIEWS ─────────────────────────────────────────────────


async def review_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    _, order_id, rating = query.data.split("_")
    rating_i = int(rating)

    review = {
        "order_id": order_id,
        "rating": rating_i,
        "user_id": update.effective_user.id,
        "username": update.effective_user.username,
        "created_at": now_iso(),
    }
    save_review(review)

    await render_text_from_callback(
        update,
        context,
        f"תודה! קיבלנו דירוג של {stars(rating_i)} עבור ההזמנה {order_id} 💚",
        reply_markup=back_to_menu_kb(),
    )

    await context.bot.send_message(
        SELLER_CHAT_ID,
        f"⭐ ביקורת חדשה\n\nהזמנה: {order_id}\nדירוג: {stars(rating_i)} ({rating_i}/5)",
    )


async def review_skip_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    order_id = query.data.replace("review_skip_", "")
    await render_text_from_callback(
        update,
        context,
        f"סבבה — אפשר תמיד לכתוב לנו אחר כך. ההזמנה שלך: {order_id}",
        reply_markup=back_to_menu_kb(),
    )


# ─── FAQ / CONTACT CALLBACKS (inline) ─────────────────────────


async def howitworks_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    text = (
        "ℹ️ *איך זה עובד?*\n\n"
        "1️⃣ *בוחרים מוצר* — בוחרים את המוצר מהתפריט ומוסיפים לעגלה\n\n"
        "2️⃣ *משאירים פרטים* — שם, טלפון ואמצעי תשלום\n\n"
        "3️⃣ *נציג חוזר אליכם* — סוגרים תשלום ומשלוח\n\n"
        "📦 *משלוח דיסקרטי* — אריזה רגילה ללא שם המוצר מבחוץ\n\n"
        "⏱ *תוך 1-3 ימי עסקים* — מההזמנה ועד הדלת"
    )
    await render_text_from_callback(update, context, text, reply_markup=back_to_menu_kb(), parse_mode=ParseMode.MARKDOWN)


async def testimonials_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    stats = get_review_stats()
    rating_block = ""
    if stats["count"]:
        rating_block = f"\n\n⭐ דירוג ממוצע: {stats['avg']}/5 ({stats['count']} ביקורות)"

    text = (
        "⭐ *מה הלקוחות אומרים*\n\n"
        'ד. מתל אביב: \"Kamagra עובד מהר. תוך 15 דקות הרגשתי שינוי. ממליץ.\"\n\n'
        'א. מחיפה: \"Vidalista — 36 שעות זה לא בדיחה. מוצר אמיתי.\"\n\n'
        'מ. מירושלים: \"\u05d4זמנתי את החבילה. המחיר שווה והכל הגיע דיסקרטי.\"\n\n'
        'ר. מבאר שבע: \"\u05e7ניתי פעם שנייה. שירות אדיב, משלוח מהיר.\"'
        f"{rating_block}"
    )
    await render_text_from_callback(update, context, text, reply_markup=back_to_menu_kb(), parse_mode=ParseMode.MARKDOWN)


async def faq_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    stats = get_review_stats()
    rating_line = ""
    if stats["count"]:
        rating_line = f"\n\n⭐ דירוג לקוחות ממוצע: {stats['avg']} / 5 ({stats['count']} ביקורות)"

    text = (
        "❓ *שאלות נפוצות*\n\n"
        "*מה יש בחנות?*\n"
        "Kamagra Oral Jelly 100mg, Vidalista 40mg, וחבילת שילוב משתלמת.\n\n"
        "*כמה יחידות יש במוצר?*\n"
        "Kamagra: 7 יחידות | Vidalista: 10 כדורים | חבילת הגבר: 17 יחידות סה״כ.\n\n"
        "*יש הנחה?*\n"
        "כן — מ-3 חבילות ומעלה יש 10% הנחה אוטומטית.\n\n"
        "*איך מזמינים?*\n"
        "בוחרים מוצר → מוסיפים לעגלה → קופה → נציג בוואטסאפ.\n\n"
        "*איך משלמים?*\n"
        "מזומן, ביט, פייבוקס או העברה בנקאית."
        f"{rating_line}"
    )
    await render_text_from_callback(update, context, text, reply_markup=back_to_menu_kb(), parse_mode=ParseMode.MARKDOWN)


async def contact_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    text = (
        "📞 *צור קשר*\n\n"
        f"💬 טלגרם: @{SELLER_USERNAME}\n"
        f"📱 וואטסאפ: https://wa.me/{WHATSAPP_NUMBER}\n\n"
        "נציג יחזור אליך בהקדם."
    )
    await render_text_from_callback(update, context, text, reply_markup=back_to_menu_kb(), parse_mode=ParseMode.MARKDOWN)


# ─── USER COMMANDS ────────────────────────────────────────────


async def myorders_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    register_user(update.effective_user)
    uid = update.effective_user.id
    orders = [o for o in get_orders() if o.get("customer", {}).get("telegram_id") == uid]

    if not orders:
        await update.message.reply_text("אין לך עדיין הזמנות במערכת.", reply_markup=back_to_menu_kb())
        return

    last = list(reversed(orders[-5:]))
    lines: List[str] = ["📦 *5 ההזמנות האחרונות שלך:*\n"]

    for o in last:
        created = o.get("created_at", "")
        status = o.get("status", "חדש")
        total = o.get("total", 0)
        # items summary
        it_s = []
        for it in o.get("items", []):
            it_s.append(f"{it.get('product_emoji', '')}{it.get('product_name', '')} x{it.get('qty', 0)}")
        if not it_s and o.get("product_name"):
            it_s.append(f"{o.get('product_emoji', '')}{o.get('product_name')} x{o.get('qty', 0)}")
        lines.append(
            f"🆔 {o.get('order_id')} | ₪{total} | {status}\n"
            f"🗓 {created}\n"
            f"📦 {' | '.join(it_s)}\n"
        )

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN, reply_markup=back_to_menu_kb())


# ─── ADMIN COMMANDS ───────────────────────────────────────────


async def orders_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        return

    orders = get_orders()
    if not orders:
        await update.message.reply_text("אין עדיין הזמנות.")
        return

    lines = ["📦 10 ההזמנות האחרונות:\n"]
    for order in reversed(orders[-10:]):
        status = order.get("status", "חדש")
        total = order.get("total", 0)
        cust_name = order.get("customer", {}).get("name") or "(ללא שם)"
        items = order.get("items")
        if isinstance(items, list) and items:
            brief = ", ".join(
                [f"{it.get('product_emoji', '')}{it.get('product_name', '')}x{it.get('qty', 0)}" for it in items]
            )
        else:
            brief = f"{order.get('product_emoji', '')} {order.get('product_name', '')} x{order.get('qty', '')}".strip()

        lines.append(f"{order['order_id']} | {cust_name} | {brief} | ₪{total} | {status}")

    await update.message.reply_text("\n".join(lines))


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        return

    orders = get_orders()
    total_orders = len(orders)
    total_revenue = sum(int(o.get("total", 0) or 0) for o in orders)

    today = datetime.now().date()
    orders_today = 0
    prod_qty: Dict[str, int] = {}

    for o in orders:
        created = o.get("created_at")
        try:
            dt = datetime.fromisoformat(created)
        except Exception:
            dt = None
        if dt and dt.date() == today:
            orders_today += 1

        items = o.get("items")
        if isinstance(items, list) and items:
            for it in items:
                k = it.get("product_key") or it.get("product_name")
                if not k:
                    continue
                prod_qty[k] = prod_qty.get(k, 0) + int(it.get("qty", 0) or 0)
        else:
            k = o.get("product_key") or o.get("product_name")
            if k:
                prod_qty[k] = prod_qty.get(k, 0) + int(o.get("qty", 0) or 0)

    top_key = max(prod_qty.items(), key=lambda x: x[1])[0] if prod_qty else "-"
    top_name = PRODUCTS.get(top_key, {}).get("name") if top_key in PRODUCTS else top_key
    avg_order_value = round(total_revenue / total_orders, 1) if total_orders else 0

    text = (
        "📊 *סטטיסטיקות*\n\n"
        f"📦 סה\"כ הזמנות: *{total_orders}*\n"
        f"💰 סה\"כ הכנסות: *₪{total_revenue}*\n"
        f"🗓 הזמנות היום: *{orders_today}*\n"
        f"🏆 מוצר מוביל: *{top_name}*\n"
        f"🧮 ממוצע להזמנה: *₪{avg_order_value}*"
    )

    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ─── BROADCAST (admin) ───────────────────────────────────────


async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    await update.message.reply_text(
        "שלח לי עכשיו את ההודעה שתרצה לשדר לכל המשתמשים.\nכדי לבטל: /cancelbroadcast"
    )
    return BROADCAST_TEXT


async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END

    text = update.message.text
    sent = 0
    failed = 0
    for user_id in get_all_user_ids():
        if user_id == SELLER_CHAT_ID:
            continue
        try:
            await context.bot.send_message(user_id, text)
            sent += 1
        except Exception as e:
            logger.warning("Broadcast failed to %s: %s", user_id, e)
            failed += 1

    await update.message.reply_text(f"✅ ברודקאסט נשלח. הצליח: {sent} | נכשל: {failed}")
    return ConversationHandler.END


async def cancel_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("בוטל.")
    return ConversationHandler.END


# ─── STATUS UPDATE (admin) ────────────────────────────────────


async def status_update_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    await update.message.reply_text(
        "שלח לי את מספר ההזמנה לעדכון (למשל VT-0001).\nכדי לבטל: /cancelstatus"
    )
    return STATUS_ORDER_ID


async def status_update_get_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    order_id = update.message.text.strip().upper()
    order = get_order(order_id)
    if not order:
        await update.message.reply_text("לא מצאתי את ההזמנה הזאת. נסה שוב או /cancelstatus")
        return STATUS_ORDER_ID

    context.user_data["status_order_id"] = order_id
    await update.message.reply_text(
        f"מה הסטטוס החדש עבור {order_id}?\nלמשל: 'ההזמנה נארזה' או 'השליח בדרך'."
    )
    return STATUS_TEXT


async def status_update_send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    order_id = context.user_data.get("status_order_id")
    status_text = update.message.text.strip()
    order = update_order_status(order_id, status_text)
    if not order:
        await update.message.reply_text("משהו השתבש. נסה שוב.")
        return ConversationHandler.END

    customer_id = order["customer"]["telegram_id"]
    message = (
        "📦 עדכון להזמנה שלך\n\n"
        f"מספר הזמנה: {order_id}\n"
        f"סטטוס חדש: {status_text}\n\n"
        "אם צריך, אפשר לענות כאן או לפנות לנציג."
    )
    try:
        await context.bot.send_message(customer_id, message)
        await update.message.reply_text(f"✅ נשלח עדכון ללקוח עבור {order_id}")
    except Exception as e:
        logger.warning("Failed sending status update for %s: %s", order_id, e)
        await update.message.reply_text(f"הסטטוס נשמר, אבל שליחת ההודעה נכשלה עבור {order_id}")

    context.user_data.pop("status_order_id", None)
    return ConversationHandler.END


async def cancel_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("status_order_id", None)
    await update.message.reply_text("בוטל.")
    return ConversationHandler.END


# ─── MAIN ─────────────────────────────────────────────────────


def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN environment variable is required")

    ensure_data_files()

    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    checkout_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(checkout_start, pattern=r"^checkout$"),
            CallbackQueryHandler(upsell_bundle_callback, pattern=r"^upsell_bundle$"),
            CallbackQueryHandler(checkout_confirm_callback, pattern=r"^checkout_confirm$"),
        ],
        states={
            # QTY state reserved (required by spec); not used because cart handles quantities
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_city)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            DELIVERY: [CallbackQueryHandler(delivery_callback, pattern=r"^delivery_")],
            PAYMENT: [CallbackQueryHandler(payment_callback, pattern=r"^pay_")],
            PROOF: [
                MessageHandler(
                    (filters.PHOTO | filters.Document.IMAGE) & ~filters.COMMAND,
                    proof_handler,
                ),
                MessageHandler(filters.Document.ALL & ~filters.COMMAND, proof_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND, proof_handler),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_order_callback, pattern=r"^cancel_order$"),
            CallbackQueryHandler(menu_callback, pattern=r"^menu$"),
            CommandHandler("start", start),
        ],
        allow_reentry=True,
    )

    broadcast_handler = ConversationHandler(
        entry_points=[CommandHandler("broadcast", broadcast_start)],
        states={
            BROADCAST_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_send)],
        },
        fallbacks=[CommandHandler("cancelbroadcast", cancel_broadcast)],
    )

    status_handler = ConversationHandler(
        entry_points=[CommandHandler("statusupdate", status_update_start)],
        states={
            STATUS_ORDER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, status_update_get_order)],
            STATUS_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, status_update_send)],
        },
        fallbacks=[CommandHandler("cancelstatus", cancel_status)],
    )

    app.add_handler(checkout_handler)
    app.add_handler(broadcast_handler)
    app.add_handler(status_handler)

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("faq", faq_command))
    app.add_handler(CommandHandler("contact", contact_command))
    app.add_handler(CommandHandler("myorders", myorders_command))

    # Admin commands
    app.add_handler(CommandHandler("orders", orders_command))
    app.add_handler(CommandHandler("stats", stats_command))

    # Callbacks
    app.add_handler(CallbackQueryHandler(menu_callback, pattern=r"^menu$"))
    app.add_handler(CallbackQueryHandler(store_callback, pattern=r"^store$"))
    app.add_handler(CallbackQueryHandler(product_callback, pattern=r"^prod_"))
    app.add_handler(CallbackQueryHandler(qty_callback, pattern=r"^qty_"))
    app.add_handler(CallbackQueryHandler(add_to_cart_callback, pattern=r"^addcart_"))
    app.add_handler(CallbackQueryHandler(cart_callback, pattern=r"^cart$"))
    app.add_handler(CallbackQueryHandler(remove_from_cart_callback, pattern=r"^rm_"))
    app.add_handler(CallbackQueryHandler(clear_cart_callback, pattern=r"^clearcart$"))

    app.add_handler(CallbackQueryHandler(faq_callback, pattern=r"^faq$"))
    app.add_handler(CallbackQueryHandler(contact_callback, pattern=r"^contact$"))
    app.add_handler(CallbackQueryHandler(howitworks_callback, pattern=r"^howitworks$"))
    app.add_handler(CallbackQueryHandler(testimonials_callback, pattern=r"^testimonials$"))

    app.add_handler(CallbackQueryHandler(review_callback, pattern=r"^review_[A-Z0-9-]+_[1-5]$"))
    app.add_handler(CallbackQueryHandler(review_skip_callback, pattern=r"^review_skip_"))

    print("🤖 DrViagra Shop Bot (upgraded) is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
