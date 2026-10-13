"""
handlers/url.py
~~~~~~~~~~~~~~~

Приём URL и запуск pipeline (через GLOBAL_SEM и user_sem).
"""

from __future__ import annotations

import logging

from aiogram import Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.pipeline import run_pipeline
from bot.prefs import get_prefs
from bot.semaphores import GLOBAL_SEM, user_sem
from utils.helpers import is_youtube_url

logger = logging.getLogger(__name__)


async def handle_url_message(message: Message, state: FSMContext) -> None:
    """Прислали ссылку — запускаем pipeline."""
    if not message.text:
        return

    url = message.text.strip()
    user_id = message.from_user.id if message.from_user else 0
    chat_id = message.chat.id

    if not (url.startswith("http://") or url.startswith("https://")):
        await message.answer(
            "🤔 Это не похоже на ссылку.\n"
            "Пришли URL, начинающийся с <code>http://</code> или <code>https://</code>.",
            parse_mode=ParseMode.HTML,
        )
        return

    semaphore = user_sem(user_id)
    if semaphore.locked():
        await message.answer("⏳ У тебя уже идёт обработка. Подожди, пока закончится.")
        return

    youtube_hint = " (YouTube)" if is_youtube_url(url) else ""
    prefs = get_prefs(chat_id)
    status = await message.answer(
        f"📥 Принял ссылку{youtube_hint}.\n"
        f"⚙️ Параметры: {prefs.clip_count} клипов × {prefs.clip_duration} сек, "
        f"{'🧠 Smart' if prefs.strategy == 'smart' else '🎲 Random'}.\n"
        f"Запускаю пайплайн…\n\nПодожди ~1–5 минут."
    )

    async with GLOBAL_SEM, semaphore:
        await run_pipeline(message, status, url, chat_id)
    await state.clear()


def register(dp: Dispatcher) -> None:
    # Любой текст с http(s):// — запуск pipeline.
    dp.message.register(handle_url_message, F.text.regexp(r"https?://"))
