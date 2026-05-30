# VITAMAN / DrViagra Shop — Railway Stack

Unified marketing funnel: **landing page + Telegram bot** in one deploy.

## Stack
- `index.html` — high-conversion Hebrew landing (FB Pixel, sticky CTA, product deep links)
- `server.py` — aiohttp web on `PORT` (fixes Railway 502)
- `bot_new.py` — Telegram store bot (cart, checkout, admin, reminders)
- `start.sh` — runs web + bot together
- `config.py` — all secrets from environment

## Env vars (Railway)
| Var | Purpose |
|-----|---------|
| `BOT_TOKEN` | Telegram bot token |
| `FB_PIXEL_ID` | Meta Pixel |
| `WHATSAPP_NUMBER` | e.g. 972523288147 |
| `SELLER_CHAT_ID` | Admin Telegram ID |
| `TELEGRAM_BOT_USERNAME` | e.g. DrViagrashop_Bot |
| `DATA_DIR` | `/data` (persistent volume) |
| `LANDING_PAGE_URL` | Public URL for OG tags |

## Local dev
```bash
pip install -r requirements.txt
export BOT_TOKEN=... PORT=8080
bash start.sh
```

## Deploy
```bash
railway link  # project vitaman
railway up --detach
curl -fsS https://vitaman-production.up.railway.app/health
```

## Marketing deep links
Landing → `t.me/Bot?start=fb_kamagra` opens product directly in bot.
