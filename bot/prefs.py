"""
bot/prefs.py
~~~~~~~~~~~~

Пользовательские предпочтения (per chat_id).

Кладётся в dict в памяти. На проде надо заменить на Redis.
"""

from __future__ import annotations

from dataclasses import dataclass

from config import settings


@dataclass
class UserPrefs:
    """Предпочтения одного пользователя (чата)."""

    clip_count: int = int(settings.CLIP_COUNT)
    clip_duration: int = int(settings.CLIP_DURATION)
    strategy: str = "smart"   # "smart" (LLM) или "random"


# Глобальное хранилище. На проде заменить на Redis.
_PREFS: dict[int, UserPrefs] = {}


def get_prefs(chat_id: int) -> UserPrefs:
    """Получить prefs для чата. Создаёт дефолтные, если не было."""
    if chat_id not in _PREFS:
        _PREFS[chat_id] = UserPrefs()
    return _PREFS[chat_id]


def update(chat_id: int, **kwargs) -> UserPrefs:
    """Обновить prefs. Возвращает обновлённый объект."""
    prefs = get_prefs(chat_id)
    for k, v in kwargs.items():
        if hasattr(prefs, k):
            setattr(prefs, k, v)
    return prefs


def reset(chat_id: int) -> None:
    """Сбросить prefs (используется в тестах)."""
    _PREFS.pop(chat_id, None)
