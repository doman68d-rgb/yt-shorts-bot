"""
bot/formatters.py
~~~~~~~~~~~~~~~~~

Маленькие функции форматирования для текста.
"""

from __future__ import annotations

from services.editor import ClipRange


def escape(text: str) -> str:
    """Грубое HTML-экранирование (защита от «<» в названии видео)."""
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def duration(seconds: float) -> str:
    """HH:MM:SS / MM:SS."""
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:d}:{m:02d}:{sec:02d}" if h else f"{m:d}:{sec:02d}"


def clip_range(r: ClipRange) -> str:
    """Тайм-диапазон клипа в формате MM:SS → MM:SS."""
    return f"[{duration(r.start)} → {duration(r.end)}]" if r else ""
