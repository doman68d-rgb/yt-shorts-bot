"""
utils/helpers.py
~~~~~~~~~~~~~~~

Маленькие вспомогательные функции: генерация ID, чистка временных файлов,
удаление одного файла без падений.

Идея: всё, что нужно в нескольких местах проекта, но не тянет на целый модуль.
"""

from __future__ import annotations

import logging
import os
import shutil
import uuid
from collections.abc import Iterable
from pathlib import Path

from config import settings

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Генерация идентификаторов
# ──────────────────────────────────────────────────────────────────────────────
def make_job_id() -> str:
    """
    Короткий уникальный ID задачи (8 hex-символов).
    Используется как префикс файлов в downloads/ и clips/ — чтобы параллельные
    пользователи не перетирали файлы друг друга.
    """
    return uuid.uuid4().hex[:8]


# ──────────────────────────────────────────────────────────────────────────────
# Безопасное удаление файлов и папок
# ──────────────────────────────────────────────────────────────────────────────
def safe_remove(path: Path | str | None) -> bool:
    """
    Удалить файл без падения. Возвращает True, если что-то удалили.
    • Не падает, если файла нет.
    • Не падает, если нет прав (только логирует).
    • Папки не удаляет — для папок есть safe_rmtree().
    """
    if path is None:
        return False
    p = Path(path)
    if not p.exists():
        return False
    if p.is_dir():
        logger.warning("safe_remove получил директорию, использую safe_rmtree: %s", p)
        return safe_rmtree(p)
    try:
        p.unlink()
        logger.info("🗑 удалён файл: %s", p.name)
        return True
    except OSError as exc:
        logger.warning("Не удалось удалить %s: %s", p, exc)
        return False


def safe_rmtree(path: Path | str | None) -> bool:
    """Удалить папку (рекурсивно) со всем содержимым без падения."""
    if path is None:
        return False
    p = Path(path)
    if not p.exists():
        return False
    try:
        shutil.rmtree(p)
        logger.info("🗑 удалена папка: %s", p)
        return True
    except OSError as exc:
        logger.warning("Не удалось удалить папку %s: %s", p, exc)
        return False


def cleanup_job(
    downloads_files: Iterable[Path | str] = (),
    clips_files: Iterable[Path | str] = (),
) -> dict:
    """
    Массовая очистка временных файлов после выполнения задачи.
    Возвращает статистику для логов.
    """
    deleted_files = 0
    deleted_bytes = 0

    for f in (*downloads_files, *clips_files):
        p = Path(f)
        if p.exists() and p.is_file():
            try:
                size = p.stat().st_size
                p.unlink()
                deleted_files += 1
                deleted_bytes += size
            except OSError:
                pass

    if deleted_files:
        logger.info(
            "🧹 cleanup_job: удалено %d файлов, %.1f MB освобождено",
            deleted_files,
            deleted_bytes / 1024 / 1024,
        )

    return {"files": deleted_files, "bytes": deleted_bytes}


def wipe_temp_dirs() -> None:
    """
    Стереть старые временные файлы из DOWNLOADS_DIR / CLIPS_DIR.
    Полезно запускать на старте бота, чтобы не накапливать мусор
    после прошлых сессий.
    """
    for folder in (settings.DOWNLOADS_DIR, settings.CLIPS_DIR):
        if not folder.exists():
            continue
        count = 0
        bytes_ = 0
        for p in folder.iterdir():
            try:
                if p.is_file():
                    bytes_ += p.stat().st_size
                    p.unlink()
                    count += 1
                elif p.is_dir():
                    shutil.rmtree(p)
                    count += 1
            except OSError:
                pass
        if count:
            logger.info(
                "wipe_temp_dirs[%s]: удалено %d файлов (%.1f MB)",
                folder.name,
                count,
                bytes_ / 1024 / 1024,
            )


# ──────────────────────────────────────────────────────────────────────────────
# Прочие мелочи
# ──────────────────────────────────────────────────────────────────────────────
def human_bytes(n: int | float) -> str:
    """Человекочитаемый размер: 1024 → '1.0 KB'."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def is_youtube_url(url: str) -> bool:
    """Грубая проверка, что URL похож на YouTube (для подсказок пользователю)."""
    if not url:
        return False
    u = url.lower()
    return any(host in u for host in ("youtube.com", "youtu.be", "youtube-nocookie.com"))


# Размер файла через Path.
def file_size(path: Path | str) -> int | None:
    p = Path(path)
    try:
        return p.stat().st_size if p.exists() else None
    except OSError:
        return None


def resolve_ffmpeg_location() -> str | None:
    """
    Найти путь к ffmpeg для yt-dlp (например, bundled из imageio_ffmpeg).
    Возвращает строковый путь или None, если ffmpeg нет.
    yt-dlp понимает и строковый путь, и директорию, и None (тогда ищет сам в PATH).
    """
    try:
        import imageio_ffmpeg  # type: ignore

        bundled = imageio_ffmpeg.get_ffmpeg_exe()
        if bundled and Path(bundled).exists():
            return bundled
    except ImportError:
        pass

    sys_ffmpeg = shutil.which("ffmpeg")
    return sys_ffmpeg  # None если не найден


# Подавить access_log у aiohttp (используется внутри aiogram), чтобы лог
# не засорялся GET-запросами к Telegram-серверу.
def silence_aiohttp_log() -> None:
    for noisy in ("aiohttp.access", "aiohttp.client", "aiohttp.internal"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


# Можно использовать как удобный рантайм-гард:
# в некоторых окружениях asynckit/asyncio возмущаются на не-utf-вывод.
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
