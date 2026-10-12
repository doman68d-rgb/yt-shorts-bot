"""
handlers/
~~~~~~~~

Хендлеры aiogram. Разбиты по функциональности:

    commands    — /start, /help, /clips, /strategy
    callbacks   — кнопки inline-меню
    url         — приём URL и запуск pipeline
    unknown     — fallback для непонятных сообщений
"""

from aiogram import Dispatcher

from . import callbacks, commands, unknown, url


def register(dp: Dispatcher) -> None:
    """Зарегистрировать все хендлеры в диспетчере."""
    commands.register(dp)
    callbacks.register(dp)
    url.register(dp)
    unknown.register(dp)
