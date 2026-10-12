# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: Builder — собираем wheels для зависимостей
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim-bookworm AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: Runtime — минимальный образ с ботами и ffmpeg
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim-bookworm AS runtime

# ffmpeg — обязателен. libgomp1 — для faster-whisper.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libgomp1 \
        ca-certificates \
        tini \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get autoremove -y \
    && apt-get clean

# Запуск от не-root пользователя.
RUN useradd --create-home --shell /bin/bash botuser

WORKDIR /app

# Устанавливаем пакеты из wheels builder-этапа.
COPY requirements.txt .
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels

# Копируем код проекта.
COPY --chown=botuser:botuser bot/ /app/bot/
COPY --chown=botuser:botuser services/ /app/services/
COPY --chown=botuser:botuser utils/ /app/utils/
COPY --chown=botuser:botuser handlers/ /app/handlers/
COPY --chown=botuser:botuser config.py /app/
COPY --chown=botuser:botuser entrypoint.sh /app/
COPY --chown=botuser:botuser .env.example /app/

RUN chmod +x /app/entrypoint.sh

# Папки для временных файлов.
RUN mkdir -p /app/downloads /app/clips /app/logs \
    && chown -R botuser:botuser /app

USER botuser

# Дефолты (могут быть переопределены через env_file в docker-compose).
ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    WHISPER_MODEL=base \
    WHISPER_DEVICE=cpu \
    WHISPER_COMPUTE_TYPE=int8 \
    LLM_MODEL=gpt-4o-mini \
    LLM_BASE_URL=https://api.openai.com/v1 \
    LOG_FILE=/app/logs/bot.log

# Healthcheck — проверяем, что процесс бота жив.
HEALTHCHECK --interval=60s --timeout=10s --start-period=60s --retries=3 \
    CMD pgrep -f "python -m bot" > /dev/null || exit 1

# tini корректно ловит SIGTERM (важно для docker stop).
ENTRYPOINT ["/usr/bin/tini", "--", "/app/entrypoint.sh"]
