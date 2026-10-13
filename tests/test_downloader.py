"""
Тесты для services/downloader.py — URL-валидация и edge-cases.

(Не тестируем реальное скачивание: это интеграция, требует сеть и ffmpeg.)
"""

import pytest

from services.downloader import (
    InvalidURLError,
    _sanitize_filename,
    _validate_url,
)


class TestValidateUrl:
    def test_https(self):
        _validate_url("https://youtube.com/watch?v=1")  # не упадёт

    def test_http(self):
        _validate_url("http://example.com/")  # не упадёт

    def test_empty(self):
        with pytest.raises(InvalidURLError):
            _validate_url("")

    def test_none(self):
        with pytest.raises(InvalidURLError):
            _validate_url(None)  # type: ignore[arg-type]

    def test_no_scheme(self):
        with pytest.raises(InvalidURLError):
            _validate_url("youtube.com/watch?v=1")

    def test_strips_whitespace(self):
        _validate_url("  https://example.com/  ")  # не упадёт


class TestSanitizeFilename:
    def test_basic(self):
        assert _sanitize_filename("hello") == "hello"

    def test_empty(self):
        # Пустая → дефолт
        assert _sanitize_filename("") == "video"

    def test_removes_windows_chars(self):
        result = _sanitize_filename("a<b>c:d")
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result

    def test_truncates_long(self):
        long_name = "a" * 1000
        result = _sanitize_filename(long_name, max_len=80)
        assert len(result) <= 80

    def test_no_trailing_dots(self):
        result = _sanitize_filename("hello...")
        assert not result.endswith(".")

    def test_collapses_underscores(self):
        result = _sanitize_filename("hello___world")
        assert "_" not in result.replace("_", "", 1).replace("_", "", 1) or "hello_world" in result
