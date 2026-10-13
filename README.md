# ✂️ NarezkaShorts

> **Telegram bot that turns long YouTube videos into viral Shorts — automatically.**

Powered by AI: it downloads the video, transcribes it with Whisper, picks the
best moments (via LLM or randomly), and sends you ready-to-upload vertical
clips (1080×1920). With real-time progress in the chat.

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Docker ready](https://img.shields.io/badge/docker-ready-blue.svg)](https://hub.docker.com/)
[![Telegram bot](https://img.shields.io/badge/telegram-bot-blue.svg)](https://core.telegram.org/bots)

---

## ✨ Features

| | |
|---|---|
| 📥 **Download** | YouTube + 1000+ platforms (via `yt-dlp`) |
| 🎧 **Transcribe** | `faster-whisper` with timestamps |
| 🧠 **Smart highlights** | LLM picks the most engaging moments from the transcript |
| 🎲 **Random strategy** | Fallback when no API key — random clips from the "middle" |
| 🔍 **Progress bar** | One message updates every ~1.5s — see exactly where the bot is |
| ⚙️ **In-chat settings** | Change clip count/length via `/clips N L` or inline buttons |
| ✂️ **Auto-edit** | Single ffmpeg pass: extract + center-crop to 9:16 + scale to 1080×1920 |
| 📤 **Send** | All clips as messages with captions (timing, strategy, size) |
| 🧹 **Auto-cleanup** | Temp files deleted after each run |
| 🐳 **Docker-ready** | One-command deploy on Railway, Fly.io, or any VPS |

## 📸 Demo

> 🎮 **Try it right now**: send a YouTube link to **[@yt_shorts_demo_bot](https://t.me/yt_shorts_demo_bot)** on Telegram.
> 
> _No install needed. Bot is hosted on Railway (24/7)._

---

## 🚀 Quick start

### Option 1: Local (Windows / macOS / Linux)

```bash
# 1. Install FFmpeg
#    Windows: winget install Gyan.FFmpeg
#    macOS:   brew install ffmpeg
#    Linux:   sudo apt install ffmpeg

# 2. Install dependencies
git clone https://github.com/doman68d-rgb/yt-shorts-bot.git
cd yt-shorts-bot
python -m venv venv
source venv/Scripts/activate   # Windows Git Bash
# source venv/bin/activate     # Linux / macOS
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# Add your BOT_TOKEN (get from @BotFather)
# Optionally add OPENAI_API_KEY for smart highlights

# 4. Run
python -m bot
```

Open Telegram, find your bot, send `/start`.

### Option 2: Docker

```bash
cp .env.example .env
# fill in BOT_TOKEN (and optionally OPENAI_API_KEY)
docker compose up -d
docker compose logs -f bot
```

That's it.

### Option 3: ☁️ Railway (24/7 deployment for everyone)

Deploy as a public bot anyone can use. Free $5/month credit.

1. Create a new bot via [@BotFather](https://t.me/BotFather) → `/newbot`
   - Save the token (e.g., `7012345678:AAF-xxxxx`)
2. Go to [railway.app](https://railway.app/) → **New Project** → **Deploy from GitHub repo**
3. Select `doman68d-rgb/yt-shorts-bot`
4. In **Variables**, add:
   ```
   BOT_TOKEN=<your-token-from-step-1>
   ```
   (Optional) also add `OPENAI_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL` if you want Smart highlights.
5. Click **Deploy**. Wait ~2 min for build + Whisper model download.
6. Watch logs: you should see `🚀 Запускаю бота…`
7. Open your bot in Telegram → `/start` → 🎉

**Cost:** ~$1–3/month under free tier for low traffic. See `scripts/deploy-demo.md` for details.

---

## ⚙️ Configuration

All settings live in `.env`:

```ini
# Required
BOT_TOKEN=7012345678:AAF-xxxxxxxxxxxxxxxxxx

# Optional: enable "Smart" strategy (LLM-based highlight selection)
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxx
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini

# Whisper (default: base / cpu / int8)
WHISPER_MODEL=base
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8

# Output clips
CLIP_WIDTH=1080
CLIP_HEIGHT=1920
CLIP_DURATION=45
CLIP_COUNT=3
SKIP_EDGES_PERCENT=10
```

See [`.env.example`](.env.example) for the full reference.

---

## 🤖 Bot commands

| Command | What it does |
|---|---|
| `/start` | Welcome + settings menu |
| `/help` | Full help |
| `/clips N L` | Set clip count and length. Example: `/clips 5 60` |
| `/strategy` | Switch Smart ↔ Random |

Or use inline buttons in **⚙️ Settings**.

---

## 🧠 Highlight strategies

### 🎲 Random (no API key required)

Picks random clips from the "middle" of the video, excluding the first and last `SKIP_EDGES_PERCENT` percent. Always works.

### 🧠 Smart (requires `OPENAI_API_KEY`)

1. Chunks the transcript (30-second windows).
2. Sends to the LLM: *"Pick N most engaging L-second moments for vertical Shorts."*
3. Validates returned ranges (within video bounds, not too short).
4. Cuts clips exactly at those timestamps.

Works with **any OpenAI-compatible API**:

```ini
# OpenRouter (one key, many models)
OPENAI_API_KEY=sk-or-v1-xxxxxxxxxxxxx
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=anthropic/claude-3-haiku

# Ollama (local, free)
OPENAI_API_KEY=ollama
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=llama3.1:8b
```

---

## 📁 Project structure

```
narezkashorts/
├── bot/                    # Telegram bot package (modular)
│   ├── main.py             #   entry point
│   ├── pipeline.py         #   the 5-step processing chain
│   ├── logging.py          #   log config
│   ├── prefs.py            #   per-chat user settings
│   ├── semaphores.py       #   anti-spam
│   ├── fsm.py              #   FSM states
│   ├── messages.py         #   safe wrappers
│   └── formatters.py       #   time / size / escape helpers
├── handlers/               # aiogram handlers (commands, callbacks, URL)
├── services/               # business logic
│   ├── downloader.py       #   yt-dlp wrapper with progress hook
│   ├── transcriber.py      #   faster-whisper with progress callback
│   ├── highlights.py       #   LLM & random highlight selection
│   ├── editor.py           #   ffmpeg-based clip extraction
│   └── progress.py         #   async Telegram progress reporter
├── utils/helpers.py        # file ops, job IDs, etc.
├── tests/                  # 50+ pytest tests
├── Dockerfile              # multi-stage image
├── docker-compose.yml
├── entrypoint.sh
└── pyproject.toml          # ruff + black + mypy config
```

---

## 🧪 Running tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

We run 50+ tests covering URL validation, filename sanitization, time/size
formatting, progress reporting, random/strategy selection, and per-chat prefs.

CI on every push/PR via GitHub Actions (Python 3.10, 3.11, 3.12).

---

## 🛠 Tech stack

| | |
|---|---|
| **aiogram 3.x** | Async Telegram framework |
| **yt-dlp** | Video downloader (1000+ platforms) |
| **faster-whisper** | Whisper ASR, CPU-optimized |
| **moviepy** | Video probing (we don't actually use its rendering) |
| **ffmpeg** | Clipping + 9:16 crop + 1080×1920 scale |
| **httpx** | OpenAI-compatible LLM API client |
| **OpenAI / OpenRouter / Ollama** | Smart highlight selection |

---

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). TL;DR:

1. Fork & branch from `main`
2. Run tests before pushing: `pytest tests/`
3. Format: `black . && ruff check --fix .`
4. Open a PR with a clear description

We welcome:
- 🐛 Bug reports
- 💡 Feature requests
- 📖 Docs improvements
- 🌍 Translations

## 🔒 Security

See [SECURITY.md](SECURITY.md). For vulnerabilities, **don't open public issues** — email privately.

## 📜 License

This project is dual-licensed:

- **AGPL-3.0** for open-source use (see [LICENSE](LICENSE))
- **Commercial** license for embedding in closed-source products (see [COMMERCIAL.md](COMMERCIAL.md))

By contributing, you agree your contributions will be licensed under AGPL-3.0.

## ⚠️ Legal

This bot downloads videos from YouTube and other platforms. Make sure you have the right to download and remix the videos you process — comply with each platform's Terms of Service and applicable copyright law.

## 🌟 Show your support

If this project helped you, give it a ⭐ on GitHub! It helps others discover it.

---

Made with ❤️ and a lot of CPU cycles.
