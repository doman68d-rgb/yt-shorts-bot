"""
handlers/callbacks.py
~~~~~~~~~~~~~~~~~~~~~

Inline-кнопки: меню настроек, выбор стратегии, выбор числа/длины клипов.
"""

from __future__ import annotations

import logging

from aiogram import Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from bot.fsm import VideoStates
from bot.prefs import RESOLUTIONS, get_prefs
from bot.prefs import update as update_prefs

logger = logging.getLogger(__name__)


# ── Главное меню настроек ────────────────────────────────────────────────────
async def show_settings(message: Message, is_edit: bool = False) -> None:
    prefs = get_prefs(message.chat.id)
    # Подсказка что значит выбранное разрешение
    res_note = {
        "720x1280": "лёгкое, быстрее",
        "1080x1350": "Instagram лента (4:5)",
        "1080x1920": "стандарт Shorts/TikTok",
    }.get(prefs.resolution, "")
    text = (
        "⚙️ <b>Настройки обработки</b>\n\n"
        f"Клипов: <b>{prefs.clip_count}</b>\n"
        f"Длина: <b>{prefs.clip_duration}</b> сек\n"
        f"Разрешение: <b>{prefs.resolution}</b> ({res_note})\n"
        f"Стратегия: <b>{'🧠 Smart (LLM)' if prefs.strategy == 'smart' else '🎲 Random'}</b>\n\n"
        "Выбери, что менять:"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔢 Сколько клипов", callback_data="set_count")],
            [InlineKeyboardButton(text="⏱ Длина клипа", callback_data="set_length")],
            [InlineKeyboardButton(text="🎬 Разрешение", callback_data="set_resolution")],
            [InlineKeyboardButton(text="🧠 Стратегия", callback_data="set_strategy")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back_start")],
        ]
    )
    if is_edit:
        await message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    else:
        await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)


async def on_settings(call: CallbackQuery) -> None:
    await call.answer()
    await show_settings(call.message, is_edit=True)


async def on_help(call: CallbackQuery) -> None:
    await call.answer()
    # Просто отправляем новую справку (callback.message.edit_text сломал бы картинки, если бы они были).
    await call.message.answer(
        "🛠 Как пользоваться:\n\n"
        "1️⃣ Пришли ссылку на YouTube.\n"
        "2️⃣ Жди 1–5 минут (прогресс виден в реальном времени).\n"
        "3️⃣ Получи 3 готовых Shorts.\n\n"
        "Команды:\n"
        "   /clips N L  — задать количество и длину клипов\n"
        "   /strategy   — переключить smart ↔ random\n"
        "   /help       — эта справка\n",
    )
    await call.message.answer("А ещё подробная справка по команде /help.")


async def on_send_url(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await call.message.answer("📎 Пришли ссылку на видео сюда в чат, я подхвачу автоматически.")
    await state.set_state(VideoStates.waiting_url)


# ── Выбор количества / длины / стратегии ────────────────────────────────────
COUNTS = [1, 3, 5, 7]
LENGTHS = [15, 30, 45, 60, 90]


async def on_set_count(call: CallbackQuery) -> None:
    await call.answer()
    prefs = get_prefs(call.message.chat.id)
    rows = []
    for n in COUNTS:
        label = f"{n} клип(ов) ✅" if n == prefs.clip_count else f"{n} клип(ов)"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"count_{n}")])
    await call.message.edit_text(
        "Выбери количество клипов:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
    )


async def on_set_length(call: CallbackQuery) -> None:
    await call.answer()
    prefs = get_prefs(call.message.chat.id)
    rows = []
    for length in LENGTHS:
        label = f"{length} сек ✅" if length == prefs.clip_duration else f"{length} сек"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"length_{length}")])
    await call.message.edit_text(
        "Выбери длину клипа:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
    )


async def on_set_strategy(call: CallbackQuery) -> None:
    await call.answer()
    prefs = get_prefs(call.message.chat.id)
    smart_label = "🧠 Smart (LLM) ✅" if prefs.strategy == "smart" else "🧠 Smart (LLM)"
    random_label = "🎲 Random ✅" if prefs.strategy == "random" else "🎲 Random"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=smart_label, callback_data="strategy_smart_inline")],
            [InlineKeyboardButton(text=random_label, callback_data="strategy_random_inline")],
        ]
    )
    await call.message.edit_text("Стратегия выбора моментов:", reply_markup=kb)


