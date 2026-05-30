# Bot Setup — DrViagra Shop / Vitaman

## Current production bot

- Bot username: `@DrViagrashop_Bot`
- Runtime file: `bot_new.py`
- Server/webhook file: `server.py`
- Production mode: webhook through Railway
- Admin chat is controlled by `SELLER_CHAT_ID`

## Bot commands

Customer:
- `/start` — opens the store
- `/faq` — FAQ
- `/contact` — seller contact
- `/myorders` — customer order history

Admin only:
- `/orders` — recent orders
- `/stats` — order/revenue stats
- `/broadcast` — broadcast to known users
- `/statusupdate` — send order status update

## Production webhook config

Railway env should include:

```text
BOT_TOKEN=<telegram token>
TELEGRAM_BOT_USERNAME=DrViagrashop_Bot
SELLER_CHAT_ID=400023112
USE_POLLING=0
WEBHOOK_BASE=https://vitaman-production.up.railway.app
WEBHOOK_PATH=/telegram/webhook
WEBHOOK_SECRET=<secret>
DATA_DIR=/data
```

`server.py` registers the webhook on startup and checks Telegram's secret-token header on incoming updates.

## Local dev

Use a separate dev token if possible. If using the production token, do not run polling at the same time as the production webhook.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export BOT_TOKEN=...
export USE_POLLING=1
export DATA_DIR=./data
bash start.sh
```

## Editing products

Products are defined in `PRODUCTS` inside `bot_new.py`:
- `kamagra`
- `vidalista`
- `bundle`

Each product has:
- `name`
- `emoji`
- `desc`
- `pills_per_pack`
- `base_price`
- `image`

Keep copy restrained: no guaranteed outcomes, no cure/treatment claims, and include advice to consult a medical professional where appropriate.
