"""
services/transcriber.py
~~~~~~~~~~~~~~~~~~~~~~~

Модуль транскрибации видео в текст с временными метками через faster-whisper.

Что делает:
    1. Принимает Path к видеофайлу.
    2. Извлекает аудио через ffmpeg во временный .wav (faster-whisper
       работает с m4a/mp3/wav/flac — нам .wav гарантирует корректное чтение).
    3. Прогоняет через модель faster-whisper, получая сегменты с временами.
    4. Возвращает список сегментов (start, end, text) + общий текст.

⚠️ Тяжёлая синхронная функция! Должна вызываться через asyncio.to_thread().

Использование:
    transcript = await asyncio.to_thread(transcribe_video, video_path)

    for seg in transcript.segments:
        print(f"[{seg.start:.1f}–{seg.end:.1f}] {seg.text}")
"""

from __future__ import annotations

import contextlib
import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

# faster-whisper загружается лениво — чтобы падение установки
# не валило весь бот при импорте.
from faster_whisper import WhisperModel  # type: ignore

from config import settings

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Исключения
# ──────────────────────────────────────────────────────────────────────────────
class TranscriptionError(Exception):
    """Базовая ошибка транскрибации."""


class AudioExtractionError(TranscriptionError):
    """Не удалось извлечь аудио из видео."""


class FFmpegNotFoundError(TranscriptionError):
    """FFmpeg не найден в системе."""


# ──────────────────────────────────────────────────────────────────────────────
# Модели данных
# ──────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class TranscriptSegment:
    """Один фрагмент речи с временными метками (секунды)."""

    start: float
    end: float
    text: str

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass(frozen=True)
class TranscriptResult:
    """Полный результат транскрибации видео."""

    language: str  # определённый язык (например, "ru")
    full_text: str  # склеенный текст всех сегментов
    segments: list[TranscriptSegment] = field(default_factory=list)
    audio_path: Path | None = None  # путь к .wav (если не удалили)
    title: str = ""  # название видео (для LLM-промпта)


# ──────────────────────────────────────────────────────────────────────────────
# FFmpeg helpers
# ──────────────────────────────────────────────────────────────────────────────
def _find_ffmpeg() -> str:
    """
    Найти путь к бинарю ffmpeg. Приоритет:
        1. imageio-ffmpeg (часто ставится как зависимость moviepy — ffmpeg в комплекте).
        2. Системный ffmpeg из PATH.
    Если не нашли — бросаем FFmpegNotFoundError.
    """
    # Способ 1: imageio-ffmpeg (bundled binary, удобно для Windows).
    try:
        import imageio_ffmpeg  # type: ignore

        bundled = imageio_ffmpeg.get_ffmpeg_exe()
        if bundled and Path(bundled).exists():
            logger.info("Используем bundled ffmpeg: %s", bundled)
            return bundled
    except ImportError:
        pass

    # Способ 2: системный ffmpeg.
    sys_ffmpeg = shutil.which("ffmpeg")
    if sys_ffmpeg:
        logger.info("Используем системный ffmpeg: %s", sys_ffmpeg)
        return sys_ffmpeg

    raise FFmpegNotFoundError(
        "❌ FFmpeg не найден.\n"
        "👉 Установи ffmpeg и добавь в PATH:\n"
        "   • Windows: скачай сборку https://www.gyan.dev/ffmpeg/builds/\n"
        "                и распакуй, добавив bin/ в PATH.\n"
        "   • Linux:   sudo apt install ffmpeg\n"
        "   • macOS:   brew install ffmpeg\n"
        "Или перезапусти бота — он может найти bundled ffmpeg из imageio-ffmpeg."
    )


