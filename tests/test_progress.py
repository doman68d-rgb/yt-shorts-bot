"""
Тесты для services/progress.py — репортер прогресса.
"""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.progress import ProgressReporter, ProgressState


class TestProgressState:
    def test_render_simple(self):
        s = ProgressState(text="Downloading", percent=50.0)
        out = s.render()
        assert "Downloading" in out
        assert "50%" in out
        assert "▓" in out
        assert "░" in out

    def test_render_full(self):
        s = ProgressState(text="Done", percent=100.0)
        out = s.render()
        assert "100%" in out
        assert "▓" * 10 in out

    def test_render_zero(self):
        s = ProgressState(text="Init", percent=0.0)
        out = s.render()
        assert "0%" in out


class TestProgressReporter:
    def test_set_step_basic(self):
        # Прямое использование без async-контекста.
        bot = MagicMock()
        msg = MagicMock()
        r = ProgressReporter(bot, msg)
        r.set_step("step1", "Doing", 25.0)
        assert r.state.step == "step1"
        assert r.state.percent == 25.0

    def test_yt_dlp_hook_downloading(self):
        bot = MagicMock()
        msg = MagicMock()
        r = ProgressReporter(bot, msg)
        r.yt_dlp_update({
            "status": "downloading",
            "downloaded_bytes": 50,
            "total_bytes": 100,
            "speed": 1024 * 1024,
            "eta": 60,
        })
        assert r.state.step == "downloading"
        assert "MB/s" in r.state.text or "KB/s" in r.state.text
        assert r.state.percent > 0

    def test_yt_dlp_hook_finished(self):
        bot = MagicMock()
        msg = MagicMock()
        r = ProgressReporter(bot, msg)
        r.yt_dlp_update({"status": "finished"})
        assert r.state.percent == 50.0

    def test_yt_dlp_hook_error(self):
        bot = MagicMock()
        msg = MagicMock()
        r = ProgressReporter(bot, msg)
        r.yt_dlp_update({"status": "error"})
        assert r.state.failed is True

    def test_whisper_update_clamps(self):
        bot = MagicMock()
        msg = MagicMock()
        r = ProgressReporter(bot, msg)
        r.whisper_update(120.0)   # > 85
        assert r.state.percent == 85.0
        r.whisper_update(30.0)    # < 50
        assert r.state.percent == 50.0

    def test_done(self):
        bot = MagicMock()
        msg = MagicMock()
        r = ProgressReporter(bot, msg)
        r.done()
        assert r.state.done is True
        assert r.state.percent == 100.0

    def test_fail(self):
        bot = MagicMock()
        msg = MagicMock()
        r = ProgressReporter(bot, msg)
        r.fail("something went wrong")
        assert r.state.failed is True
        assert "something went wrong" in r.state.text


class TestFormatters:
    def test_format_speed(self):
        assert "MB/s" in ProgressReporter._fmt_speed(1024 * 1024 * 2)
        assert "KB/s" in ProgressReporter._fmt_speed(1024 * 100)
        assert "B/s" in ProgressReporter._fmt_speed(500)
        assert "—" in ProgressReporter._fmt_speed(0)

    def test_format_eta(self):
        assert "h" in ProgressReporter._fmt_eta(4000) or "s" in ProgressReporter._fmt_eta(4000)
        assert "s" in ProgressReporter._fmt_eta(30)
        assert "—" in ProgressReporter._fmt_eta(0)
        assert "—" in ProgressReporter._fmt_eta(-1)
