"""
config.py
~~~~~~~~~

Единая точка загрузки настроек проекта.

Что делает:
    1. Читает переменные из файла .env (через python-dotenv).
    2. Валидирует обязательные переменные (BOT_TOKEN) — если токена нет,
       программа падает ДО старта aiogram, чтобы не получить непонятный
       RuntimeError где-то в середине polling-а.
    3. Содержит «дефолты» — параметры, которые можно переопределить
       через .env, но разумные значения уже проставлены.

Использование:
    from config import settings
    print(settings.BOT_TOKEN)        # токен Telegram
    print(settings.DOWNLOADS_DIR)    # Path("downloads/")
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Final

from dotenv import load_dotenv

# Фикс кодировки для Windows: без этого Git Bash / cmd.exe падают на
# эмодзи и кириллице в print/logger (UnicodeEncodeError: cp1251).
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass  # не критично — просто останется дефолтная кодировка

# ──────────────────────────────────────────────────────────────────────────────
# 1. Загрузка .env
# ──────────────────────────────────────────────────────────────────────────────
# load_dotenv() ищет .env в текущей рабочей директоре и поднимает переменные
# в os.environ. Делаем это ОДИН раз при импорте модуля.
load_dotenv()


# ──────────────────────────────────────────────────────────────────────────────
# 2. Вспомогательные функции
# ──────────────────────────────────────────────────────────────────────────────
def _require_env(key: str) -> str:
    """Вернуть значение обязательной переменной или упасть с понятной ошибкой."""
    value = os.getenv(key)
    if not value or value.startswith("123456789"):  # защита от .env-example
        raise RuntimeError(
            f"❌ Переменная окружения {key!r} не задана или имеет значение по умолчанию.\n"
            f"👉 Создай файл `.env` в корне проекта (рядом с bot.py) и впиши туда:\n"
            f"   {key}=<реальное значение>\n"
            f"   Образец смотри в `.env.example`."
        )
    return value


def _get_path(key: str, default: str) -> Path:
    """Получить путь из env (если задан) или вернуть дефолт относительно корня проекта."""
    raw = os.getenv(key)
    base = Path(__file__).resolve().parent  # корень проекта (где лежит config.py)
    return (base / raw).resolve() if raw else (base / default).resolve()


# ──────────────────────────────────────────────────────────────────────────────
# 3. Конфиг
# ──────────────────────────────────────────────────────────────────────────────
class Settings:
    """Контейнер настроек. Все атрибуты read-only (Final через dataclass позже)."""

    # --- Обязательное ---
    BOT_TOKEN: str = _require_env("BOT_TOKEN")

    # --- Пути (можно переопределить через .env: DOWNLOADS_DIR=my_videos) ---
    DOWNLOADS_DIR: Path = _get_path("DOWNLOADS_DIR", "downloads")
    CLIPS_DIR: Path = _get_path("CLIPS_DIR", "clips")

    # --- Параметры пайплайна (можно крутить в .env) ---
    # Модель faster-whisper: tiny / base / small / medium / large-v3
    # tiny — самая быстрая, base — баланс качества и скорости на CPU
    WHISPER_MODEL: Final[str] = os.getenv("WHISPER_MODEL", "base")

    # Устройство для whisper: "cpu" или "cuda"
    WHISPER_DEVICE: Final[str] = os.getenv("WHISPER_DEVICE", "cpu")

    # Тип квантования: int8 / int8_float16 / float16 / float32
    # int8 заметно ускоряет CPU-инференс почти без потери качества
    WHISPER_COMPUTE_TYPE: Final[str] = os.getenv("WHISPER_COMPUTE_TYPE", "int8")

    # Целевой формат клипа (Shorts / TikTok / Reels)
    CLIP_WIDTH: Final[int] = int(os.getenv("CLIP_WIDTH", "1080"))
    CLIP_HEIGHT: Final[int] = int(os.getenv("CLIP_HEIGHT", "1920"))
    CLIP_DURATION: Final[int] = int(os.getenv("CLIP_DURATION", "45"))  # секунд
    CLIP_COUNT: Final[int] = int(os.getenv("CLIP_COUNT", "3"))          # сколько клипов

    # Исключаемые «хвосты» (первые и последние N процентов видео)
    SKIP_EDGES_PERCENT: Final[int] = int(os.getenv("SKIP_EDGES_PERCENT", "10"))


# ──────────────────────────────────────────────────────────────────────────────
# 4. Создаём папки сразу и экспортируем singleton
# ──────────────────────────────────────────────────────────────────────────────
settings = Settings()

# Создаём папки при импорте. exist_ok=True — без падений, если уже есть.
settings.DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
settings.CLIPS_DIR.mkdir(parents=True, exist_ok=True)


# Удобно для отладки: `python config.py` напечатает текущие настройки
if __name__ == "__main__":
    print("⚙️  Текущие настройки:")
    print(f"  • BOT_TOKEN: {settings.BOT_TOKEN[:8]}... (скрыт)")
    print(f"  • DOWNLOADS_DIR: {settings.DOWNLOADS_DIR}")
    print(f"  • CLIPS_DIR:    {settings.CLIPS_DIR}")
    print(f"  • WHISPER:      {settings.WHISPER_MODEL} on {settings.WHISPER_DEVICE} ({settings.WHISPER_COMPUTE_TYPE})")
    print(f"  • CLIP размер:  {settings.CLIP_WIDTH}x{settings.CLIP_HEIGHT}")
    print(f"  • CLIP длина:   {settings.CLIP_DURATION}s × {settings.CLIP_COUNT} шт")
    print(f"  • SKIP_EDGES:   {settings.SKIP_EDGES_PERCENT}% с каждого края")
