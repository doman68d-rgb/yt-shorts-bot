"""
services/downloader.py
~~~~~~~~~~~~~~~~~~~~~~

Модуль скачивания видео по ссылке через yt-dlp.

Что делает:
    1. Принимает URL (YouTube, VK, Rutube и т.д. — всё, что поддерживает yt-dlp).
    2. Выбирает «безопасный» формат: mp4 + m4a, либо лучший единый файл,
       если раздельных потоков нет (например, для Shorts).
    3. Сохраняет в DOWNLOADS_DIR с уникальным ID в имени файла, чтобы
       параллельные пользователи не затирали друг друга.
    4. На выходе возвращает абсолютный Path к скачанному файлу и метаданные.

Использование из bot.py (через asyncio.to_thread, потому что yt-dlp синхронный):
    path, meta = await asyncio.to_thread(download_video, url, job_id="abc123")

Вне aiogram можно просто:
    path, meta = download_video("https://youtu.be/...")
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yt_dlp

from config import settings
from utils.helpers import resolve_ffmpeg_location

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Исключения домена
# ──────────────────────────────────────────────────────────────────────────────
class DownloadError(Exception):
    """Базовая ошибка модуля downloader."""


class InvalidURLError(DownloadError):
    """Ссылка пустая или явно битая."""


class VideoUnavailableError(DownloadError):
    """Видео не существует / приватное / недоступно в регионе."""


# ──────────────────────────────────────────────────────────────────────────────
# Модель результата
# ──────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class DownloadResult:
    """То, что вернёт download_video(). Неизменяемый (frozen) для безопасности."""

    file_path: Path          # путь к скачанному файлу
    title: str               # название видео
    duration: float          # длительность в секундах
    uploader: Optional[str]  # автор канала (может быть None)
    source_url: str          # исходный URL (для логов)


# ──────────────────────────────────────────────────────────────────────────────
# Вспомогательные функции
# ──────────────────────────────────────────────────────────────────────────────
def _sanitize_filename(name: str, max_len: int = 80) -> str:
    """
    Удалить/заменить символы, запрещённые в Windows/macOS именах файлов.
    Ограничить длину, чтобы не упёрться в 260 символов на Windows.
    """
    # Запрещённые в Windows: <>:"/\|?*  и управляющие символы 0x00-0x1F
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    # Схлопываем повторяющиеся подчёркивания и пробелы по краям
    name = re.sub(r"_+", "_", name).strip(" ._")
    return (name[:max_len] or "video").rstrip(".")


def _validate_url(url: str) -> None:
    """Проверить, что url похож на http(s)-ссылку. Иначе — InvalidURLError."""
    if not url or not isinstance(url, str):
        raise InvalidURLError("Пустая ссылка.")
    url = url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        raise InvalidURLError(
            f"Ссылка должна начинаться с http(s)://. Получил: {url!r}"
        )


# ──────────────────────────────────────────────────────────────────────────────
# Главная функция модуля
# ──────────────────────────────────────────────────────────────────────────────
def download_video(
    url: str,
    job_id: str,
    progress_hook=None,
) -> DownloadResult:
    """
    Скачать видео по URL. Блокирующая (синхронная) функция!

    Параметры:
        url          — ссылка на видео.
        job_id       — уникальный идентификатор задачи (например, короткий uuid).
                       Используется как префикс имени файла, чтобы параллельные
                       скачивания не конфликтовали.
        progress_hook — (опционально) колбэк вида `fn(d: dict)`, который yt-dlp
                       дёргает на каждом этапе скачивания. Используется для
                       прогресс-бара.

    Возвращает:
        DownloadResult с путём к файлу и метаданными.

    Бросает:
        InvalidURLError      — кривая ссылка.
        VideoUnavailableError — видео недоступно.
        DownloadError        — любая другая ошибка yt-dlp.
    """
    _validate_url(url)

    # Шаблон имени файла. %(ext)s подставится yt-dlp автоматически.
    # Уникальный job_id — главная защита от «перезаписал чужой файл».
    out_template = str(settings.DOWNLOADS_DIR / f"{job_id}_%(title)s.%(ext)s")

    # Подсказываем yt-dlp путь к ffmpeg: сначала bundled (imageio_ffmpeg),
    # потом системный из PATH. Без этого yt-dlp не сможет смерджить
    # раздельные видео и аудио в один .mp4.
    ffmpeg_loc = resolve_ffmpeg_location()

    # Опции yt-dlp.
    # ─────────────────────────────────────────────────────────────────────
    # format: берём прогрессивный mp4 (видео+аудио в одном файле).
    #         Если такого нет (например, клипы VK), отдадим лучший единый файл
    #         через "best[ext=mp4]/best". Это безопаснее, чем отдельно
    #         скачивать video и audio и потом мерджить ffmpeg-ом.
    # quiet=True / no_warnings=True — гасим спам в консоль, но нужные ошибки
    #                                    мы всё равно поймаем через try/except.
    # outtmpl — наш шаблон имени.
    # noplaylist=True — если кинут плейлист, скачаем только одно видео, иначе
    #                   yt-dlp попытается качать всё и утопит диск.
    # ─────────────────────────────────────────────────────────────────────
    ydl_opts = {
        "format": "bv*[height<=720]+ba/best[height<=720]/best",
        "outtmpl": out_template,
        "ffmpeg_location": ffmpeg_loc,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "merge_output_format": "mp4",
        "retries": 3,                    # авто-повторы при сетевых ошибках
        "fragment_retries": 3,
        "ignoreerrors": False,
    }
    if progress_hook is not None:
        ydl_opts["progress_hooks"] = [progress_hook]

    logger.info("▶ download start: url=%s job_id=%s", url, job_id)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Сначала пробуем достать только метаданные (быстро), чтобы
            # понять, что видео вообще существует. Если не получится —
            # не потратим трафик на скачивание.
            try:
                info = ydl.extract_info(url, download=False)
            except yt_dlp.utils.DownloadError as exc:
                msg = str(exc).lower()
                if any(k in msg for k in ("private video", "unavailable", "not found",
                                          "доступ к видео", "видео недоступно",
                                          "video unavailable", "sign in")):
                    raise VideoUnavailableError(
                        "Видео недоступно (приватное / удалено / региональная блокировка)."
                    ) from exc
                raise

            # Теперь само скачивание.
            # Если info — это плейлист (по идее noplaylist=True этого не пустит,
            # но на всякий случай), берём первый элемент.
            if "entries" in info and info["entries"]:
                info = info["entries"][0]

            file_path_str = ydl.prepare_filename(info)

            # Скачиваем, если файл ещё не на диске (повторный вызов с тем же job_id).
            file_path = Path(file_path_str)
            if not file_path.exists():
                # Стандартный download yt-dlp сам переиспользует полученный
                # info из кэша ключевых операций, поэтому повторно extract_info
                # не выполняется — сеть бьётся ровно один раз.
                ydl.download([url])

            if not file_path.exists():
                raise DownloadError(
                    f"yt-dlp отработал, но файл {file_path} не найден."
                )

            # Склеиваем результат.
            result = DownloadResult(
                file_path=file_path.resolve(),
                title=info.get("title", "video"),
                duration=float(info.get("duration") or 0.0),
                uploader=info.get("uploader") or info.get("channel"),
                source_url=url,
            )

            logger.info(
                "✔ download done: %s (%.1f MB, %.1f sec)",
                result.file_path.name,
                result.file_path.stat().st_size / 1024 / 1024,
                result.duration,
            )
            return result

    except VideoUnavailableError:
        raise  # уже «наша» ошибка, не оборачиваем
    except InvalidURLError:
        raise
    except yt_dlp.utils.DownloadError as exc:
        raise DownloadError(f"yt-dlp: {exc}") from exc
    except Exception as exc:  # noqa: BLE001 — ловим всё непредвиденное
        logger.exception("Неизвестная ошибка скачивания")
        raise DownloadError(f"Неожиданная ошибка: {exc}") from exc


# ──────────────────────────────────────────────────────────────────────────────
# Быстрый CLI-тест
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Позволяет проверить модуль автономно: `python -m services.downloader <URL>`
    import sys
    import uuid

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if len(sys.argv) < 2:
        print("Использование: python -m services.downloader <URL>")
        sys.exit(1)

    test_url = sys.argv[1]
    test_job = uuid.uuid4().hex[:8]

    try:
        r = download_video(test_url, job_id=test_job)
        print("\n✅ Скачано:")
        print(f"  путь:      {r.file_path}")
        print(f"  название:  {r.title}")
        print(f"  длительность: {r.duration:.1f} сек")
        print(f"  автор:     {r.uploader}")
    except DownloadError as e:
        print(f"\n❌ Ошибка: {e}")
        sys.exit(2)
