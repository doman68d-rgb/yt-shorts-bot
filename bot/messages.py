"""
bot/messages.py
~~~~~~~~~~~~~~~

Безопасные операции с сообщениями (не падают, если юзер удалил чат и т.п.).
"""

from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.types import Message

logger = logging.getLogger(__name__)


async def safe_send(bot: Bot, chat_id: int, text: str, **kwargs) -> None:
    """Отправить сообщение без падения. Логируем, но не пробрасываем."""
    try:
        await bot.send_message(chat_id=chat_id, text=text, **kwargs)
    except Exception as exc:  # noqa: BLE001
        logger.warning("safe_send → chat %d упал: %s", chat_id, exc)


async def safe_delete(msg: Message | None) -> None:
    """Удалить сообщение без падения (если уже удалено/нет прав)."""
    if msg is None:
        return
    try:
        await msg.delete()
    except Exception:  # noqa: BLE001
        pass
