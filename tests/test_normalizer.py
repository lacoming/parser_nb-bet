"""Tests for team name normalizer."""
from __future__ import annotations

import json
import os
import tempfile

from src.kush.normalizer import normalize, _transliterate, load_aliases, _apply_aliases, _aliases


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


class TestAliases:
    def setup_method(self):
        """Reset aliases before each test."""
        import src.kush.normalizer as mod
        mod._aliases = {}

    def test_load_aliases_from_file(self, tmp_path):
        aliases_file = tmp_path / "sl_teams_zamen.json"
        aliases_file.write_text(json.dumps({"невроз": "новруз", "миссан": "майсан"}), encoding="utf-8")
        count = load_aliases(str(aliases_file))
        assert count == 2

    def test_load_aliases_missing_file(self, tmp_path):
        count = load_aliases(str(tmp_path / "nonexistent.json"))
        assert count == 0

    def test_alias_applied_full_name(self, tmp_path):
        aliases_file = tmp_path / "sl_teams_zamen.json"
        aliases_file.write_text(json.dumps({"невроз": "новруз"}), encoding="utf-8")
        load_aliases(str(aliases_file))
        result = normalize("Невроз")
        assert "novruz" in result

    def test_alias_applied_word_level(self, tmp_path):
        aliases_file = tmp_path / "sl_teams_zamen.json"
        aliases_file.write_text(json.dumps({"миссан": "майсан"}), encoding="utf-8")
        load_aliases(str(aliases_file))
        result = normalize("Нафт Миссан")
        assert "maysan" in result
        assert "missan" not in result

    def test_alias_not_applied_when_no_match(self, tmp_path):
        aliases_file = tmp_path / "sl_teams_zamen.json"
        aliases_file.write_text(json.dumps({"невроз": "новруз"}), encoding="utf-8")
        load_aliases(str(aliases_file))
        result = normalize("Спартак")
        assert "spartak" in result

    def test_normalize_without_aliases(self):
        """Without loading aliases, normalize works as before."""
        result = normalize("Невроз")
        assert "nevroz" in result


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
