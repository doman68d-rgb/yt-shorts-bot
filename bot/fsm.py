"""
bot/fsm.py
~~~~~~~~~~

FSM-состояния для диалога с ботом.
"""

from aiogram.fsm.state import State, StatesGroup


class VideoStates(StatesGroup):
    """Состояния диалога."""

    waiting_url = State()  # ждём ссылку от пользователя
    choosing_clips = State()  # ждём решение по количеству/длине клипов
