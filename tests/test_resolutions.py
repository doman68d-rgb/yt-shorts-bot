"""
Тесты для функциональности выбора разрешения.
"""

from bot.prefs import (
    DEFAULT_RESOLUTION,
    RESOLUTIONS,
    UserPrefs,
    get_prefs,
    parse_resolution,
    reset,
    update,
)
from services.editor import _build_crop_filter


class TestResolutionsDict:
    def test_all_keys_present(self):
        assert set(RESOLUTIONS.keys()) == {"720x1280", "1080x1350", "1080x1920"}

    def test_values_are_tuples(self):
        for key, val in RESOLUTIONS.items():
            assert isinstance(val, tuple), f"{key}: expected tuple"
            assert len(val) == 2, f"{key}: expected 2 elements"

    def test_dimensions_are_positive(self):
        for _key, (w, h) in RESOLUTIONS.items():
            assert w > 0
            assert h > 0

    def test_aspect_ratios(self):
        # 720x1280 = 9:16 (Shorts/TikTok)
        assert 720 / 1280 == 9 / 16
        # 1080x1920 = 9:16 (стандарт Shorts)
        assert 1080 / 1920 == 9 / 16
        # 1080x1350 = 4:5 (Instagram лента)
        assert 1080 / 1350 == 4 / 5


class TestParseResolution:
    def test_known_key(self):
        assert parse_resolution("1080x1920") == (1080, 1920)

    def test_other_known_keys(self):
        assert parse_resolution("720x1280") == (720, 1280)
        assert parse_resolution("1080x1350") == (1080, 1350)

    def test_unknown_falls_back(self):
        assert parse_resolution("garbage") == RESOLUTIONS[DEFAULT_RESOLUTION]

    def test_empty_falls_back(self):
        assert parse_resolution("") == RESOLUTIONS[DEFAULT_RESOLUTION]


class TestUserPrefsResolution:
    def test_default_in_resolutions(self):
        assert DEFAULT_RESOLUTION in RESOLUTIONS

    def test_default_set_in_dataclass(self):
        # Создаём «вручную», без settings (для переносимости теста)
        import dataclasses

        fields = {f.name for f in dataclasses.fields(UserPrefs)}
        assert "resolution" in fields

    def test_resolution_persists_per_chat(self):
        reset(0)
        reset(999)
        # Новый пользователь → дефолт
        prefs = get_prefs(0)
        assert prefs.resolution == DEFAULT_RESOLUTION
        # Другой чат обновляет
        update(999, resolution="720x1280")
        assert get_prefs(999).resolution == "720x1280"
        # Первый чат не задет
        assert get_prefs(0).resolution == DEFAULT_RESOLUTION


class TestCropFilter:
    def test_short_formula(self):
        # 1080x1920 -> crop=ih*1080/1920:ih
        f = _build_crop_filter(1080, 1920)
        assert "ih*1080/1920" in f
        assert "scale=1080:1920" in f

    def test_instagram_formula(self):
        # 1080x1350 -> crop=ih*1080/1350:ih
        f = _build_crop_filter(1080, 1350)
        assert "ih*1080/1350" in f
        assert "scale=1080:1350" in f
        assert "lanczos" in f

    def test_lightweight_formula(self):
        f = _build_crop_filter(720, 1280)
        assert "ih*720/1280" in f
        assert "scale=720:1280" in f

    def test_filter_includes_sar_and_flags(self):
        # Все фильтры должны нормализовать SAR и использовать lanczos
        for w, h in [(720, 1280), (1080, 1350), (1080, 1920)]:
            f = _build_crop_filter(w, h)
            assert "setsar=1" in f
            assert "flags=lanczos" in f
