"""
services/highlights.py
~~~~~~~~~~~~~~~~~~~~~~

«Умный» выбор моментов для клипов через LLM.

Идея:
    1. Берём TranscriptResult (тайминги + текст).
    2. Группируем сегменты в «чанки» по N секунд (по умолчанию 30).
    3. Сжимаем каждый чанк: начало, конец, текст чанка.
    4. Шлём в LLM (OpenAI-совместимый API) с просьбой:
       «выбери K самых ярких/информативных моментов для Shorts».
    5. Парсим JSON с ответа → список ClipRange.

Поддерживаемые провайдеры (через единый OpenAI-совместимый API):
    • OpenAI (по умолчанию модель gpt-4o-mini)
    • OpenRouter (https://openrouter.ai) — единый ключ на все модели
    • Любой локальный LLM-сервер (Ollama, llama.cpp server, LM Studio)

Если LLM недоступна / ключ не задан — fallback на random (для совместимости
со старым поведением).
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass

from services.editor import ClipRange
from services.transcriber import TranscriptResult

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Исключения
# ──────────────────────────────────────────────────────────────────────────────
class HighlightsError(Exception):
    """Базовая ошибка модуля highlights."""


class LLMUnavailableError(HighlightsError):
    """LLM API недоступен (нет ключа / сеть / формат ответа)."""


# ──────────────────────────────────────────────────────────────────────────────
# Конфиг LLM через env
# ──────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class LLMConfig:
    """Настройки LLM. Берутся из env при создании."""

    api_key: str | None
    base_url: str
    model: str
    timeout: float

    @classmethod
    def from_env(cls) -> LLMConfig:
        return cls(
            api_key=os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY"),
            base_url=os.getenv(
                "LLM_BASE_URL",
                "https://api.openai.com/v1",  # можно переопределить на OpenRouter/Ollama
            ),
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            timeout=float(os.getenv("LLM_TIMEOUT", "60")),
        )


# ──────────────────────────────────────────────────────────────────────────────
# Вспомогательные функции
# ──────────────────────────────────────────────────────────────────────────────
def _chunk_segments(
    segments: list,
    chunk_seconds: float,
) -> list[dict]:
    """
    Сгруппировать сегменты речи в чанки по N секунд.
    Возвращает список:
        {"index": int, "start": float, "end": float, "text": str, "char_count": int}
    """
    if not segments:
        return []

    chunks: list[dict] = []
    cur_start = segments[0].start
    cur_text_parts: list[str] = []
    cur_end = segments[0].start
    idx = 0

    for seg in segments:
        # Если чанк переполнен И текущий сегмент не начинается в этом же чанке
        # — закрываем чанк и открываем новый.
        if seg.start - cur_start > chunk_seconds and cur_text_parts:
            chunks.append(
                {
                    "index": idx,
                    "start": cur_start,
                    "end": cur_end,
                    "text": " ".join(cur_text_parts).strip(),
                    "char_count": sum(len(p) for p in cur_text_parts),
                }
            )
            idx += 1
            cur_start = seg.start
            cur_text_parts = []
        cur_text_parts.append(seg.text)
        cur_end = seg.end

    # Финальный чанк
    if cur_text_parts:
        chunks.append(
            {
                "index": idx,
                "start": cur_start,
                "end": cur_end,
                "text": " ".join(cur_text_parts).strip(),
                "char_count": sum(len(p) for p in cur_text_parts),
            }
        )

    return chunks


def _build_llm_prompt(
    chunks: list[dict],
    video_title: str,
    clip_count: int,
    clip_duration: int,
) -> str:
    """Сформировать промпт для LLM."""
    chunks_text = []
    for c in chunks:
        chunks_text.append(f"[#{c['index']} t={c['start']:.0f}-{c['end']:.0f}s] {c['text']}")
    chunks_block = "\n".join(chunks_text)

    return f"""Ты — ассистент для создания Shorts / TikTok клипов.

Видео: «{video_title}»

Ниже — разбитый на чанки транскрипт с временными метками. Каждый чанк — это
кусок речи длительностью ~{int((chunks[1]["end"] - chunks[0]["end"]) + (chunks[1]["end"] - chunks[1]["start"])) if len(chunks) > 1 else 30} секунд.

{chunks_block}

Задача: выбери ровно {clip_count} самых ярких, информативных или эмоциональных
момента длительностью примерно {clip_duration} секунд каждый, которые лучше всего
подходят для вертикальных Shorts.

