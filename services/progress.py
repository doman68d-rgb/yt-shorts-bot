"""
services/progress.py
~~~~~~~~~~~~~~~~~~~~

Универсальный «прогресс-репортер» для тяжёлых шагов пайплайна.

Зачем:
    yt-dlp умеет писать progress_hook, у faster-whisper нет встроенного
    прогресса, ffmpeg вообще молчит. Этот модуль:
        • запускает фоновую таску, которая раз в N секунд редактирует
          одно и то же сообщение в Telegram;
        • предоставляет набор методов (`update`, `done`, `fail`), которые
          вызываются из тяжёлой функции в asyncio-потоке.

⚠️ Синхронизация:
    • Все методы (`update`, `done`, `fail`) — синхронные, можно звать
      прямо из ffmpeg/whisper/yt-dlp колбэков.
    • Но они **не блокируют** event loop, потому что пишут в asyncio.Queue
      и фреймворк progress-репортера сам решает, когда слать в Telegram.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Модели
# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class ProgressState:
    """Текущее состояние прогресса (шаг + текст + 0..100)."""

    step: str = "init"
    text: str = "⏳ Обработка..."
    percent: float = 0.0
    done: bool = False
    failed: bool = False

    def render(self) -> str:
        # Прогресс-бар из 10 блоков.
        blocks = max(0, min(10, round(self.percent / 10)))
        bar = "▓" * blocks + "░" * (10 - blocks)
        head = f"{self.text}\n\n`{bar}` {self.percent:.0f}%"
        return head


class ProgressReporter:
    """
    Объект, который передаётся в тяжёлые функции.

    Использование из bot.py:
        reporter = ProgressReporter(bot, status_msg, total_duration_sec=...)
        async with reporter:                      # запускает фоновую таску
            await run_pipeline(...)

    Использование из синхронного yt-dlp progress_hook:
        def _hook(d):
            reporter.yt_dlp_update(d)

    Использование из синхронного whisper:
        reporter.set_step("transcribing", percent=10)
        ...
        reporter.set_step("transcribing", percent=80)
        reporter.done()
    """

    # Минимальный интервал между edit-сообщениями — Telegram API
    # ограничивает ~30 msg/sec на одного бота, но на chat есть лимит
    # ~1 msg/sec если часто слать в одно сообщение.
    MIN_INTERVAL_SEC = 1.5

    def __init__(
        self,
        bot,  # aiogram Bot
        status_msg,  # aiogram Message
        total_seconds: float | None = None,
    ):
        self.bot = bot
        self.status_msg = status_msg
        self.total_seconds = total_seconds or 0.0

        self.state = ProgressState()
        self._task: asyncio.Task | None = None
        self._last_sent_text: str = ""
        self._last_sent_at: float = 0.0
        self._queue: asyncio.Queue | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    # ─── Lifecycle ────────────────────────────────────────────────────────────
    def __enter__(self):
        """Запустить фоновую задачу. Используется через `with` в async-контексте."""
        # Мы в синхронном коде (asyncio.to_thread), поэтому захватываем loop.
        try:
            self._loop = asyncio.get_running_loop()
            self._queue = asyncio.Queue()
            self._task = self._loop.create_task(self._pump())
        except RuntimeError:
            # Если вызвали вне async — никаких апдейтов не будет.
            logger.warning("ProgressReporter вне async — отключаем апдейты.")
        return self

    def __exit__(self, *exc):
        # В контексте with — просто ensure_done.
        pass

    async def __aenter__(self):
        # Если войти через `async with` — корректный запуск.
        self._loop = asyncio.get_running_loop()
        self._queue = asyncio.Queue()
        self._task = self._loop.create_task(self._pump())
        return self

    async def __aexit__(self, *exc):
        if self._task and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    # ─── Внешний API (синхронный, можно звать из yt-dlp, whisper, ffmpeg) ───
    def set_step(self, step: str, text: str, percent: float) -> None:
        """Обновить шаг и процент. Sync API."""
        self.state.step = step
        self.state.text = text
        self.state.percent = max(0.0, min(100.0, percent))
        if self._queue is not None:
            with contextlib.suppress(Exception):
                self._loop.call_soon_threadsafe(self._queue.put_nowait, "update")

    def done(self) -> None:
        """Сообщить, что задача завершена. Sync API."""
        self.state.done = True
        self.state.percent = 100.0
        self.state.text = "✅ Готово"
        if self._queue is not None:
            with contextlib.suppress(Exception):
                self._loop.call_soon_threadsafe(self._queue.put_nowait, "stop")

    def fail(self, reason: str) -> None:
        """Сообщить об ошибке. Sync API."""
        self.state.failed = True
        self.state.text = f"❌ {reason}"
        if self._queue is not None:
            with contextlib.suppress(Exception):
                self._loop.call_soon_threadsafe(self._queue.put_nowait, "stop")

    # ─── Специализированные хелперы ──────────────────────────────────────────
    def yt_dlp_update(self, d: dict) -> None:
        """
        Вызывать из yt-dlp progress_hook(d).
        d['status'] in: 'downloading', 'finished', 'error'.
        """
        status = d.get("status")
        if status == "downloading":
            downloaded = d.get("downloaded_bytes", 0)
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            percent = (downloaded / total * 100) if total else 0.0
            speed = d.get("speed") or 0
            eta = d.get("eta") or 0
            speed_str = self._fmt_speed(speed)
            eta_str = self._fmt_eta(eta)
            self.set_step(
                step="downloading",
                text=f"⬇️ Скачиваю видео… ({speed_str}, ⏱ {eta_str})",
                percent=min(50.0, percent / 2),  # скачивание занимает первую половину прогресса
            )
        elif status == "finished":
            self.set_step("downloading", "✅ Скачал, готовлю к обработке…", 50.0)
        elif status == "error":
            self.fail("yt-dlp: ошибка скачивания")

    def whisper_update(self, percent: float, text: str = "🎧 Whisper распознаёт речь…") -> None:
        """Установить прогресс для whisper. percent: 50..85."""
        self.set_step("transcribing", text, max(50.0, min(85.0, percent)))

    def ffmpeg_update(self, clip_index: int, total_clips: int) -> None:
        """Нарезаем клипы: 85..99%."""
        per_clip = 14.0 / max(1, total_clips)  # от 85% до 99%
        percent = 85.0 + per_clip * clip_index
        self.set_step(
            "editing",
            f"✂️ Нарезаю клип {clip_index}/{total_clips}…",
            percent,
        )

    # ─── Внутренний апдейтер ─────────────────────────────────────────────────
    async def _pump(self) -> None:
        """Фоновая таска: раз в MIN_INTERVAL секунд отправляет editMessageText."""
        try:
            while True:
                try:
                    sig = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=self.MIN_INTERVAL_SEC,
                    )
                except asyncio.TimeoutError:
                    sig = None

                now = time.monotonic()
                if sig is None and (now - self._last_sent_at) < self.MIN_INTERVAL_SEC:
                    continue

                text = self.state.render()
                if text != self._last_sent_text:
                    with contextlib.suppress(Exception):
                        await self.status_msg.edit_text(text, parse_mode="Markdown")
                    self._last_sent_text = text
                    self._last_sent_at = now

                if sig == "stop":
                    break
        except asyncio.CancelledError:
            pass
        except Exception:  # noqa: BLE001
            logger.exception("ProgressReporter._pump упал")

    # ─── Утилиты форматирования ───────────────────────────────────────────────
    @staticmethod
    def _fmt_speed(bps: float) -> str:
        if bps <= 0:
            return "—"
        if bps > 1024 * 1024:
            return f"{bps / 1024 / 1024:.1f} MB/s"
        if bps > 1024:
            return f"{bps / 1024:.0f} KB/s"
        return f"{bps:.0f} B/s"

    @staticmethod
    def _fmt_eta(sec: float) -> str:
        if not sec or sec < 0:
            return "—"
        sec = int(sec)
        if sec > 3600:
            return f"{sec // 3600}h {(sec % 3600) // 60}m"
        if sec > 60:
            return f"{sec // 60}m {sec % 60}s"
        return f"{sec}s"
