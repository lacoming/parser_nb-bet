"""Tests for team name normalizer."""
from __future__ import annotations

from src.kush.normalizer import normalize, _transliterate


class TestNormalize:
    def test_lowercase(self):
        assert normalize("Manchester United") == "manchester united"

    def test_remove_punctuation(self):
        # C.F. → "c f" after punctuation removal (single-char words kept)
        result = normalize("Real Madrid C.F.")
        assert "real madrid" in result

    def test_transliterate_cyrillic(self):
        result = normalize("Спартак Москва")
        assert "spartak" in result
        assert "moskva" in result

    def test_remove_fc_prefix(self):
        assert normalize("FC Barcelona") == "barcelona"

    def test_remove_fk_prefix(self):
        assert normalize("ФК Зенит") == "zenit"

    def test_collapse_whitespace(self):
        assert normalize("Team   A") == "team a"

    def test_empty_string(self):
        assert normalize("") == ""

    def test_mixed_script(self):
        result = normalize("Динамо Kyiv")
        assert "dinamo" in result
        assert "kyiv" in result

    def test_special_chars(self):
        result = normalize("Borussia Mönchengladbach")
        assert "borussia" in result

    def test_strip(self):
        assert normalize("  Team A  ") == "team a"


class TestTransliterate:
    def test_basic(self):
        assert _transliterate("а") == "a"
        assert _transliterate("б") == "b"

    def test_compound(self):
        assert _transliterate("ж") == "zh"
        assert _transliterate("ш") == "sh"

    def test_soft_hard_signs(self):
        assert _transliterate("ъ") == ""
        assert _transliterate("ь") == ""

    def test_preserves_latin(self):
        assert _transliterate("abc") == "abc"

    def test_full_word(self):
        assert _transliterate("спартак") == "spartak"
