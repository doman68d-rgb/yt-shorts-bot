"""
bot/logging.py
~~~~~~~~~~~~~~

Настройка логирования для всего бота.

Консоль: INFO
Файл bot.log: INFO с полным форматом
aiohttp access/chat: WARNING (подавлено — иначе лог забит мусором Telegram)
"""

from __future__ import annotations

import logging
import sys


def setup_logging(log_file: str = "bot.log") -> None:
    """Настроить логирование. Вызывается в `main.py` однократно."""
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

    root = logging.getLogger()
    # Удаляем дефолтные хендлеры, чтобы не было двойных логов при повторных вызовах.
    for h in list(root.handlers):
        root.removeHandler(h)

    # ── Stdout ──────────────────────────────────────────────────────────────
    stdout_h = logging.StreamHandler(sys.stdout)
    stdout_h.setFormatter(logging.Formatter(fmt))
    root.addHandler(stdout_h)

    # ── Файл ────────────────────────────────────────────────────────────────
    try:
        file_h = logging.FileHandler(log_file, encoding="utf-8")
        file_h.setFormatter(logging.Formatter(fmt))
        root.addHandler(file_h)
    except OSError:
        # Если файл не доступен (read-only файловая система, нет прав) — продолжим
        # только с stdout, без падения.
        pass

    root.setLevel(logging.INFO)

    # ── Подавить шум ────────────────────────────────────────────────────────
    for noisy in ("aiohttp.access", "aiohttp.client", "aiohttp.internal",
                  "aiogram.event", "multipart"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def silence(name: str) -> None:
    """Утилита для подавления конкретного логгера (например, в тестах)."""
    logging.getLogger(name).setLevel(logging.WARNING)
