<!--
GitHub Pages лендинг для проекта.
Включи GitHub Pages через Settings → Pages → Source: gh-pages branch
Файл положи в корень gh-pages ветки (или используй Jekyll тему repo).
-->

# ✂️ NarezkaShorts

> **Telegram bot that turns long YouTube videos into viral Shorts — automatically.**

## ✨ Features

- 🎧 **Whisper transcription** of any YouTube video
- 🧠 **LLM-powered highlight selection** (or random fallback)
- ✂️ **Auto-edit** to vertical 9:16 (1080×1920)
- 📤 **Send clips directly** to your Telegram chat
- 🔍 **Real-time progress** bar
- 🐳 **Docker-ready** — `docker compose up` and done
- 🧪 **50+ tests** in CI

## 🚀 Quick start

```bash
git clone https://github.com/<your-username>/narezkashorts
cd narezkashorts
cp .env.example .env
# Add your BOT_TOKEN
docker compose up -d
docker compose logs -f bot
```

Bot up. Open Telegram, send it a YouTube link, get 3 clips.

## 📸 Demo

![Demo GIF — coming soon](docs/demo.gif)

> _Record with `./scripts/record_demo.sh` after your first successful run._

## 🧠 Smart highlights

With an OpenAI-compatible API key, the bot uses an LLM to pick the most engaging moments from the transcript. Works with:

- OpenAI (`gpt-4o-mini`)
- OpenRouter (`anthropic/claude-3-haiku`, etc.)
- Local Ollama (`llama3.1:8b`) — free

Without a key, falls back to random clips from the middle of the video.

## 📜 License

Dual-licensed under:
- **AGPL-3.0** for open-source use
- **Commercial** license for embedding in closed-source products

See [LICENSE](https://github.com/<your-username>/narezkashorts/blob/main/LICENSE) and [COMMERCIAL.md](https://github.com/<your-username>/narezkashorts/blob/main/COMMERCIAL.md).

## ⭐ Star us on GitHub!

If this is useful to you, please star the repo — it really helps.

[GitHub repo →](https://github.com/<your-username>/narezkashorts)
