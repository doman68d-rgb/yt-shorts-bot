"""
bot/pipeline.py
~~~~~~~~~~~~~~~

Основной конвейер обработки видео.

Поток:
    1. Скачивание         (services.downloader, с прогрессом)
    2. Транскрибация      (services.transcriber, с прогрессом)
    3. Выбор моментов     (services.highlights: LLM или random)
    4. Нарезка клипов     (services.editor, с прогрессом)
    5. Отправка видео
    6. Очистка временных файлов

Каждый шаг в try/except — падение одного клипа не валит остальные.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from pathlib import Path

from aiogram.types import FSInputFile, Message

from bot.formatters import clip_range, escape
from bot.messages import safe_delete, safe_send
from bot.prefs import get_prefs
from config import settings
from services.downloader import (
    DownloadError,
    DownloadResult,
    InvalidURLError,
    VideoUnavailableError,
    download_video,
)
from services.editor import EditorError, make_clips
from services.highlights import pick_highlights
from services.progress import ProgressReporter
from services.transcriber import TranscriptionError, transcribe_video
from utils.helpers import cleanup_job, human_bytes, make_job_id

logger = logging.getLogger(__name__)


async def run_pipeline(
    message: Message,
    status_msg: Message,
    url: str,
    chat_id: int,
) -> None:
    """Полный цикл обработки одного видео."""
    job_id = make_job_id()
    bot = message.bot
    prefs = get_prefs(chat_id)

    downloaded_path: Path | None = None
    clip_paths: list[Path] = []
    transcript = None

    async with ProgressReporter(bot, status_msg) as reporter:
        try:
            # ─── ШАГ 1: СКАЧИВАНИЕ ────────────────────────────────────────────
            reporter.set_step("downloading", "⬇️ Скачиваю видео…", 0)
            try:
                result: DownloadResult = await asyncio.to_thread(
                    download_video, url, job_id,
                    progress_hook=reporter.yt_dlp_update,
                )
            except InvalidURLError:
                await safe_send(bot, chat_id, "❌ Ссылка битая. Проверь и пришли ещё раз 🙏")
                await safe_delete(status_msg)
                return
            except VideoUnavailableError:
                await safe_send(
                    bot, chat_id,
                    "🚫 Видео недоступно (приватное / удалено / региональная блокировка).\n"
                    "Попробуй другое видео.",
                )
                await safe_delete(status_msg)
                return
            except DownloadError as exc:
                logger.exception("Ошибка скачивания")
                await safe_send(bot, chat_id, f"😵 Не удалось скачать видео:\n{exc}")
                await safe_delete(status_msg)
                return

            downloaded_path = result.file_path
            size_str = human_bytes(downloaded_path.stat().st_size)

            reporter.set_step(
                "downloading",
                f"✅ Скачал «{escape(result.title)}» ({size_str})",
                50.0,
            )

            # ─── ШАГ 2: ТРАНСКРИБАЦИЯ ─────────────────────────────────────────
            reporter.set_step("transcribing", "🎧 Whisper запускается…", 50.0)
            try:
                transcript = await asyncio.to_thread(
                    transcribe_video,
                    downloaded_path,
                    progress_callback=reporter.whisper_update,
                )
            except TranscriptionError as exc:
                logger.warning("Whisper упал: %s", exc)
                await safe_send(
                    bot, chat_id,
                    f"⚠️ Скачал видео, но распознать речь не получилось:\n{exc}\n"
                    f"Если в видео нет речи — это ожидаемо.\n"
                    f"Продолжаю обработку без транскрипта…",
                )
                transcript = None

            # ─── ШАГ 3: ВЫБОР МОМЕНТОВ ────────────────────────────────────────
            reporter.set_step(
                "highlights",
                "🧠 LLM-выбор моментов…" if prefs.strategy == "smart" else "🎲 Random: выбираю моменты…",
                85.0,
            )
            await asyncio.sleep(0.05)  # дать сообщению отрисоваться

            try:
                ranges, strategy_used = pick_highlights(
                    transcript=transcript,
                    total_duration=result.duration,
                    clip_count=prefs.clip_count,
                    clip_duration=prefs.clip_duration,
                    skip_edges_percent=int(settings.SKIP_EDGES_PERCENT),
                    prefer_llm=(prefs.strategy == "smart"),
                )
            except Exception as exc:
                logger.exception("Ошибка выбора моментов")
                await safe_send(bot, chat_id, f"🧠 Не удалось выбрать моменты:\n{exc}")
                await safe_delete(status_msg)
                return

            if not ranges:
                await safe_send(bot, chat_id, "⚠️ Не получилось выбрать ни одного момента.")
                await safe_delete(status_msg)
                return

            # ─── ШАГ 4: НАРЕЗКА ──────────────────────────────────────────────
            try:
                clip_paths = await asyncio.to_thread(
                    make_clips,
                    video_path=downloaded_path,
                    ranges=ranges,
                    job_id=job_id,
                    progress_hook=reporter.ffmpeg_update,
                )
            except EditorError as exc:
                logger.exception("Ошибка монтажа")
                await safe_send(bot, chat_id, f"🎬 Не удалось нарезать клипы:\n{exc}")
                await safe_delete(status_msg)
                return

            # ─── ШАГ 5: ОТПРАВКА ──────────────────────────────────────────────
            reporter.set_step(
                "sending",
                f"📤 Отправляю {len(clip_paths)} клип(ов)…",
                99.0,
            )

            sent = 0
            for i, clip_path in enumerate(clip_paths, start=1):
                cap = (
                    f"📹 Клип {i}/{len(clip_paths)}\n"
                    f"⏱ {clip_range(ranges[i-1])}\n"
                    f"📦 {human_bytes(clip_path.stat().st_size)}\n"
                    f"🧠 Стратегия: {strategy_used}"
                )
                try:
                    await message.answer_video(
                        video=FSInputFile(str(clip_path), filename=clip_path.name),
                        caption=cap,
                        supports_streaming=True,
                    )
                    sent += 1
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Не удалось отправить клип %s", clip_path)
                    await safe_send(
                        bot, chat_id,
                        f"⚠️ Клип {i} не отправился: {exc}",
                    )

            reporter.done()

            if sent == 0:
                await safe_send(bot, chat_id, "😔 Не удалось отправить ни одного клипа.")
            else:
                await safe_send(
                    bot, chat_id,
                    f"✨ Готово! Отправил {sent} из {len(clip_paths)} клипов "
                    f"(стратегия: {'🧠 LLM' if strategy_used == 'llm' else '🎲 Random'}).",
                )

        except Exception as exc:  # noqa: BLE001
            reporter.fail(str(exc)[:100])
            logger.exception("Неизвестная ошибка пайплайна")
            with contextlib.suppress(Exception):
                await safe_send(
                    bot, chat_id,
                    f"💥 Что-то пошло совсем не так:\n{exc}\n\n"
                    f"Логи сохранены. Попробуй ещё раз чуть позже.",
                )

        finally:
            await safe_delete(status_msg)
            cleanup_job(
                downloads_files=[downloaded_path] if downloaded_path else [],
                clips_files=clip_paths,
            )
