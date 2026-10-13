"""
Тесты для bot/prefs.py — пользовательские настройки.
"""

import pytest

from bot.prefs import UserPrefs, get_prefs, reset, update


@pytest.fixture(autouse=True)
def clean_prefs():
    """Очищаем prefs до и после теста."""
    reset(0)
    reset(123)
    yield
    reset(0)
    reset(123)


class TestGetPrefs:
    def test_creates_defaults(self):
        p = get_prefs(123)
        assert isinstance(p, UserPrefs)
        # Дефолты из config.py.
        assert p.clip_count >= 1
        assert p.clip_duration >= 5
        assert p.strategy in ("smart", "random")

    def test_returns_same_object(self):
        p1 = get_prefs(123)
        p2 = get_prefs(123)
        assert p1 is p2

    def test_different_chats(self):
        p1 = get_prefs(100)
        p2 = get_prefs(200)
        update(100, clip_count=9)
        assert p1.clip_count == 9
        assert p2.clip_count != 9  # дефолт


class TestUpdate:
    def test_update_existing_field(self):
        update(0, clip_count=5, clip_duration=60)
        p = get_prefs(0)
        assert p.clip_count == 5
        assert p.clip_duration == 60

    def test_update_unknown_field_ignored(self):
        # Не падать, если передали что-то странное.
        p = update(0, nonexistent_field=42)
        assert p is not None

    def test_update_returns_object(self):
        result = update(0, strategy="random")
        p = get_prefs(0)
        assert result is p
