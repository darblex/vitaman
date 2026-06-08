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
| `SELLER_USERNAME` | Telegram username (e.g. lilnano0) |
| `SELLER_CHAT_ID` | Admin Telegram ID |
| `TELEGRAM_BOT_USERNAME` | e.g. DrViagrashop_Bot |
| `AUTO_POST_ENABLED` | `1` enables scheduled channel posts |
| `AUTO_POST_CHANNEL_ID` | Target channel id or `@channelusername` |
| `AUTO_POST_TIMES` | Comma-separated HH:MM list (e.g. `10:00,14:00,20:00`) |
| `AUTO_POST_TIMEZONE` | e.g. `Asia/Jerusalem` |
| `AUTO_REPORT_ENABLED` | `1` enables daily report |
| `AUTO_REPORT_CHAT_ID` | Admin chat id for reports |
| `AUTO_REPORT_TIME` | Daily HH:MM (e.g. `22:00`) |
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

## Sales/Marketing Ops (new)
- `MARKETING_PLAN_TELEGRAM.md` - practical growth execution plan
- `TELEGRAM_POSTS_READY_HE.md` - ready-to-publish Hebrew post bank
- `scripts/generate_campaign_links.py` - generate tracked Telegram deep links
- `automation.py` - scheduled posts + automatic daily sales report
- `marketing_posts.json` - editable post templates for automation
- `scripts/run_automation_once.py` - one-shot automation smoke test
