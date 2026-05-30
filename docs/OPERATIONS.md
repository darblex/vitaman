# Vitaman Operations Runbook

## Production

- Railway project: `vitaman`
- Railway service: `vitaman`
- Public URL: https://vitaman-production.up.railway.app
- Bot: https://t.me/DrViagrashop_Bot
- Entrypoint: `bash start.sh`
- Runtime: Dockerfile → Python 3.12 → `server.py`

## Fast status check

```bash
cd /home/dark/.openclaw/workspace/projects/vitaman
railway status
curl -fsS https://vitaman-production.up.railway.app/health
railway logs --tail 100
```

Healthy response should look like:

```json
{
  "ok": true,
  "service": "vitaman",
  "bot_mode": "webhook"
}
```

The response may include more fields over time.

## Deploy checklist

1. Inspect changes:
   ```bash
   git status --short
   git diff --check
   ```
2. Run local QA:
   ```bash
   python3 -m compileall -q .
   python3 qa_full.py
   ```
3. Commit and push:
   ```bash
   git add .
   git commit -m "..."
   git push origin master
   ```
4. Deploy:
   ```bash
   railway up --detach
   ```
5. Smoke:
   ```bash
   curl -fsS https://vitaman-production.up.railway.app/health
   curl -fsSI https://vitaman-production.up.railway.app/
   railway logs --tail 100
   ```

## Rollback

Use Railway dashboard or CLI deployment list:

```bash
railway deployment list
```

If the latest deploy fails badly, use Railway rollback/redeploy from the dashboard, or redeploy a known-good commit.

## Bot webhook notes

Production uses webhook mode:

```text
USE_POLLING=0
WEBHOOK_BASE=https://vitaman-production.up.railway.app
WEBHOOK_PATH=/telegram/webhook
WEBHOOK_SECRET=<secret>
```

Do not run polling locally with the production token while webhook is active unless you intentionally disable webhook or use a separate dev bot token.

## Common fixes

### 502 from Railway
- Check `railway logs --tail 200`.
- Confirm `PORT` is being used by `server.py`.
- Confirm `start.sh` runs `python server.py`.

### Telegram webhook forbidden
- Telegram sends `X-Telegram-Bot-Api-Secret-Token`.
- It must match `WEBHOOK_SECRET` in Railway.

### Orders disappear after redeploy
- Check that `DATA_DIR=/data`.
- Confirm Railway volume is mounted to `/data` if persistence is required.

### Bot not answering
- Check `/health` first.
- Check `railway logs --tail 200` for Telegram API errors.
- Verify `BOT_TOKEN` and webhook registration.

## Safety / copy

Keep public copy clean and restrained:
- no cure/treatment/diagnosis claims
- no guaranteed outcome promises
- no fake medical authority
- include “אין תחליף לייעוץ רפואי” style disclaimer where appropriate
