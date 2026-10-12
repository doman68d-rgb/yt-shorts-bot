# 🚂 Deploy Demo Bot on Railway (free tier)

This walks you through deploying a "demo bot" that anyone can interact with —
no install required.

## 🆓 Railway free tier

- $5 credit/month
- Roughly 500 hours of small-container runtime
- Enough for a demo bot you showcase on Product Hunt / HN

## 1. Prepare your code

Make sure these files are committed in your repo:
- `Dockerfile` (we already wrote it ✅)
- `docker-compose.yml`
- `entrypoint.sh`

## 2. Create Railway project

1. Sign up at https://railway.app/
2. Click **New Project** → **Deploy from Docker Image**
3. (Alternative) **Deploy from GitHub Repo** if you've already pushed to GitHub

## 3. Set environment variables

In Railway dashboard → **Variables**:

```
BOT_TOKEN=<your test bot's token>
OPENAI_API_KEY=<optional, your OpenAI key>
WHISPER_MODEL=base
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
LOG_FILE=/app/logs/bot.log
```

Get a **separate test bot** from @BotFather — don't reuse your main bot token.

## 4. Configure Dockerfile build

Railway will detect `Dockerfile` automatically. If it doesn't:
- Settings → Build → Set custom Dockerfile path: `./Dockerfile`

## 5. Set the healthcheck (optional but recommended)

Railway uses `HEALTHCHECK` from Dockerfile automatically.

## 6. Deploy

1. Click **Deploy**
2. Watch logs: they should show `🚀 Запускаю бота…` and `Run polling for bot @your_test_bot`
3. If you see errors: check Variables, then check logs for specific issue

## 7. Set up periodic restarts (optional)

For a demo bot, you may want a daily restart to clear memory and refresh
Whisper cache. Use Railway's **Cron** feature, or rely on Railway's
auto-restart on deploy.

## ⚠️ Costs

- Whisper uses CPU on free tier → slow but works
- If demo gets too popular, watch the credit — Railway will warn you
- 1 hour of Whisper base = ~100MB of model + ~200MB RAM

## 🚀 Alternative: Fly.io

Fly.io also has a generous free tier:
1. Install flyctl
2. `fly launch` (auto-detects Dockerfile)
3. `fly secrets set BOT_TOKEN=...`
4. `fly deploy`

## 🐳 Alternative: Local ngrok

If you don't want to deploy anywhere:
1. Run bot locally
2. Run ngrok to expose port to the internet (but bot doesn't use ports)
3. ... actually that doesn't help, ignore this 😅

Just use Railway or Fly.io.

---

## 🎯 Demo bot etiquette

When someone uses your demo bot:
- Don't store their videos longer than necessary
- Add a `/privacy` command that explains what data is kept
- Be ready for abusive users (rate-limit aggressively)
