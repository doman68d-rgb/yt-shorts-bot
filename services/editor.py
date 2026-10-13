"""
services/editor.py
~~~~~~~~~~~~~~~~~~

Модуль нарезки длинных видео в вертикальные клипы (Shorts / TikTok / Reels).

Пайплайн:
    1. На вход: Path к скачанному видео + (опционально) TranscriptResult.
    2. На Шаге 6 (MVP) TranscriptResult НЕ используется для выбора моментов —
       мы делаем упрощённый алгоритм:
            • отсекаем по SKIP_EDGES_PERCENT с каждого края (без интро/аутро);
            • делим «середину» на кусочки и берём CLIP_COUNT случайных.
       Позже этот же модуль заменим на «умный» выбор по таймингам речи.
    3. Режем клипы через moviepy.
    4. Кадрируем в 9:16 через ffmpeg-subprocess (быстрее и стабильнее, чем
       moviepy-ресайз — moviepy тянет целый файл в RAM, ffmpeg стримит).

⚠️ Тяжёлые синхронные функции. Вызывать через asyncio.to_thread()!

Использование:
    clip_paths = await asyncio.to_thread(
        make_clips,
        video_path=video_path,
        duration=video_duration,
        job_id="abc123",
        transcript=transcript,  # опционально, MVP игнорирует
    )
"""

from __future__ import annotations

import contextlib
import logging
import random
import subprocess
from dataclasses import dataclass
from pathlib import Path

from moviepy.video.io.VideoFileClip import VideoFileClip  # type: ignore

from config import settings
from services.transcriber import _find_ffmpeg

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Исключения
# ──────────────────────────────────────────────────────────────────────────────
class EditorError(Exception):
    """Базовая ошибка монтажа."""


class InvalidClipRangeError(EditorError):
    """Плохо посчитанные временные рамки (например, после обрезки осталось меньше, чем нужно)."""


class VideoProcessingError(EditorError):
    """ffmpeg/ffprobe упал при обработке."""


# ──────────────────────────────────────────────────────────────────────────────
# Модели данных
# ──────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class ClipRange:
    """Тайминги одного клипа в исходном видео (секунды)."""
    index: int          # 1, 2, 3 — порядковый номер клипа
    start: float
    end: float

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass(frozen=True)
class ClipResult:
    """Готовый файл клипа."""
    file_path: Path
    range: ClipRange


