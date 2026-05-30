# Vitaman Project Map

## What this project is
Vitaman is a Telegram-first sales funnel. The public page gets traffic from ads/social, then pushes buyers into the Telegram bot where they choose products, build a cart, and leave order details for human closing.

## Runtime components

```text
Facebook / direct traffic
        ↓
Railway public URL
        ↓
server.py (aiohttp)
   ├─ GET /           → index.html landing
   ├─ GET /health     → operational status
   └─ POST /telegram/webhook → Telegram updates
        ↓
bot_new.py
   ├─ customer catalog/cart/checkout
   ├─ admin notifications and commands
   ├─ JSON persistence under DATA_DIR
   └─ reminder jobs via python-telegram-bot JobQueue
```

## Data files
Created automatically by `ensure_data_files()` in `bot_new.py`:

| File | Meaning |
|---|---|
| `users.json` | Telegram user IDs that interacted with the bot |
| `orders.json` | Orders and statuses |
| `reviews.json` | Customer review ratings |
| `counters.json` | Order sequence counter for `VT-xxxx` IDs |
| `coupons.json` | Coupon codes and discount rules |

On Railway these live under `/data` if a volume is mounted/configured. Locally they live under `./data` unless `DATA_DIR` is set.

## Customer bot flow

1. `/start` or landing deep link.
2. Splash screen.
3. Store menu.
4. Product page.
5. Quantity selection / add to cart.
6. Cart summary.
7. Checkout details:
   - name
   - city
   - phone
   - delivery method
   - coupon
   - payment method
   - optional proof screenshot for non-cash methods
8. Customer gets order summary.
9. Seller/admin gets full order notification.
10. Customer may leave a review.

## Admin commands

| Command | Purpose |
|---|---|
| `/orders` | Show recent orders |
| `/stats` | Sales/order statistics |
| `/broadcast` | Send message to all known bot users |
| `/statusupdate` | Update a customer about an order status |

Admin access is controlled by `SELLER_CHAT_ID`.

## Marketing links

The landing uses Telegram deep links like:

```text
https://t.me/DrViagrashop_Bot?start=fb_kamagra
https://t.me/DrViagrashop_Bot?start=fb_vidalista
https://t.me/DrViagrashop_Bot?start=fb_bundle
```

`bot_new.py` resolves these into the matching product page.

## Legacy files

| File | Status |
|---|---|
| `bot_new.py` | Current production bot |
| `server.py` | Current production server |
| `bot.py` | Legacy, keep only as reference |
| `bot_new_backup.py` | Legacy backup, not used by Railway |
| `BOT_SETUP.md`, `TELEGRAM_STORE.md`, `FACEBOOK_ADS.md`, `BRAND.md` | Older planning docs; updated but not runtime |
