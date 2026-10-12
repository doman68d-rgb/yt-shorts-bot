"""
handlers/unknown.py
~~~~~~~~~~~~~~~~~~~

Fallback для непонятных сообщений (не команды, не URL).
"""

from __future__ import annotations

from aiogram import Dispatcher
from aiogram.types import Message


async def handle_unknown(message: Message) -> None:
    if message.text and message.text.startswith("/"):
        await message.answer("🤷 Не знаю такой команды. Попробуй /help или /clips.")
    else:
        await message.answer(
            "👋 Привет! Я нарезаю длинные видео в Shorts.\n"
            "Пришли ссылку на YouTube — начнём.\n"
            "Или нажми /help для подробностей."
        )


def register(dp: Dispatcher) -> None:
    dp.message.register(handle_unknown)
