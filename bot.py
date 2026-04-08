#!/usr/bin/env python3
"""
DrViagra Shop Telegram Bot v3
Adds: order IDs, admin broadcast, abandoned-order reminders,
review collection, status updates, order persistence, and real WhatsApp contact.
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
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

# ─── CONFIG ───────────────────────────────────────────────────
BOT_TOKEN = "8798178533:AAHE2xfhNScv9Mo1V4FVS1IAL746opPR858"
SELLER_CHAT_ID = 400023112
SELLER_USERNAME = "Darblex"
WHATSAPP_NUMBER = "972523288147"
REMINDER_DELAY_SECONDS = 3600
MAX_QTY = 5
DISCOUNT_THRESHOLD = 3
DISCOUNT_PCT = 10
# ──────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
IMGS_DIR = os.path.join(BASE_DIR, "images")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
ORDERS_FILE = os.path.join(DATA_DIR, "orders.json")
REVIEWS_FILE = os.path.join(DATA_DIR, "reviews.json")
COUNTERS_FILE = os.path.join(DATA_DIR, "counters.json")

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── PRODUCTS ─────────────────────────────────────────────────
PRODUCTS = {
    "kamagra": {
        "name": "Kamagra Oral Jelly 100mg",
        "emoji": "💊",
        "desc": "Sildenafil Oral Jelly 100mg — פעולה מהירה תוך 15 דקות.\n\nטעמים מגוונים, נוח לשימוש, תוצאות מוכחות.",
        "pills_per_pack": 7,
        "base_price": 89,
        "image": os.path.join(BASE_DIR, "images", "product1.jpg"),
    },
    "vidalista": {
        "name": "Vidalista 40mg (Tadalafil)",
        "emoji": "🐎",
        "desc": "Tadalafil 40mg — פעיל עד 36 שעות.\n\nהפתרון האמין לגבר שרוצה גמישות מלאה.",
        "pills_per_pack": 10,
        "base_price": 99,
        "image": os.path.join(BASE_DIR, "images", "product2.jpg"),
    },
    "bundle": {
        "name": "חבילת הגבר — Kamagra + Vidalista",
        "emoji": "💪",
        "desc": "Kamagra Jelly + Vidalista 40 יחד — ניסוי מלא לבחירה הנכונה.\n\nהחבילה המשתלמת ביותר.",
        "pills_per_pack": 17,
        "base_price": 169,
        "image": os.path.join(BASE_DIR, "images", "product1.jpg"),
    },
}

PAYMENT_OPTIONS = ["מזומן", "ביט", "פייבוקס", "העברה בנקאית"]

# ─── STATES ───────────────────────────────────────────────────
QTY, NAME, CITY, PHONE, PAYMENT = range(5)
BROADCAST_TEXT = 10
STATUS_ORDER_ID, STATUS_TEXT = range(20, 22)

# ─── TEXTS ────────────────────────────────────────────────────
WELCOME_TEXT = (
    "ברוך הבא ל־*DrViagra Shop* 💊\n"
    "המקום לאמצעים איכותיים לגבר.\n\n"
    "🏷 *הנחה 10% על 3 חבילות ומעלה!*\n\n"
    "בחר מוצר מהתפריט:"
)


def ensure_data_files() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    defaults = {
        USERS_FILE: {"users": []},
        ORDERS_FILE: {"orders": []},
        REVIEWS_FILE: {"reviews": []},
        COUNTERS_FILE: {"last_order_seq": 0},
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


def calc_price(base_price: int, qty: int):
    total = base_price * qty
    discount = 0
    if qty >= DISCOUNT_THRESHOLD:
        discount = round(total * DISCOUNT_PCT / 100)
        total -= discount
    return total, discount


def format_qty_line(base_price: int, pills_per_pack: int, qty: int) -> str:
    total_pills = pills_per_pack * qty
    total, discount = calc_price(base_price, qty)
    label = f"{qty} חבילות — {total_pills} כדורים — ₪{total}"
    if qty == 1:
        label = f"חבילה אחת — {total_pills} כדורים — ₪{total}"
    if discount > 0:
        label += f" (חסכת ₪{discount}!)"
    return label


def stars(n: int) -> str:
    return "⭐" * max(1, min(5, n))


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💊 Kamagra Oral Jelly 100mg — 7 ערכות — ₪89", callback_data="prod_kamagra")],
        [InlineKeyboardButton("🐎 Vidalista 40mg — 10 כדורים — ₪99", callback_data="prod_vidalista")],
        [InlineKeyboardButton("💪 חבילת הגבר — Kamagra + Vidalista — ₪169", callback_data="prod_bundle")],
        [InlineKeyboardButton("❓ שאלות נפוצות", callback_data="faq")],
        [InlineKeyboardButton("📞 דבר עם נציג", callback_data="contact")],
    ])


def product_kb(key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 בחר כמות והזמן", callback_data=f"qty_{key}")],
        [InlineKeyboardButton("🔙 חזרה לתפריט", callback_data="menu")],
    ])


def quantity_kb(key: str) -> InlineKeyboardMarkup:
    p = PRODUCTS[key]
    buttons = []
    for qty in range(1, MAX_QTY + 1):
        buttons.append([
            InlineKeyboardButton(
                format_qty_line(p["base_price"], p["pills_per_pack"], qty),
                callback_data=f"setqty_{key}_{qty}",
            )
        ])
    buttons.append([InlineKeyboardButton("🔙 חזרה למוצר", callback_data=f"prod_{key}")])
    return InlineKeyboardMarkup(buttons)


def back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 חזרה לתפריט", callback_data="menu")],
    ])


def payment_kb() -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(opt, callback_data=f"pay_{opt}")] for opt in PAYMENT_OPTIONS]
    buttons.append([InlineKeyboardButton("❌ ביטול", callback_data="cancel_order")])
    return InlineKeyboardMarkup(buttons)


def cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ ביטול הזמנה", callback_data="cancel_order")],
    ])


def review_kb(order_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⭐", callback_data=f"review_{order_id}_1"),
            InlineKeyboardButton("⭐⭐", callback_data=f"review_{order_id}_2"),
            InlineKeyboardButton("⭐⭐⭐", callback_data=f"review_{order_id}_3"),
            InlineKeyboardButton("⭐⭐⭐⭐", callback_data=f"review_{order_id}_4"),
            InlineKeyboardButton("⭐⭐⭐⭐⭐", callback_data=f"review_{order_id}_5"),
        ],
        [InlineKeyboardButton("אולי אחר כך", callback_data=f"review_skip_{order_id}")],
    ])


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


def cancel_reminder(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    if not context.job_queue:
        return
    for job in context.job_queue.get_jobs_by_name(f"order_reminder_{user_id}"):
        job.schedule_removal()


async def reminder_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    data = job.data or {}
    user_id = data.get("user_id")
    product_name = data.get("product_name", "המוצר שלך")
    qty = data.get("qty")
    if not user_id:
        return

    qty_line = f" ({qty} חבילות)" if qty else ""
    text = (
        "היי 👋\n\n"
        f"ראיתי שהתחלת הזמנה של {product_name}{qty_line} ולא סיימת.\n"
        "אם תרצה, פשוט לחץ /start ונמשיך משם."
    )
    try:
        await context.bot.send_message(chat_id=user_id, text=text)
    except Exception as e:
        logger.warning("Failed sending reminder to %s: %s", user_id, e)


async def post_init(app: Application) -> None:
    ensure_data_files()
    commands = [
        BotCommand("start", "פתיחת התפריט הראשי"),
        BotCommand("help", "עזרה ושאלות נפוצות"),
        BotCommand("faq", "שאלות נפוצות"),
        BotCommand("contact", "יצירת קשר עם נציג"),
        BotCommand("orders", "אדמין: צפייה בהזמנות האחרונות"),
        BotCommand("broadcast", "אדמין: שליחה לכל המשתמשים"),
        BotCommand("statusupdate", "אדמין: עדכון סטטוס הזמנה"),
    ]
    await app.bot.set_my_commands(commands)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update.effective_user)
    context.user_data.clear()
    await update.message.reply_text(WELCOME_TEXT, parse_mode="Markdown", reply_markup=main_menu_kb())


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update.effective_user)
    await update.message.reply_text(
        "אפשר להשתמש ב- /start כדי לפתוח את התפריט, /faq לשאלות נפוצות, ו- /contact ליצירת קשר.",
        reply_markup=back_kb(),
    )


async def faq_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update.effective_user)
    stats = get_review_stats()
    rating_block = ""
    if stats["count"]:
        rounded = round(stats["avg"])
        rating_block = f"\n\n⭐ דירוג לקוחות ממוצע: {stats['avg']} / 5 ({stats['count']} ביקורות) {stars(rounded)}"

    text = (
        "❓ שאלות נפוצות\n\n"
        "מה יש בחנות?\n"
        "Kamagra Oral Jelly 100mg, Vidalista 40mg, וחבילת שילוב משתלמת.\n\n"
        "כמה יחידות יש במוצר?\n"
        "Kamagra: 7 יחידות | Vidalista: 10 כדורים | חבילת הגבר: 17 יחידות סה״כ.\n\n"
        "יש הנחה?\n"
        "כן — מ-3 חבילות ומעלה יש 10% הנחה אוטומטית.\n\n"
        "איך מזמינים?\n"
        "בוחרים מוצר → בוחרים כמות → משאירים פרטים → עוברים לנציג בוואטסאפ.\n\n"
        "יש משלוח?\n"
        "כן, בתיאום מול הנציג.\n\n"
        "איך משלמים?\n"
        "מזומן, ביט, פייבוקס או העברה בנקאית."
        f"{rating_block}"
    )
    await update.message.reply_text(text, reply_markup=back_kb())


async def contact_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update.effective_user)
    text = (
        "📞 צור קשר\n\n"
        f"💬 טלגרם: @{SELLER_USERNAME}\n"
        f"📱 וואטסאפ: https://wa.me/{WHATSAPP_NUMBER}\n\n"
        "נציג יחזור אליך בהקדם."
    )
    await update.message.reply_text(text, reply_markup=back_kb())


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update.effective_user)
    query = update.callback_query
    await query.answer()
    await render_text_from_callback(update, context, WELCOME_TEXT, main_menu_kb(), "Markdown")


async def product_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update.effective_user)
    query = update.callback_query
    await query.answer()
    key = query.data.replace("prod_", "")
    p = PRODUCTS[key]
    caption = (
        f"{p['emoji']} *{p['name']}*\n\n"
        f"{p['desc']}\n\n"
        f"💊 חבילה אחת = *{p['pills_per_pack']} יחידות*\n"
        f"💰 מחיר: *₪{p['base_price']}*\n\n"
        f"🏷 *קונים 3+ חבילות? 10% הנחה!*"
    )
    img_path = p.get("image", "")
    if img_path and os.path.exists(img_path):
        await render_photo_from_callback(update, context, img_path, caption, product_kb(key), "Markdown")
    else:
        await render_text_from_callback(update, context, caption, product_kb(key), "Markdown")


async def qty_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update.effective_user)
    query = update.callback_query
    await query.answer()
    key = query.data.replace("qty_", "")
    p = PRODUCTS[key]
    text = (
        f"📦 *בחר כמות — {p['name']}*\n\n"
        f"💊 כל חבילה = {p['pills_per_pack']} יחידות\n"
        f"🏷 מ-{DISCOUNT_THRESHOLD} חבילות — {DISCOUNT_PCT}% הנחה!\n"
        "בחר את הכמות שמתאימה לך:"
    )
    await render_text_from_callback(update, context, text, quantity_kb(key), "Markdown")


async def order_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update.effective_user)
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")
    key = parts[1]
    qty = int(parts[2])
    p = PRODUCTS[key]
    total, discount = calc_price(p["base_price"], qty)
    total_pills = p["pills_per_pack"] * qty

    context.user_data["product"] = key
    context.user_data["qty"] = qty
    context.user_data["total"] = total
    context.user_data["total_pills"] = total_pills
    context.user_data["discount"] = discount

    cancel_reminder(context, update.effective_user.id)
    if context.job_queue:
        context.job_queue.run_once(
            reminder_callback,
            when=REMINDER_DELAY_SECONDS,
            name=f"order_reminder_{update.effective_user.id}",
            data={
                "user_id": update.effective_user.id,
                "product_name": p["name"],
                "qty": qty,
            },
        )

    summary = (
        "🛒 *סיכום הזמנה*\n\n"
        f"📦 {p['emoji']} {p['name']}\n"
        f"📦 כמות: *{qty}* חבילות — *{total_pills} כדורים*\n"
        f"💰 סה״כ: *₪{total}*"
    )
    if discount > 0:
        summary += f"\n🏷 חסכת: *₪{discount}*"
    summary += "\n\n✏️ מה השם המלא שלך?"

    await render_text_from_callback(update, context, summary, cancel_kb(), "Markdown")
    return NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text.strip()
    await update.message.reply_text("🏙 באיזו עיר אתה?", reply_markup=cancel_kb())
    return CITY


async def get_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["city"] = update.message.text.strip()
    await update.message.reply_text("📱 מה מספר הטלפון שלך?", reply_markup=cancel_kb())
    return PHONE


async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["phone"] = update.message.text.strip()
    await update.message.reply_text("💳 איך תרצה לשלם?", reply_markup=payment_kb())
    return PAYMENT


async def get_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    method = query.data.replace("pay_", "")
    ud = context.user_data
    p = PRODUCTS[ud["product"]]
    order_id = next_order_id()

    cancel_reminder(context, update.effective_user.id)

    order = {
        "order_id": order_id,
        "created_at": now_iso(),
        "status": "חדש",
        "customer": {
            "telegram_id": update.effective_user.id,
            "username": update.effective_user.username,
            "first_name": update.effective_user.first_name,
            "name": ud["name"],
            "city": ud["city"],
            "phone": ud["phone"],
        },
        "product_key": ud["product"],
        "product_name": p["name"],
        "product_emoji": p["emoji"],
        "qty": ud["qty"],
        "total_pills": ud["total_pills"],
        "total": ud["total"],
        "discount": ud.get("discount", 0),
        "payment_method": method,
    }
    save_order(order)

    summary = (
        "✅ ההזמנה נקלטה!\n\n"
        f"🆔 מספר הזמנה: {order_id}\n"
        f"📦 מוצר: {p['emoji']} {p['name']}\n"
        f"📦 כמות: {ud['qty']} חבילות — {ud['total_pills']} כדורים\n"
        f"💰 סה״כ: ₪{ud['total']}\n"
    )
    if ud.get("discount", 0) > 0:
        summary += f"🏷 הנחה: ₪{ud['discount']}\n"
    summary += (
        f"👤 שם: {ud['name']}\n"
        f"🏙 עיר: {ud['city']}\n"
        f"📱 טלפון: {ud['phone']}\n"
        f"💳 תשלום: {method}\n\n"
        "נציג יצור איתך קשר בקרוב לסגירת ההזמנה. תודה 🙏"
    )
    await query.edit_message_text(summary, reply_markup=back_kb())

    seller_msg = (
        "🔔 הזמנה חדשה!\n\n"
        f"🆔 {order_id}\n"
        f"📦 {p['emoji']} {p['name']}\n"
        f"📦 {ud['qty']} חבילות — {ud['total_pills']} כדורים\n"
        f"💰 ₪{ud['total']}"
    )
    if ud.get("discount", 0) > 0:
        seller_msg += f" (הנחה ₪{ud['discount']})"
    seller_msg += (
        f"\n👤 {ud['name']}\n"
        f"🏙 {ud['city']}\n"
        f"📱 {ud['phone']}\n"
        f"💳 {method}\n"
        f"🆔 Telegram: {update.effective_user.id}"
    )
    await context.bot.send_message(SELLER_CHAT_ID, seller_msg)

    # WhatsApp redirect to seller
    wa_msg = (
        f"שלום, הזמנתי {p['name']} x{ud['qty']} — הזמנה {order_id}.\n"
        f"שם: {ud['name']} | טל: {ud['phone']} | עיר: {ud['city']} | תשלום: {method}"
    )
    import urllib.parse
    wa_url = f"https://wa.me/{WHATSAPP_NUMBER}?text={urllib.parse.quote(wa_msg)}"
    await context.bot.send_message(
        chat_id=update.effective_user.id,
        text="📲 לחץ כאן כדי לעבור לנציג שירות בוואטסאפ לסיום ההזמנה:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 פתח וואטסאפ עם הנציג", url=wa_url)],
        ]),
    )

    await context.bot.send_message(
        chat_id=update.effective_user.id,
        text=(
            f"אם בא לך — אפשר לדרג עכשיו את חוויית ההזמנה עבור {order_id}.\n"
            "זה עוזר לנו לשפר 🙌"
        ),
        reply_markup=review_kb(order_id),
    )

    context.user_data.clear()
    return ConversationHandler.END


async def cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cancel_reminder(context, update.effective_user.id)
    context.user_data.clear()
    await render_text_from_callback(update, context, WELCOME_TEXT, main_menu_kb(), "Markdown")
    return ConversationHandler.END


async def review_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, order_id, rating = query.data.split("_")
    rating = int(rating)

    review = {
        "order_id": order_id,
        "rating": rating,
        "user_id": update.effective_user.id,
        "username": update.effective_user.username,
        "created_at": now_iso(),
    }
    save_review(review)

    await query.edit_message_text(
        f"תודה! קיבלנו דירוג של {stars(rating)} עבור ההזמנה {order_id} 💚"
    )
    await context.bot.send_message(
        SELLER_CHAT_ID,
        f"⭐ ביקורת חדשה\n\nהזמנה: {order_id}\nדירוג: {stars(rating)} ({rating}/5)",
    )


async def review_skip_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_id = query.data.replace("review_skip_", "")
    await query.edit_message_text(f"סבבה — אפשר תמיד לכתוב לנו אחר כך. ההזמנה שלך: {order_id}")


async def faq_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        "בוחרים מוצר → בוחרים כמות → משאירים פרטים → עוברים לנציג בוואטסאפ.\n\n"
        "*יש משלוח?*\n"
        "כן, בתיאום מול הנציג.\n\n"
        "*איך משלמים?*\n"
        "מזומן, ביט, פייבוקס או העברה בנקאית."
        f"{rating_line}"
    )
    await render_text_from_callback(update, context, text, back_kb(), "Markdown")


async def contact_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = (
        "📞 *צור קשר*\n\n"
        f"💬 טלגרם: @{SELLER_USERNAME}\n"
        f"📱 וואטסאפ: https://wa.me/{WHATSAPP_NUMBER}\n\n"
        "נציג יחזור אליך בהקדם."
    )
    await render_text_from_callback(update, context, text, back_kb(), "Markdown")


async def orders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    orders = get_orders()
    if not orders:
        await update.message.reply_text("אין עדיין הזמנות.")
        return

    lines = ["📦 10 ההזמנות האחרונות:\n"]
    for order in reversed(orders[-10:]):
        lines.append(
            f"{order['order_id']} | {order['customer']['name']} | {order['product_emoji']} {order['product_name']} | ₪{order['total']} | {order.get('status', 'חדש')}"
        )
    await update.message.reply_text("\n".join(lines))


async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    await update.message.reply_text(
        "שלח לי עכשיו את ההודעה שתרצה לשדר לכל המשתמשים.\nכדי לבטל: /cancelbroadcast"
    )
    return BROADCAST_TEXT


async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
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


async def cancel_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("בוטל.")
    return ConversationHandler.END


async def status_update_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    await update.message.reply_text(
        "שלח לי את מספר ההזמנה לעדכון (למשל VT-0001).\nכדי לבטל: /cancelstatus"
    )
    return STATUS_ORDER_ID


async def status_update_get_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
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


async def status_update_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
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


async def cancel_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("status_order_id", None)
    await update.message.reply_text("בוטל.")
    return ConversationHandler.END


def main():
    ensure_data_files()

    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    order_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(order_start, pattern=r"^setqty_")],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_city)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            PAYMENT: [CallbackQueryHandler(get_payment, pattern=r"^pay_")],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_order, pattern=r"^cancel_order$"),
            CallbackQueryHandler(menu_callback, pattern=r"^menu$"),
            CommandHandler("start", start),
        ],
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

    app.add_handler(order_handler)
    app.add_handler(broadcast_handler)
    app.add_handler(status_handler)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("faq", faq_command))
    app.add_handler(CommandHandler("contact", contact_command))
    app.add_handler(CommandHandler("orders", orders_command))

    app.add_handler(CallbackQueryHandler(menu_callback, pattern=r"^menu$"))
    app.add_handler(CallbackQueryHandler(product_callback, pattern=r"^prod_"))
    app.add_handler(CallbackQueryHandler(qty_callback, pattern=r"^qty_"))
    app.add_handler(CallbackQueryHandler(faq_callback, pattern=r"^faq$"))
    app.add_handler(CallbackQueryHandler(contact_callback, pattern=r"^contact$"))
    app.add_handler(CallbackQueryHandler(review_callback, pattern=r"^review_[A-Z0-9-]+_[1-5]$"))
    app.add_handler(CallbackQueryHandler(review_skip_callback, pattern=r"^review_skip_"))

    print("🤖 DrViagra Shop Bot v3 is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
