"""
bot/semaphores.py
~~~~~~~~~~~~~~~~~

Глобальные семафоры для анти-спама:
    • GLOBAL_SEM — максимум N параллельных обработок на бота
    • _user_sem() — 1 обработка на пользователя
"""

from __future__ import annotations

import asyncio

# Максимум 2 параллельные обработки на бота.
GLOBAL_SEM: asyncio.Semaphore = asyncio.Semaphore(2)

_USER_SEMS: dict[int, asyncio.Semaphore] = {}


def user_sem(user_id: int) -> asyncio.Semaphore:
    """Получить/создать семафор для конкретного пользователя."""
    if user_id not in _USER_SEMS:
        _USER_SEMS[user_id] = asyncio.Semaphore(1)
    return _USER_SEMS[user_id]
