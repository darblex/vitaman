# Vitaman / DrViagra Shop

Production funnel for Telegram-first sales: **landing page + Telegram store bot + admin flow** in one Railway service.

- Production URL: https://vitaman-production.up.railway.app
- Telegram bot: https://t.me/DrViagrashop_Bot
- Railway project/service: `vitaman`
- GitHub repo: `darblex/vitaman`

## Current architecture

| File | Purpose |
|---|---|
| `server.py` | `aiohttp` web server: landing page, `/health`, Telegram webhook endpoint |
| `bot_new.py` | Main Telegram bot: catalog, cart, checkout, admin commands, reminders, reviews |
| `index.html` | Hebrew landing page rendered with env placeholders |
| `config.py` | Runtime configuration from environment variables only |
| `start.sh` | Railway entrypoint; starts the unified server |
| `railway.json` | Railway Dockerfile deployment config |
| `qa_full.py` | Local project sanity/QA checks |
| `docs/OPERATIONS.md` | Runbook for daily ops, deploy, rollback, and bot commands |
| `docs/PROJECT_MAP.md` | Human-readable map of flows and data files |

## Main live flows

### Public landing
`GET /` renders `index.html` with env values:
- shop name
- Telegram deep links
- WhatsApp links
- Meta Pixel ID
- discount values

### Health
`GET /health` returns service status, bot mode, webhook path, data-dir readiness, and configured bot username.

### Telegram webhook
Railway runs webhook mode by default:
- `USE_POLLING=0`
- webhook endpoint: `WEBHOOK_PATH` (default `/telegram/webhook`)
- webhook base: `WEBHOOK_BASE` / `LANDING_PAGE_URL`

### Bot features
- `/start` landing inside Telegram
- product pages for Kamagra, Vidalista, bundle
- cart and quantity selection
- checkout: name → city → phone → delivery → coupon → payment/proof
- admin order notification
- `/orders`, `/stats`, `/broadcast`, `/statusupdate`
- `/myorders` for customers
- abandoned-cart reminder
- review collection

## Railway environment variables

Required:

| Var | Purpose |
|---|---|
| `BOT_TOKEN` | Telegram Bot API token |
| `SELLER_CHAT_ID` | Telegram chat ID for admin notifications |
| `TELEGRAM_BOT_USERNAME` | Public bot username, e.g. `DrViagrashop_Bot` |
| `WEBHOOK_BASE` | Public Railway URL, e.g. `https://vitaman-production.up.railway.app` |
| `WEBHOOK_SECRET` | Secret checked against Telegram webhook header |
| `DATA_DIR` | Persistent storage path; use `/data` on Railway |

Recommended:

| Var | Purpose |
|---|---|
| `SHOP_NAME` | Display name |
| `SELLER_USERNAME` | Telegram seller username without `@` |
| `WHATSAPP_NUMBER` | WhatsApp number in international format, no `+` |
| `FB_PIXEL_ID` | Meta Pixel ID |
| `LANDING_PAGE_URL` | Public URL for OG/canonical-style rendering |
| `DISCOUNT_THRESHOLD` | Packs required for automatic discount |
| `DISCOUNT_PCT` | Automatic discount percent |
| `MAX_QTY` | Max quantity per product |
| `REMINDER_DELAY_SECONDS` | Abandoned-cart reminder delay |

## Local development

```bash
cd /home/dark/.openclaw/workspace/projects/vitaman
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export BOT_TOKEN="..."
export USE_POLLING=1
export PORT=8080
bash start.sh
```

Open:
- http://127.0.0.1:8080
- http://127.0.0.1:8080/health

## QA

```bash
python3 -m compileall -q .
python3 qa_full.py
```

For production smoke:

```bash
curl -fsS https://vitaman-production.up.railway.app/health
curl -fsSI https://vitaman-production.up.railway.app/
railway logs --tail 100
```

## Deploy

```bash
railway link --project 673f0069-1ebb-42d0-b752-a2e11cd2e2e6 --environment production --service vitaman
railway up --detach
curl -fsS https://vitaman-production.up.railway.app/health
```

## Important notes

- `bot_new.py` is the current production bot. `bot.py` and `bot_new_backup.py` are legacy backups.
- Runtime JSON data is intentionally ignored by git under `data/`.
- Keep secrets in Railway env only; never commit `.env` or tokens.
- Product and marketing copy should stay careful: avoid medical promises, diagnosis/treatment claims, or guaranteed outcomes.
