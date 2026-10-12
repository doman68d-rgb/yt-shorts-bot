"""
Тесты для bot/formatters.py.
"""

from bot.formatters import clip_range, duration, escape
from services.editor import ClipRange


class TestEscape:
    def test_empty(self):
        assert escape("") == ""

    def test_no_specials(self):
        assert escape("hello") == "hello"

    def test_html_chars_escaped(self):
        assert escape("<b>bold</b>") == "&lt;b&gt;bold&lt;/b&gt;"
        assert escape("a & b") == "a &amp; b"

    def test_none_safe(self):
        # Should not crash on None-like input.
        assert "&lt;" in escape("<")


class TestDuration:
    def test_zero(self):
        assert duration(0) == "0:00"

    def test_seconds_only(self):
        assert duration(45) == "0:45"
        assert duration(59) == "0:59"

    def test_minutes(self):
        assert duration(60) == "1:00"
        assert duration(125) == "2:05"

    def test_hours(self):
        assert duration(3600) == "1:00:00"
        assert duration(3725) == "1:02:05"


class TestClipRange:
    def test_format(self):
        r = ClipRange(index=1, start=10.0, end=55.0)
        assert clip_range(r) == "[0:10 → 0:55]"

    def test_none(self):
        assert clip_range(None) == ""
