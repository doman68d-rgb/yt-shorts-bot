"""
bot/prefs.py
~~~~~~~~~~~~

Пользовательские предпочтения (per chat_id).

Кладётся в dict в памяти. На проде надо заменить на Redis.
"""

from __future__ import annotations

from dataclasses import dataclass

from config import settings

# ──────────────────────────────────────────────────────────────────────────────
# Поддерживаемые разрешения
# ──────────────────────────────────────────────────────────────────────────────
RESOLUTIONS: dict[str, tuple[int, int]] = {
    "720x1280": (720, 1280),  # лёгкое, быстро, ~5 МБ за клип
    "1080x1350": (1080, 1350),  # Instagram лента (4:5)
    "1080x1920": (1080, 1920),  # стандарт Shorts/TikTok (9:16)
}

DEFAULT_RESOLUTION = "1080x1920"


def parse_resolution(key: str) -> tuple[int, int]:
    """Безопасно получить (width, height) по ключу. Fallback на дефолт."""
    return RESOLUTIONS.get(key, RESOLUTIONS[DEFAULT_RESOLUTION])


# ──────────────────────────────────────────────────────────────────────────────
# UserPrefs dataclass
# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class UserPrefs:
    """Предпочтения одного пользователя (чата)."""

    clip_count: int = int(settings.CLIP_COUNT)
    clip_duration: int = int(settings.CLIP_DURATION)
    strategy: str = "smart"  # "smart" (LLM) | "random"
    resolution: str = DEFAULT_RESOLUTION  # ключ из RESOLUTIONS


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
