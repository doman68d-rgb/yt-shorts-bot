#!/usr/bin/env bash
# create_release.sh — создать релиз v0.1.0 через GitHub CLI
#
# Использование:
#   1. Установи GitHub CLI:   winget install GitHub.cli  (или brew install gh)
#   2. Залогинься:           gh auth login
#   3. Запусти:               bash scripts/create_release.sh
#
# Скрипт создаст релиз с тегом v0.1.0 и release notes.

set -e

if ! command -v gh >/dev/null 2>&1; then
    echo "❌ gh CLI не найден. Установи:"
    echo "   Windows: winget install GitHub.cli"
    echo "   macOS:   brew install gh"
    echo "   Linux:   apt install gh"
    exit 1
fi

# Проверка авторизации.
if ! gh auth status >/dev/null 2>&1; then
    echo "❌ Не залогинен в gh. Выполни: gh auth login"
    exit 1
fi

RELEASE_NOTES="$(cat <<'EOF'
## ✨ Features

- 📥 Download YouTube videos via `yt-dlp`
- 🎧 Transcribe with `faster-whisper` (base, CPU-optimized)
- 🧠 Smart highlight selection via OpenAI-compatible LLM (with random fallback)
- ✂️ Auto-edit to vertical 9:16 (1080×1920) using ffmpeg
- 📤 Send clips directly to Telegram chat
- 🔍 Real-time progress bar in Telegram
- ⚙️ In-chat settings via `/clips N L`, `/strategy`, and inline buttons

## 🚀 Quick start

```bash
git clone https://github.com/doman68d-rgb/yt-shorts-bot.git
cd yt-shorts-bot
cp .env.example .env       # Add BOT_TOKEN
docker compose up -d
```

Or without Docker: `pip install -r requirements.txt && python -m bot`

## 📊 Stats

- 50+ pytest tests, all passing
- 0 ruff warnings
- Python 3.10 / 3.11 / 3.12 tested via GitHub Actions
- Multi-stage Docker image with FFmpeg pre-installed

## 📜 License

Dual-licensed under AGPL-3.0 (open-source) and Commercial. See [LICENSE](LICENSE) and [COMMERCIAL.md](COMMERCIAL.md).
EOF
)"

gh release create v0.1.0 \
    --title "v0.1.0 — Initial public release" \
    --notes "$RELEASE_NOTES" \
    --target main

echo ""
echo "✅ Готово! Открой https://github.com/doman68d-rgb/yt-shorts-bot/releases"
