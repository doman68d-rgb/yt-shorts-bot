"""
bot/main.py
~~~~~~~~~~~

Точка входа для запуска: `python -m bot` или `python bot/main.py`.
"""

from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from bot.logging import setup_logging
from config import settings
from handlers import register as register_handlers
from utils.helpers import wipe_temp_dirs


logger = logging.getLogger(__name__)


async def run() -> None:
    """Запустить бота в polling-режиме."""
    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    register_handlers(dp)

    logger.info("🧹 Чищу старые временные файлы…")
    wipe_temp_dirs()

    logger.info("🚀 Запускаю бота…")
    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )
    finally:
        await bot.session.close()
        logger.info("🛑 Бот остановлен")


def main() -> None:
    setup_logging()
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("Остановлено пользователем (Ctrl+C)")
    except Exception as exc:
        logger.critical("Фатальная ошибка при запуске: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