async def on_set_resolution(call: CallbackQuery) -> None:
    """Подменю выбора разрешения клипа."""
    await call.answer()
    prefs = get_prefs(call.message.chat.id)
    rows = []
    for key in RESOLUTIONS:
        label = f"{key} ✅" if prefs.resolution == key else f"{key}"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"res_{key}")])
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="settings")])
    await call.message.edit_text(
        "🎬 <b>Разрешение клипа</b>\n\n"
        "Меньше — быстрее обработка и меньше размер файла.\n"
        "Больше — чётче картинка и больше деталей.\n\n"
        "Рекомендации:\n"
        "• 720×1280 — если важна скорость или мало места\n"
        "• 1080×1350 — для Instagram (4:5)\n"
        "• 1080×1920 — стандарт для TikTok/YouTube Shorts\n\n"
        "Выбери:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode=ParseMode.HTML,
    )


async def on_resolution(call: CallbackQuery) -> None:
    """Обработать выбор конкретного разрешения."""
    res_key = call.data.replace("res_", "", 1)
    if res_key not in RESOLUTIONS:
        await call.answer("Неизвестное разрешение", show_alert=True)
        return
    update_prefs(call.message.chat.id, resolution=res_key)
    await call.answer(f"Готово: {res_key}")
    await show_settings(call.message, is_edit=True)


# ── Применение выбора ────────────────────────────────────────────────────────
async def on_count(call: CallbackQuery) -> None:
    n = int(call.data.split("_", 1)[1])
    update_prefs(call.message.chat.id, clip_count=n)
    await call.answer(f"✅ {n} клип(ов)")
    await show_settings(call.message, is_edit=True)


async def on_length(call: CallbackQuery) -> None:
    length = int(call.data.split("_", 1)[1])
    update_prefs(call.message.chat.id, clip_duration=length)
    await call.answer(f"✅ {length} сек")
    await show_settings(call.message, is_edit=True)


async def on_strategy_smart(call: CallbackQuery) -> None:
    update_prefs(call.message.chat.id, strategy="smart")
    await call.answer("🧠 Smart")
    # Если пришли из /strategy (без inline) — отвечаем текстом, не edit.
    if call.message.text and "Какую стратегию" in call.message.text:
        await call.message.edit_text(
            "✅ Стратегия: 🧠 Smart (LLM).\n"
            "Если задан OPENAI_API_KEY — будет использоваться LLM.\n"
            "Без ключа автоматически используется Random."
        )
    else:
        await show_settings(call.message, is_edit=True)


async def on_strategy_random(call: CallbackQuery) -> None:
    update_prefs(call.message.chat.id, strategy="random")
    await call.answer("🎲 Random")
    if call.message.text and "Какую стратегию" in call.message.text:
        await call.message.edit_text(
            "✅ Стратегия: 🎲 Random.\n"
            "Будут выбраны случайные фрагменты из «середины» видео без LLM."
        )
    else:
        await show_settings(call.message, is_edit=True)


async def on_back_start(call: CallbackQuery) -> None:
    await call.answer()
    await call.message.edit_text("👉 Кинь ссылку на YouTube — начнём обработку.")


def register(dp: Dispatcher) -> None:
    # Меню
    dp.callback_query.register(on_settings, F.data == "settings")
    dp.callback_query.register(on_help, F.data == "help")
    dp.callback_query.register(on_send_url, F.data == "send_url")

    # Подменю
    dp.callback_query.register(on_set_count, F.data == "set_count")
    dp.callback_query.register(on_set_length, F.data == "set_length")
    dp.callback_query.register(on_set_strategy, F.data == "set_strategy")
    dp.callback_query.register(on_set_resolution, F.data == "set_resolution")
    dp.callback_query.register(on_resolution, F.data.startswith("res_"))

    # Применение выбора (порядок важен)
    dp.callback_query.register(on_count, F.data.startswith("count_"))
    dp.callback_query.register(on_length, F.data.startswith("length_"))
    dp.callback_query.register(on_strategy_smart, F.data == "strategy_smart")
    dp.callback_query.register(on_strategy_random, F.data == "strategy_random")
    dp.callback_query.register(on_strategy_smart, F.data == "strategy_smart_inline")
    dp.callback_query.register(on_strategy_random, F.data == "strategy_random_inline")
    dp.callback_query.register(on_back_start, F.data == "back_start")
