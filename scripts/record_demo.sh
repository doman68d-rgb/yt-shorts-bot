#!/usr/bin/env bash
# record_demo.sh — записать 60-секундный GIF-демо бота для README.
#
# Использование:
#   1. Запусти бота локально: `python -m bot`
#   2. Запусти этот скрипт: `./scripts/record_demo.sh`
#   3. В Telegram открой своего бота и пришли любую YouTube-ссылку
#   4. Запись начнётся автоматически через 3 секунды.
#   5. Нажми Ctrl+C, когда клипы придут — GIF сохранится в docs/demo.gif

set -e

OUTPUT="${1:-docs/demo.gif}"

if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "❌ ffmpeg не найден. Установи: brew install ffmpeg / apt install ffmpeg"
    exit 1
fi

echo "🎬 Записываю демо-GIF с экрана → $OUTPUT"
echo "⏱  Подожди 3 секунды, затем в Telegram пришли ссылку боту..."
echo "⏹  Останови: Ctrl+C"
sleep 3

# macOS
if [[ "$OSTYPE" == "darwin"* ]]; then
    ffmpeg -f avfoundation -i "1:0" -t 90 \
        -vf "fps=15,scale=720:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse" \
        -loop 0 "$OUTPUT"
# Linux
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    if command -v recordmydesktop >/dev/null 2>&1; then
        TMP=$(mktemp /tmp/demo-XXXX.mp4)
        recordmydesktop --no-sound --output="$TMP" --duration=90
        ffmpeg -i "$TMP" -vf "fps=15,scale=720:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse" \
            -loop 0 "$OUTPUT"
        rm -f "$TMP"
    else
        echo "💡 Установи recordmydesktop: sudo apt install recordmydesktop"
        echo "    Или используй OBS / SimpleScreenRecorder / иной инструмент"
        echo "    Вручную сделай 60-сек запись экрана с ботом и сохрани как $OUTPUT"
        exit 1
    fi
# Windows (Git Bash)
else
    echo "💡 На Windows нет встроенного screen recording в Git Bash."
    echo ""
    echo "   Вариант 1: установи OBS Studio и запиши экран вручную"
    echo "               (https://obsproject.com/)"
    echo ""
    echo "   Вариант 2: используй ShareX / ScreenToGif"
    echo "               (https://www.screentogif.com/)"
    echo ""
    echo "   После записи сохрани как $OUTPUT и конвертируй в GIF:"
    echo "   ffmpeg -i input.mp4 -vf \"fps=15,scale=720:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse\" \\"
    echo "          -loop 0 $OUTPUT"
    exit 1
fi

echo ""
echo "✅ Готово: $OUTPUT"
echo "💾 Размер: $(ls -lh "$OUTPUT" | awk '{print $5}')"