# ──────────────────────────────────────────────────────────────────────────────
# Утилиты для ffmpeg
# ──────────────────────────────────────────────────────────────────────────────
def _clip_video_to_vertical(
    src: Path,
    dst: Path,
    start: float,
    end: float,
) -> Path:
    """
    Вырезать фрагмент [start, end] из src, масштабировать в целевое
    вертикальное разрешение (1080x1920) одним вызовом ffmpeg.

    Стратегия:
        - Берём фильтр `crop=ih*9/16:ih` — из исходного кадра вырезаем
          центральный вертикальный кусок с соотношением 9:16.
          Это самый простой способ получить вертикаль из горизонтали:
          ширина = высота * 9/16. Высота остаётся как есть.
        - Дальше `scale=1080:1920:flags=lanczos` — растягиваем в целевой
          размер (с качественным ресэмплингом).
        - `-ss` ДО `-i` = быстрый seek (без перекодирования исходника).
        - `-ss` ПОСЛЕ `-i` = точный seek (с перекодированием).
          Нам нужен точный, поэтому `-ss` ставим ДО входного фильтра, но
          используем `-noaccurate_seek` нет — у moviepy/ffmpeg точный seek
          по умолчанию. Для стабильности ставим `-ss` ДО `-i`, а для
          точности указываем `-avoid_negative_ts make_zero`.
    """
    ffmpeg_bin = _find_ffmpeg()
    target_w, target_h = settings.CLIP_WIDTH, settings.CLIP_HEIGHT
    duration = max(0.1, end - start)

    # Логика фильтра:
    #   crop=ih*9/16:ih:0           → центр. вертикальный 9:16
    #   scale=W:H:flags=lanczos     → целевое разрешение
    vf = f"crop=ih*9/16:ih,scale={target_w}:{target_h}:flags=lanczos,setsar=1"

    cmd = [
        ffmpeg_bin,
        "-hide_banner", "-loglevel", "error",
        "-y",                              # перезаписать
        "-ss", f"{start:.3f}",             # старт (секунды)
        "-i", str(src),                    # входной файл
        "-t", f"{duration:.3f}",           # длительность фрагмента
        "-vf", vf,                         # фильтр кадрирования+масштаба
        "-c:v", "libx264",                 # кодек видео — H.264 (нужно для Telegram)
        "-preset", "medium",               # баланс скорость/качество
        "-crf", "20",                      # качество (меньше = лучше; 18-23 норм)
        "-pix_fmt", "yuv420p",             # совместимость с плеерами
        "-c:a", "aac",                     # аудио в AAC (Telegram его понимает)
        "-b:a", "128k",                    # битрейт аудио
        "-movflags", "+faststart",         # метаданные в начале → Telegram стримит
        "-threads", "0",                   # ffmpeg сам выберет число потоков CPU
        str(dst),
    ]

    logger.info(
        "▶ ffmpeg clip %d: [%.1f–%.1f] → %s",
        dst.name,
        start,
        end,
        dst.name,
    )

    try:
        subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=900,  # 15 минут на один клип (на длинных исходниках)
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip().splitlines()
        # берём последние полезные строки stderr
        tail = "\n".join(stderr[-8:]) if stderr else "(нет stderr)"
        logger.error("ffmpeg error:\n%s", tail)
        raise VideoProcessingError(
            f"ffmpeg не смог обработать клип: {tail}"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise VideoProcessingError(
            "ffmpeg превысил лимит 15 минут при обработке клипа."
        ) from exc

    if not dst.exists() or dst.stat().st_size < 1000:
        raise VideoProcessingError(
            f"ffmpeg отработал, но клип пустой/слишком маленький: {dst}"
        )

    return dst


# ──────────────────────────────────────────────────────────────────────────────
# Выбор моментов (MVP — случайный из «середины»)
# ──────────────────────────────────────────────────────────────────────────────
def _random_clip_ranges(
    total_duration: float,
    clip_length: float = 45.0,
    count: int = 3,
    skip_edges_percent: int = 10,
    rng: random.Random | None = None,
) -> list[ClipRange]:
    """
    Выбрать `count` стартовых точек для клипов длиной `clip_length` секунд,
    исключая первые и последние skip_edges_percent процентов видео.

    Пример:
        duration = 1000s, clip = 45s, count = 3, skip = 10%
        «Середина» = [100s, 900s] → 800s доступно, 45s клип влезает.
        Выбираем 3 случайных старта в [100, 855].

    Если видео короткое и клипы не влезают — подгоняем:
        • Уменьшаем clip_length до безопасного значения.
        • Если всё равно не влезает — кидаем InvalidClipRangeError.
    """
    if total_duration <= 0:
        raise InvalidClipRangeError(f"Нулевая длительность видео: {total_duration}")

    rng = rng or random.Random()

    edges = max(0.0, total_duration * skip_edges_percent / 100.0)
    safe_start = edges
    safe_end = total_duration - edges

    if safe_end - safe_start <= 0:
        raise InvalidClipRangeError(
            f"Видео слишком короткое для {skip_edges_percent}% отступов: "
            f"длительность {total_duration:.1f}s, безопасная зона нулевая."
        )

    # Доступная «длина» — куда можно поместить клип.
    available = safe_end - safe_start
    actual_clip_length = min(clip_length, available)

    # Если клип короче оригинала, можно поставить count стартов вплотную.
    # Но для разнообразия всё равно выбираем случайные.
    if available <= actual_clip_length:
        # Нет запаса — поставим один клип в центре и больше ничего не нарежем.
        (safe_start + safe_end) / 2
    else:
        # Случайно выбираем старты, но «уплотняем» — не даём двум клипам
        # пересекаться по времени. Используем «сетку» возможных позиций.
        min_step = actual_clip_length  # минимальный зазор между клипами
        if min_step * count > available:
            # Клипы не помещаются без перекрытия — уменьшим их количество
            # ровно до того, которое влезает.
            count = max(1, int(available // min_step))

        # Генерируем старты внутри [safe_start, safe_end - clip_length].
        max_start = safe_end - actual_clip_length
        possible = list(np_linspace(safe_start, max_start, num=50))  # равномерная сетка
        # если 50 точек не помещается (короткое видео) — берём все точки
        chosen_starts: list[float] = []
        last_end = -1e9
        for _ in range(count):
            candidates = [s for s in possible if s >= last_end + min_step]
            if not candidates:
                # Fallback: снимаем ограничение непересечения.
                candidates = possible[:]
            s = rng.choice(candidates)
            chosen_starts.append(s)
            last_end = s + actual_clip_length
            # не даём сетке «уплыть» за пределы
            possible = [p for p in possible if p >= s]

    # Сортируем по времени для удобства восприятия клипов пользователем.
    chosen_starts.sort()
    return [
        ClipRange(index=i + 1, start=s, end=s + actual_clip_length)
        for i, s in enumerate(chosen_starts)
    ]


def np_linspace(start: float, stop: float, num: int) -> list[float]:
    """Мини-linspace, чтобы не тащить numpy для пары чисел."""
    if num <= 1:
        return [start]
    step = (stop - start) / (num - 1)
    return [start + step * i for i in range(num)]


# ──────────────────────────────────────────────────────────────────────────────
# Главная функция модуля
# ──────────────────────────────────────────────────────────────────────────────
def make_clips(
    video_path: Path,
    ranges: list[ClipRange],
    job_id: str,
    progress_hook=None,
) -> list[Path]:
    """
    Создать клипы по готовым диапазонам.

    Параметры:
        video_path   — путь к скачанному длинному видео.
        ranges       — список ClipRange (тайминги, которые нужно нарезать).
                       Откуда они пришли — не наше дело (рандом / LLM / руками).
        job_id       — уникальный ID задачи (для именования файлов).
        progress_hook — (опционально) fn(clip_index: int, total_clips: int).

    Возвращает:
        Список Path к готовым клипам в CLIPS_DIR.

    Бросает:
        EditorError / InvalidClipRangeError / VideoProcessingError.
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise EditorError(f"Файл видео не найден: {video_path}")

    if not ranges:
        raise InvalidClipRangeError(
            "Список диапазонов пуст. Проверь выбор моментов."
        )

    logger.info(
        "Нарезаем %d клип(ов) из %s",
        len(ranges), video_path.name,
    )
    for r in ranges:
        logger.info("   #%d [%.1f → %.1f] (%.1fs)", r.index, r.start, r.end, r.duration)

    # Moviepy используем ТОЛЬКО для проверки, что файл «открывается».
    # Реальную нарезку делает ffmpeg — он в разы быстрее и не жрёт RAM.
    try:
        with VideoFileClip(str(video_path)) as probe:
            probed_duration = probe.duration
            logger.info(
                "moviepy probe OK: %s → %.2fs",
                video_path.name,
                probed_duration,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("moviepy не смог открыть видео (это не критично): %s", exc)

    # 2. Нарезаем каждый диапазон. Падение одного не валит остальные.
    results: list[Path] = []

    total = len(ranges)
    for i, r in enumerate(ranges, start=1):
        out_name = f"{job_id}_clip_{r.index:02d}.mp4"
        out_path = settings.CLIPS_DIR / out_name

        if progress_hook is not None:
            with contextlib.suppress(Exception):
                progress_hook(i, total)

        try:
            _clip_video_to_vertical(
                src=video_path,
                dst=out_path,
                start=r.start,
                end=r.end,
            )
            results.append(out_path)
        except VideoProcessingError as exc:
            logger.error("Пропускаю клип #%d: %s", r.index, exc)
            continue

    if not results:
        raise EditorError(
            "Не удалось создать ни одного клипа. Скорее всего, видео повреждено "
            "или ffmpeg не справился с кодеком."
        )

    logger.info("✔ Готово %d/%d клипов", len(results), len(ranges))
    return results


# ──────────────────────────────────────────────────────────────────────────────
# CLI-тест
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if len(sys.argv) < 2:
        print("Использование: python -m services.editor <video.mp4> [duration_sec]")
        sys.exit(1)

    p = Path(sys.argv[1])
    if not p.exists():
        print(f"❌ Файл не найден: {p}")
        sys.exit(1)

    try:
        with VideoFileClip(str(p)) as probe:
            dur = float(probe.duration)
    except Exception:
        dur = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0

    print(f"Исходник: {p}")
    print(f"Длительность: {dur:.1f}s")

    from services.highlights import pick_highlights_random

    ranges = pick_highlights_random(
        total_duration=dur,
        clip_count=int(settings.CLIP_COUNT),
        clip_duration=float(settings.CLIP_DURATION),
        skip_edges_percent=int(settings.SKIP_EDGES_PERCENT),
    )

    try:
        clips = make_clips(p, ranges=ranges, job_id="cli_test")
        print(f"\n✅ Создано {len(clips)} клипов:")
        for c in clips:
            size_mb = c.stat().st_size / 1024 / 1024
            print(f"  • {c.name} ({size_mb:.2f} MB)")
    except EditorError as e:
        print(f"\n❌ Ошибка: {e}")
        sys.exit(2)
