"""
Тесты для services/highlights.py — модуль выбора моментов.
"""

import pytest

from services.highlights import (
    _chunk_segments,
    pick_highlights,
    pick_highlights_llm,
    pick_highlights_random,
)
from services.transcriber import TranscriptResult, TranscriptSegment


def make_transcript(segments_data):
    """Утилита: сделать TranscriptResult из списка (start, end, text)."""
    segments = [
        TranscriptSegment(start=s, end=e, text=t)
        for s, e, t in segments_data
    ]
    return TranscriptResult(
        language="en",
        full_text=" ".join(s.text for s in segments),
        segments=segments,
    )


class TestChunkSegments:
    def test_empty(self):
        assert _chunk_segments([], chunk_seconds=30) == []

    def test_single_short_segment(self):
        segs = [TranscriptSegment(start=0, end=5, text="hi")]
        chunks = _chunk_segments(segs, chunk_seconds=30)
        assert len(chunks) == 1
        assert chunks[0]["text"] == "hi"
        assert chunks[0]["index"] == 0

    def test_groups_by_duration(self):
        # Сегменты каждые 5 секунд, chunk = 30 → должно группировать по 6 сегментов в чанк.
        segs = [
            TranscriptSegment(start=i * 5, end=(i + 1) * 5, text=f"seg{i}")
            for i in range(20)
        ]
        chunks = _chunk_segments(segs, chunk_seconds=30)
        # Должно быть несколько чанков.
        assert len(chunks) >= 2
        # У каждого чанка корректный индекс.
        for i, c in enumerate(chunks):
            assert c["index"] == i

    def test_text_joined(self):
        segs = [
            TranscriptSegment(start=0, end=5, text="hello"),
            TranscriptSegment(start=5, end=10, text="world"),
        ]
        chunks = _chunk_segments(segs, chunk_seconds=30)
        assert chunks[0]["text"] == "hello world"


class TestPickHighlightsRandom:
    def test_basic(self):
        ranges = pick_highlights_random(
            total_duration=600.0,
            clip_count=3,
            clip_duration=45.0,
            skip_edges_percent=10,
        )
        assert len(ranges) == 3
        # Первый клип не начинается раньше 10% от видео.
        for r in ranges:
            assert r.start >= 60.0 - 0.1   # с поправкой на float
            assert r.end <= 600.0 - 60.0 + 0.1

    def test_short_video(self):
        # Видео 80 секунд, клип 45 — не влезает 3.
        ranges = pick_highlights_random(
            total_duration=80.0,
            clip_count=3,
            clip_duration=45.0,
            skip_edges_percent=10,
        )
        # Функция должна выдать хотя бы 1 клип.
        assert len(ranges) >= 1

    def test_indices_renumbered(self):
        ranges = pick_highlights_random(
            total_duration=600.0, clip_count=2, clip_duration=45.0,
        )
        indices = [r.index for r in ranges]
        assert indices == sorted(indices)


class TestPickHighlights:
    """Главная точка входа — auto-fallback."""

    def test_prefers_random_when_no_key(self, monkeypatch):
        """Если LLM_API_KEY не задан — должен вернуться random."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        t = make_transcript([(0, 5, "hello")])
        ranges, strategy = pick_highlights(
            transcript=t,
            total_duration=300.0,
            clip_count=2,
            clip_duration=30,
            prefer_llm=True,
        )
        assert strategy == "random"
        assert len(ranges) == 2

    def test_random_when_force(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "fake-but-present")
        # prefer_llm=False → даже с ключом должно быть random.
        t = make_transcript([(0, 5, "hello")])
        ranges, strategy = pick_highlights(
            transcript=t,
            total_duration=300.0,
            clip_count=2,
            clip_duration=30,
            prefer_llm=False,
        )
        assert strategy == "random"


class TestPickHighlightsLLM:
    def test_no_api_key_raises(self):
        import os
        os.environ.pop("OPENAI_API_KEY", None)
        os.environ.pop("LLM_API_KEY", None)
        t = make_transcript([(0, 5, "hello")])
        from services.highlights import LLMUnavailableError
        with pytest.raises(LLMUnavailableError):
            pick_highlights_llm(t, 300.0, 2, 30)
