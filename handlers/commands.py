"""
handlers/commands.py
~~~~~~~~~~~~~~~~~~~~

Текстовые команды: /start /help /clips /strategy.
"""

from __future__ import annotations

from aiogram import Dispatcher
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.markdown import hbold

from bot.fsm import VideoStates
from bot.prefs import get_prefs
from config import settings


async def cmd_start(message: Message, state: FSMContext) -> None:
    """Приветствие + inline-меню."""
    name = message.from_user.first_name if message.from_user else "друг"
    prefs = get_prefs(message.chat.id)

    text = (
        f"👋 Привет, {hbold(name)}!\n\n"
        f"Я — бот, который нарезает длинные видео в вертикальные клипы "
        f"(Shorts / TikTok / Reels).\n\n"
        f"📎 Кинь мне ссылку на YouTube — я скачаю, прогоню через AI "
        f"и верну {prefs.clip_count} готовых 9:16 клипа по {prefs.clip_duration} сек.\n\n"
        f"⚙️ Настройки по умолчанию: <b>{prefs.clip_count} клипов × {prefs.clip_duration} сек</b>.\n"
        f"Хочешь другие — жми «⚙️ Настройки».\n\n"
        f"⚠️ На обработку уходит 1–5 минут. Прогресс виден в реальном времени."
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📘 Помощь", callback_data="help")],
            [InlineKeyboardButton(text="⚙️ Настройки клипов", callback_data="settings")],
            [InlineKeyboardButton(text="▶️ Прислать ссылку", callback_data="send_url")],
        ]
    )
    await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await state.set_state(VideoStates.waiting_url)


async def cmd_help(message: Message) -> None:
    """Полная справка."""
    text = (
        "🛠 Как пользоваться:\n\n"
        "1️⃣ Пришли ссылку на YouTube-видео.\n"
        "2️⃣ Я скачаю его (видно прогресс в реальном времени).\n"
        "3️⃣ Прогоню через Whisper — получу транскрипт.\n"
        "4️⃣ Выберу моменты:\n"
        "   • 🧠 <b>Smart</b> (если задан OPENAI_API_KEY) — LLM выберет яркие места.\n"
        "   • 🎲 <b>Random</b> — случайные фрагменты из «середины».\n"
        "5️⃣ Нарежу клипы в 9:16 (1080×1920) через ffmpeg.\n"
        "6️⃣ Пришлю готовые клипы сюда в Telegram.\n\n"
        "⚙️ Команды:\n"
        "   /clips N L    — задать <b>N</b> клипов по <b>L</b> секунд.\n"
        "                   Пример: <code>/clips 5 60</code>\n"
        "   /strategy     — переключить smart ↔ random.\n"
        "   /help         — эта справка.\n\n"
        f"🤖 Модель Whisper: {settings.WHISPER_MODEL} ({settings.WHISPER_DEVICE})\n"
        f"📐 Кроп: 9:16, {settings.CLIP_WIDTH}×{settings.CLIP_HEIGHT}\n"
    )
    await message.answer(text, parse_mode=ParseMode.HTML)


async def cmd_clips(message: Message) -> None:
    """`/clips N L` — задать количество и длительность клипов."""
    args = (message.text or "").split()
    if len(args) != 3:
        await message.answer(
            "⚙️ Формат: <code>/clips N L</code>\n"
            "Где <b>N</b> — количество клипов, <b>L</b> — длина в секундах.\n"
            "Пример: <code>/clips 5 60</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    try:
        n = int(args[1])
        length = int(args[2])
    except ValueError:
        await message.answer("❌ N и L должны быть целыми числами.")
        return

    if not (1 <= n <= 10):
        await message.answer("❌ N (количество клипов) должно быть от 1 до 10.")
        return
    if not (5 <= length <= 180):
        await message.answer("❌ L (длина клипа) должна быть от 5 до 180 секунд.")
        return

    from bot.prefs import update

    update(message.chat.id, clip_count=n, clip_duration=length)
    await message.answer(
        f"✅ Запомнил: <b>{n}</b> клипов по <b>{length}</b> сек каждый.\n"
        f"Следующая обработка будет с такими параметрами.",
        parse_mode=ParseMode.HTML,
    )


async def cmd_strategy(message: Message) -> None:
    """`/strategy` — переключение стратегии через inline-кнопки."""
    prefs = get_prefs(message.chat.id)
    smart_label = "🧠 Smart (LLM) ✅" if prefs.strategy == "smart" else "🧠 Smart (LLM)"
    random_label = "🎲 Random ✅" if prefs.strategy == "random" else "🎲 Random"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=smart_label, callback_data="strategy_smart")],
            [InlineKeyboardButton(text=random_label, callback_data="strategy_random")],
        ]
    )
    await message.answer(
        "Какую стратегию выбора моментов использовать?",
        reply_markup=kb,
    )


def register(dp: Dispatcher) -> None:
    dp.message.register(cmd_start, Command("start"))
    dp.message.register(cmd_help, Command("help"))
    dp.message.register(cmd_clips, Command("clips"))
    dp.message.register(cmd_strategy, Command("strategy"))