ВАЖНО:
- Каждый момент должен быть самодостаточным (понятным без контекста).
- Не выбирай интро, аутро, паузы, рекламу, фразы вроде "подпишитесь".
- Приоритет: ключевые мысли, яркие цитаты, конфликты, инсайты, кульминации.
- Если в чанке есть самодостаточный момент — укажи его начало и конец по меткам чанка.
- Если нужный момент выходит за границы одного чанка — можно указать диапазон,
  включающий несколько чанков.

Формат ответа — СТРОГО JSON без markdown-обёрток и пояснений:
{{
  "clips": [
    {{"start": <число секунд>, "end": <число секунд>, "reason": "<короткая причина, до 10 слов>"}},
    ...
  ]
}}
"""


def _parse_llm_response(raw: str, expected_count: int) -> list[dict]:
    """
    Распарсить JSON из ответа LLM. Устойчив к:
        • markdown-обёрткам ```json ... ```
        • мусору вокруг (LLM иногда добавляет текст до/после JSON)
    """
    # Вырезаем JSON в фигурных скобках — самый надёжный способ.
    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        raise LLMUnavailableError(f"LLM не вернула JSON. Первые 200 символов:\n{raw[:200]}")
    payload = match.group(0)

    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise LLMUnavailableError(f"Битый JSON от LLM: {exc}\nПолучено: {raw[:300]}") from exc

    clips = data.get("clips")
    if not isinstance(clips, list) or not clips:
        raise LLMUnavailableError(f"LLM не вернула список 'clips'. Ответ: {data}")

    parsed: list[dict] = []
    for c in clips:
        if "start" not in c or "end" not in c:
            continue
        try:
            parsed.append(
                {
                    "start": float(c["start"]),
                    "end": float(c["end"]),
                    "reason": str(c.get("reason", ""))[:80],
                }
            )
        except (ValueError, TypeError):
            continue

    if not parsed:
        raise LLMUnavailableError("LLM вернула пустой список валидных клипов.")

    return parsed[:expected_count]


def _filter_valid_ranges(
    candidates: list[dict],
    total_duration: float,
    skip_edges_percent: int,
    min_clip: float,
) -> list[ClipRange]:
    """
    Отфильтровать LLM-кандидатов:
        • старт >= safe_start
        • конец <= safe_end
        • длина >= min_clip (если LLM сильно сократила — отбрасываем)
    Невалидные пропускаем, индексы переназначаются.
    """
    edges = max(0.0, total_duration * skip_edges_percent / 100.0)
    safe_start = edges
    safe_end = total_duration - edges

    ranges: list[ClipRange] = []
    for i, c in enumerate(candidates, start=1):
        s = c["start"]
        e = c["end"]
        if e - s < min_clip:
            logger.info("LLM-кандидат #%d слишком короткий (%.1fs) — пропуск", i, e - s)
            continue
        s = max(safe_start, min(s, safe_end))
        e = max(s + min_clip, min(e, safe_end))
        ranges.append(
            ClipRange(
                index=i,
                start=s,
                end=e,
            )
        )
        logger.info(
            "✔ LLM выбрал момент #%d: [%.1f → %.1f] %s",
            i,
            s,
            e,
            c.get("reason", ""),
        )
    return ranges


# ──────────────────────────────────────────────────────────────────────────────
# Главные функции модуля
# ──────────────────────────────────────────────────────────────────────────────
def pick_highlights_random(
    total_duration: float,
    clip_count: int,
    clip_duration: float,
    skip_edges_percent: int = 10,
) -> list[ClipRange]:
    """
    Запасной вариант: случайные клипы из «середины» видео.
    Используется, если LLM недоступна или не настроена.
    Дублирует логику из editor.py, чтобы не было циклической зависимости.
    """
    import random

    edges = max(0.0, total_duration * skip_edges_percent / 100.0)
    safe_start = edges
    safe_end = total_duration - edges

    if safe_end - safe_start <= 0:
        return []

    available = safe_end - safe_start
    actual_clip_length = min(clip_duration, available)

    if available <= actual_clip_length:
        center = (safe_start + safe_end) / 2
        starts = [center]
    else:
        rng = random.Random()
        min_step = actual_clip_length
        count = clip_count
        if min_step * count > available:
            count = max(1, int(available // min_step))
        max_start = safe_end - actual_clip_length
        # 50 равномерных точек
        step = (max_start - safe_start) / 49 if max_start > safe_start else 0
        possible = [safe_start + step * i for i in range(50)] if step > 0 else [safe_start]
        chosen: list[float] = []
        last_end = -1e9
        for _ in range(count):
            candidates = [p for p in possible if p >= last_end + min_step] or possible
            s = rng.choice(candidates)
            chosen.append(s)
            last_end = s + actual_clip_length
        starts = sorted(chosen)

    return [
        ClipRange(index=i + 1, start=s, end=s + actual_clip_length) for i, s in enumerate(starts)
    ]


def pick_highlights_llm(
    transcript: TranscriptResult,
    total_duration: float,
    clip_count: int,
    clip_duration: int,
    skip_edges_percent: int = 10,
    config: LLMConfig | None = None,
) -> list[ClipRange]:
    """
    «Умный» выбор через LLM. Бросает LLMUnavailableError, если что-то пошло не так.
    """
    cfg = config or LLMConfig.from_env()

    if not cfg.api_key:
        raise LLMUnavailableError(
            "OPENAI_API_KEY (или LLM_API_KEY) не задан в окружении. "
            "Установи ключ или используй fallback на random."
        )

    # 1. Чанкуем транскрипт.
    chunk_seconds = float(os.getenv("LLM_CHUNK_SECONDS", "30"))
    chunks = _chunk_segments(transcript.segments, chunk_seconds=chunk_seconds)
    if not chunks:
        raise LLMUnavailableError("Транскрипт пустой — нечего отправлять в LLM.")

    # 2. Слишком длинный промпт — обрезаем до ~15 000 символов текста
    # (LLM-ы считают токены, а символов в килобайтном тексте ≈ 250 токенов).
    max_chars = int(os.getenv("LLM_MAX_TRANSCRIPT_CHARS", "15000"))
    full_text_chars = sum(c["char_count"] for c in chunks)
    if full_text_chars > max_chars:
        # Сжимаем через более крупные чанки или отбрасываем хвосты.
        max_chars / full_text_chars
        chunk_seconds *= 2  # укрупняем чанки
        chunks = _chunk_segments(transcript.segments, chunk_seconds=chunk_seconds)
        logger.info(
            "Транскрипт длинный (%d симв.), укрупнил чанки до %.0fs",
            full_text_chars,
            chunk_seconds,
        )

    # 3. Формируем промпт.
    video_title = getattr(transcript, "title", "") or "Видео"
    prompt = _build_llm_prompt(
        chunks=chunks,
        video_title=video_title,
        clip_count=clip_count,
        clip_duration=clip_duration,
    )

    logger.info(
        "Отправляю в LLM (%s/%s): %d чанков, %d символов промпта",
        cfg.base_url,
        cfg.model,
        len(chunks),
        len(prompt),
    )

    # 4. HTTP-запрос к OpenAI-совместимому API.
    try:
        import httpx  # поставляется с aiogram
    except ImportError as exc:
        raise LLMUnavailableError("Нет httpx (зависимость aiogram)") from exc

    try:
        response = httpx.post(
            url=f"{cfg.base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {cfg.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": cfg.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "Ты ассистент, который ВСЕГДА отвечает строго JSON, без markdown-обёрток.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.5,
                "max_tokens": 500,
            },
            timeout=cfg.timeout,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise LLMUnavailableError(f"HTTP ошибка к LLM: {exc}") from exc

    payload = response.json()
    try:
        raw = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise LLMUnavailableError(f"Неожиданный формат ответа LLM: {payload}") from exc

    # 5. Парсим и валидируем.
    candidates = _parse_llm_response(raw, expected_count=clip_count)
    ranges = _filter_valid_ranges(
        candidates=candidates,
        total_duration=total_duration,
        skip_edges_percent=skip_edges_percent,
        min_clip=10.0,  # минимально допустимый клип — 10 секунд
    )

    if not ranges:
        raise LLMUnavailableError("LLM не дала ни одного валидного диапазона.")

    return ranges


def pick_highlights(
    transcript: TranscriptResult | None,
    total_duration: float,
    clip_count: int,
    clip_duration: int,
    skip_edges_percent: int = 10,
    prefer_llm: bool = True,
) -> tuple[list[ClipRange], str]:
    """
    Универсальная точка входа:
        1. Если есть транскрипт И prefer_llm=True И есть OPENAI_API_KEY — LLM.
        2. Иначе — fallback на random.

    Возвращает (ranges, strategy), где strategy = "llm" | "random".
    """
    has_llm_key = bool(os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY"))

    if prefer_llm and transcript and transcript.segments and has_llm_key:
        try:
            return (
                pick_highlights_llm(
                    transcript=transcript,
                    total_duration=total_duration,
                    clip_count=clip_count,
                    clip_duration=clip_duration,
                    skip_edges_percent=skip_edges_percent,
                ),
                "llm",
            )
        except LLMUnavailableError as exc:
            logger.warning("LLM недоступна (%s), fallback на random", exc)

    return (
        pick_highlights_random(
            total_duration=total_duration,
            clip_count=clip_count,
            clip_duration=clip_duration,
            skip_edges_percent=skip_edges_percent,
        ),
        "random",
    )
