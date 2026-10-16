#!/usr/bin/env bash
# entrypoint.sh — последняя проверка перед запуском бота в Docker.

set -e

echo "🩺 Health checks перед стартом..."

# 1. FFmpeg доступен?
if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "❌ FFmpeg не найден в PATH контейнера"
    exit 1
fi

FFMPEG_VER=$(ffmpeg -version 2>&1 | head -1)
echo "✔ FFmpeg: $FFMPEG_VER"

# 2. Python-зависимости живые?
python -c "
import aiogram
import faster_whisper
import yt_dlp
import httpx
print(f'✔ aiogram {aiogram.__version__}')
print(f'✔ faster-whisper {getattr(faster_whisper, \"__version__\", \"installed\")}')
print(f'✔ yt-dlp {yt_dlp.version.__version__}')
print(f'✔ httpx {httpx.__version__}')
"

# 3. Токен задан?
if [ -z "${BOT_TOKEN:-}" ]; then
    echo "❌ BOT_TOKEN не задан."
    echo "   Должен быть установлен в Railway Dashboard → Variables."
    echo "   Показываю все переменные окружения которые ВИДНЫ из контейнера:"
    echo
    # Печатаем только ИМЕНА переменных, не значения (для безопасности)
    env | cut -d= -f1 | sort | grep -E '^[A-Z_][A-Z0-9_]*$' | while read name; do
        echo "   • $name"
    done
    echo
    echo "   Ищи переменную BOT_TOKEN в этом списке выше."
    echo "   Если её там нет — добавь в Railway UI: Settings → Variables."
    exit 1
fi
echo "✔ BOT_TOKEN задан (${#BOT_TOKEN} символов)"

# 4. LLM-ключ? (опционально — бот без него работает в random-режиме)
if [ -n "${OPENAI_API_KEY:-}" ] || [ -n "${LLM_API_KEY:-}" ]; then
    echo "✔ LLM API key задан — стратегия 'smart' будет работать"
else
    echo "ℹ️  LLM API key НЕ задан — будет использоваться Random стратегия"
fi

# 5. Лог-файл доступен для записи?
LOG_DIR=$(dirname "${LOG_FILE:-bot.log}")
mkdir -p "$LOG_DIR"
touch "$LOG_FILE"
echo "✔ Логи: $LOG_FILE"

echo ""
echo "🚀 Запускаю бота..."
echo ""

exec python -u -m bot