def extract_audio(video_path: Path, output_path: Path) -> Path:
    """
    Извлечь аудио из видео в 16kHz mono WAV.

    Зачем именно 16 kHz / mono / WAV:
        faster-whisper внутри CTranslate2 жуёт 16 kHz mono float32.
        Если скармливать ему mp3/m4a — он сам сделает ресемплинг,
        но это тратит время и память. Лучше сразу подготовить.
    """
    ffmpeg_bin = _find_ffmpeg()

    cmd = [
        ffmpeg_bin,
        "-hide_banner",
        "-loglevel",
        "error",  # без спама в консоль
        "-y",  # перезаписать выход
        "-i",
        str(video_path),  # вход
        "-vn",  # без видео
        "-ac",
        "1",  # mono
        "-ar",
        "16000",  # 16 kHz
        "-f",
        "wav",  # формат
        str(output_path),
    ]

    logger.info("ffmpeg audio extract: %s → %s", video_path.name, output_path.name)
    try:
        subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=600,  # 10 минут максимум на извлечение аудио
        )
    except subprocess.CalledProcessError as exc:
        raise AudioExtractionError(
            f"ffmpeg не смог извлечь аудио: {exc.stderr.strip() or exc}"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise AudioExtractionError(
            f"ffmpeg превысил лимит 10 минут при извлечении аудио: {exc}"
        ) from exc

    if not output_path.exists() or output_path.stat().st_size < 100:
        raise AudioExtractionError(f"ffmpeg отработал, но аудио-файл пустой: {output_path}")

    return output_path


# ──────────────────────────────────────────────────────────────────────────────
# Загрузка модели (ленивая, синглтон)
# ──────────────────────────────────────────────────────────────────────────────
_model_cache: dict[str, WhisperModel] = {}


def _get_model() -> WhisperModel:
    """
    Ленивая загрузка модели Whisper. Кэшируем по «имени настроек», чтобы
    при повторных вызовах не грузить модель заново (это 100+ МБ для base).
    """
    cache_key = (
        f"{settings.WHISPER_MODEL}_{settings.WHISPER_DEVICE}_{settings.WHISPER_COMPUTE_TYPE}"
    )
    if cache_key in _model_cache:
        return _model_cache[cache_key]

    logger.info(
        "Загружаю модель Whisper: %s (device=%s, compute=%s)…",
        settings.WHISPER_MODEL,
        settings.WHISPER_DEVICE,
        settings.WHISPER_COMPUTE_TYPE,
    )

    # beam_size=5 — хороший баланс качества/скорости.
    # vad_filter=True — пропускаем тишину, экономим время.
    # vad_parameters — порог агрессивности VAD (0 = всё пропускает, 1 = максимально агрессивно).
    try:
        model = WhisperModel(
            settings.WHISPER_MODEL,
            device=settings.WHISPER_DEVICE,
            compute_type=settings.WHISPER_COMPUTE_TYPE,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Не удалось загрузить модель Whisper")
        raise TranscriptionError(
            f"Ошибка загрузки модели '{settings.WHISPER_MODEL}': {exc}"
        ) from exc

    _model_cache[cache_key] = model
    logger.info("✔ Модель Whisper загружена")
    return model


# ──────────────────────────────────────────────────────────────────────────────
# Главная функция модуля
# ──────────────────────────────────────────────────────────────────────────────
def transcribe_video(
    video_path: Path | str,
    progress_callback=None,
) -> TranscriptResult:
    """
    Транскрибировать видео: вернуть текст + сегменты с временами.

    Параметры:
        video_path       — путь к видео (любой формат, который читает ffmpeg).
        progress_callback — (опционально) fn(percent: float), вызывается при
                            прогрессе распознавания. percent = 50..85.

    Возвращает:
        TranscriptResult с полным текстом и таймингами.

    Бросает:
        TranscriptionError — что-то пошло не так.
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise TranscriptionError(f"Файл не найден: {video_path}")

    # Создаём временный .wav рядом с видео (чтобы ffmpeg быстрее работал
    # на том же диске), но в подпапке — чтобы легко удалить пачкой.
    tmp_dir = Path(tempfile.gettempdir()) / "whisper_audio"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    audio_path = tmp_dir / f"{video_path.stem}.wav"

    # 1. Извлекаем аудио.
    try:
        extract_audio(video_path, audio_path)
    except (AudioExtractionError, FFmpegNotFoundError) as exc:
        # Не нашли ffmpeg / не смогли извлечь — проброс.
        raise TranscriptionError(str(exc)) from exc

    # 2. Прогоняем через faster-whisper.
    try:
        model = _get_model()

        logger.info("Whisper recognize start: %s", audio_path.name)
        segments_iter, info = model.transcribe(
            str(audio_path),
            # beam_size — точнее, но медленнее. Для base на CPU подходит 5.
            beam_size=5,
            # Фильтр активности голоса — режем тишину.
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
            # language не задаём — модель сама определит.
        )

        # segments_iter — генератор, его надо «выпить» здесь же,
        # пока жив ресурс audio_path.
        audio_duration = float(getattr(info, "duration", 0.0) or 0.0)
        segments: list[TranscriptSegment] = []
        full_text_parts: list[str] = []
        for seg in segments_iter:
            text = (seg.text or "").strip()
            if not text:
                continue
            ts = TranscriptSegment(start=float(seg.start), end=float(seg.end), text=text)
            if progress_callback is not None and audio_duration > 0:
                # Прогресс whisper: 50% .. 85%.
                p = 50.0 + (ts.end / audio_duration) * 35.0
                with contextlib.suppress(Exception):
                    progress_callback(min(p, 85.0))
            segments.append(ts)
            full_text_parts.append(text)

        full_text = " ".join(full_text_parts).strip()
        language = getattr(info, "language", "unknown") or "unknown"

        logger.info(
            "✔ Whisper готово: язык=%s, сегментов=%d, символов=%d",
            language,
            len(segments),
            len(full_text),
        )

        return TranscriptResult(
            language=language,
            full_text=full_text,
            segments=segments,
            audio_path=audio_path,
        )

    except TranscriptionError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Неизвестная ошибка Whisper")
        raise TranscriptionError(f"Ошибка распознавания речи: {exc}") from exc

    finally:
        # Чистим временное аудио сразу — оно нам больше не нужно,
        # занимает место и так.
        try:
            if audio_path.exists():
                # Не удаляем, если кто-то снаружи захотел пошарить.
                # Но обычно у нас всё равно весь tmp_dir чистится helpers.
                audio_path.unlink()
        except OSError:
            pass


# ──────────────────────────────────────────────────────────────────────────────
# CLI-тест
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    """
    Прогон одной командой:
        python -m services.transcriber path/to/video.mp4
    """
    import sys
    import time

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if len(sys.argv) < 2:
        print("Использование: python -m services.transcriber <path-to-video>")
        sys.exit(1)

    p = Path(sys.argv[1])
    if not p.exists():
        print(f"❌ Файл не найден: {p}")
        sys.exit(1)

    t0 = time.time()
    try:
        result = transcribe_video(p)
    except TranscriptionError as e:
        print(f"\n❌ Ошибка: {e}")
        sys.exit(2)

    print(f"\n✅ Готово за {time.time() - t0:.1f} сек. Язык: {result.language}")
    print(f"   Сегментов: {len(result.segments)}, символов: {len(result.full_text)}")
    print("\n--- Первые 5 сегментов ---")
    for seg in result.segments[:5]:
        print(f"[{seg.start:6.1f} → {seg.end:6.1f}] {seg.text}")
    if len(result.segments) > 5:
        print(f"... и ещё {len(result.segments) - 5} сегментов")
