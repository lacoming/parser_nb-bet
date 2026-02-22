"""Tests for decision engine, league filter, league loader, and models."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.decision.engine import DecisionEngine
from src.decision.league_filter import LeagueFilter, load_chemps_zamen
from src.decision.models import BetDecision, LeagueSetting, normalize_bet_type
from src.nb.models import Match


def _make_match(**kwargs) -> Match:
    defaults = dict(
        match_key="k",
        league="England. Premier League",
        team_home="Team A",
        team_away="Team B",
        start_time_utc=datetime(2026, 2, 21, 15, 0, tzinfo=timezone.utc),
        nb_slug="a-vs-b",
        sport="soccer",
    )
    defaults.update(kwargs)
    return Match(**defaults)


# ─── DecisionEngine tests ──────────────────────────────────────────────


class TestDecisionEngineKf1GtKf2:
    """kf1 > kf2 branch (home is underdog)."""

    def test_all_pass(self):
        engine = DecisionEngine()
        m = _make_match(odds_1_end=3.50, odds_x_end=3.20, odds_2_end=2.10)
        decisions = engine.decide(m)
        types = {d.bet_type for d in decisions if d.passes}
        assert "1X" in types
        assert "1" in types
        assert "2" in types
        assert "X" in types

    def test_1x_fails_kf1_too_high(self):
        engine = DecisionEngine()
        m = _make_match(odds_1_end=9.00, odds_x_end=4.00, odds_2_end=1.50)
        decisions = engine.decide(m)
        d_1x = next(d for d in decisions if d.bet_type == "1X")
        assert not d_1x.passes
        assert any("kf1=9.0 > 8" in r for r in d_1x.reasons)

    def test_1x_fails_kf1x_too_low(self):
        engine = DecisionEngine()
        # kf1x = min(kf1, kfx) = min(2.0, 1.3) = 1.3 < 1.5
        m = _make_match(odds_1_end=2.00, odds_x_end=1.30, odds_2_end=1.50)
        decisions = engine.decide(m)
        d_1x = next(d for d in decisions if d.bet_type == "1X")
        assert not d_1x.passes

    def test_1x_fails_kf2_too_low(self):
        engine = DecisionEngine()
        m = _make_match(odds_1_end=3.00, odds_x_end=3.00, odds_2_end=1.30)
        decisions = engine.decide(m)
        d_1x = next(d for d in decisions if d.bet_type == "1X")
        assert not d_1x.passes

    def test_1_passes(self):
        engine = DecisionEngine()
        m = _make_match(odds_1_end=4.00, odds_x_end=3.00, odds_2_end=2.00)
        decisions = engine.decide(m)
        d_1 = next(d for d in decisions if d.bet_type == "1")
        assert d_1.passes

    def test_1_fails_kf2_low(self):
        engine = DecisionEngine()
        m = _make_match(odds_1_end=4.00, odds_x_end=3.00, odds_2_end=1.30)
        decisions = engine.decide(m)
        d_1 = next(d for d in decisions if d.bet_type == "1")
        assert not d_1.passes

    def test_2_passes(self):
        engine = DecisionEngine()
        m = _make_match(odds_1_end=3.50, odds_x_end=3.00, odds_2_end=2.00)
        decisions = engine.decide(m)
        d_2 = next(d for d in decisions if d.bet_type == "2")
        assert d_2.passes

    def test_2_fails_kf2_too_low(self):
        engine = DecisionEngine()
        m = _make_match(odds_1_end=3.50, odds_x_end=3.00, odds_2_end=1.40)
        decisions = engine.decide(m)
        d_2 = next(d for d in decisions if d.bet_type == "2")
        assert not d_2.passes

    def test_x_same_as_1x(self):
        engine = DecisionEngine()
        m = _make_match(odds_1_end=4.00, odds_x_end=3.00, odds_2_end=2.00)
        decisions = engine.decide(m)
        d_1x = next(d for d in decisions if d.bet_type == "1X")
        d_x = next(d for d in decisions if d.bet_type == "X")
        assert d_1x.passes == d_x.passes


class TestDecisionEngineKf2GtKf1:
    """kf2 > kf1 branch (away is underdog)."""

    def test_2_passes(self):
        engine = DecisionEngine()
        m = _make_match(odds_1_end=1.80, odds_x_end=3.50, odds_2_end=4.50)
        decisions = engine.decide(m)
        d_2 = next(d for d in decisions if d.bet_type == "2")
        assert d_2.passes

    def test_2_fails_kf2_too_high(self):
        engine = DecisionEngine()
        m = _make_match(odds_1_end=1.80, odds_x_end=3.50, odds_2_end=9.00)
        decisions = engine.decide(m)
        d_2 = next(d for d in decisions if d.bet_type == "2")
        assert not d_2.passes

    def test_2_fails_kf1_too_low(self):
        engine = DecisionEngine()
        m = _make_match(odds_1_end=1.30, odds_x_end=3.50, odds_2_end=5.00)
        decisions = engine.decide(m)
        d_2 = next(d for d in decisions if d.bet_type == "2")
        assert not d_2.passes

    def test_1_passes(self):
        engine = DecisionEngine()
        m = _make_match(odds_1_end=1.80, odds_x_end=3.50, odds_2_end=4.50)
        decisions = engine.decide(m)
        d_1 = next(d for d in decisions if d.bet_type == "1")
        assert d_1.passes

    def test_1_fails_kf1_too_low(self):
        engine = DecisionEngine()
        m = _make_match(odds_1_end=1.40, odds_x_end=3.50, odds_2_end=4.50)
        decisions = engine.decide(m)
        d_1 = next(d for d in decisions if d.bet_type == "1")
        assert not d_1.passes


class TestDecisionEngineEdge:
    def test_equal_odds_skip(self):
        engine = DecisionEngine()
        m = _make_match(odds_1_end=2.00, odds_x_end=3.00, odds_2_end=2.00)
        decisions = engine.decide(m)
        assert len(decisions) == 1
        assert decisions[0].bet_type == "skip"
        assert not decisions[0].passes

    def test_missing_odds_skip(self):
        engine = DecisionEngine()
        m = _make_match(odds_1_end=None, odds_2_end=None)
        decisions = engine.decide(m)
        assert decisions[0].bet_type == "skip"

    def test_get_passing_decisions(self):
        engine = DecisionEngine()
        m = _make_match(odds_1_end=3.50, odds_x_end=3.20, odds_2_end=2.10)
        passing = engine.get_passing_decisions(m)
        assert all(d.passes for d in passing)
        assert len(passing) > 0

    def test_boundary_kf1_equals_8(self):
        engine = DecisionEngine()
        m = _make_match(odds_1_end=8.00, odds_x_end=4.00, odds_2_end=1.50)
        decisions = engine.decide(m)
        d_1x = next(d for d in decisions if d.bet_type == "1X")
        # kf1 <= 8 should pass
        assert d_1x.passes

    def test_boundary_kf2_equals_1_5(self):
        engine = DecisionEngine()
        m = _make_match(odds_1_end=3.00, odds_x_end=3.00, odds_2_end=1.50)
        decisions = engine.decide(m)
        d_2 = next(d for d in decisions if d.bet_type == "2")
        # kf2 >= 1.5 should pass
        assert d_2.passes


# ─── LeagueSetting model tests ─────────────────────────────────────────


class TestLeagueSetting:
    def test_check_passes_simple_bounds(self):
        s = LeagueSetting(bet_type="1", min_kf1=1.5, max_kf1=999.0)
        assert s.check(2.0, 1.5)
        assert not s.check(1.2, 1.5)  # kf1 < min_kf1

    def test_check_passes_with_relation_kf1_lt_kf2(self):
        s = LeagueSetting(bet_type="1", min_kf1=1.5, kf_relation="kf1<kf2")
        assert s.check(2.0, 3.0)  # kf1 < kf2
        assert not s.check(3.0, 2.0)  # kf1 > kf2

    def test_check_passes_with_relation_kf1_gt_kf2(self):
        s = LeagueSetting(bet_type="2", min_kf2=1.4, kf_relation="kf1>kf2")
        assert s.check(3.0, 2.0)  # kf1 > kf2, kf2 >= 1.4
        assert not s.check(2.0, 3.0)  # kf1 < kf2

    def test_check_max_kf1_bound(self):
        s = LeagueSetting(bet_type="1X", min_kf1=1.5, max_kf1=8.0)
        assert s.check(5.0, 2.0)
        assert not s.check(9.0, 2.0)  # kf1 > max_kf1

    def test_check_none_odds(self):
        s = LeagueSetting(bet_type="1")
        assert not s.check(None, 2.0)
        assert not s.check(2.0, None)
        assert not s.check(None, None)

    def test_check_min_kf2_bound(self):
        s = LeagueSetting(bet_type="2", min_kf2=1.5, kf_relation="kf1>kf2")
        assert s.check(3.0, 2.0)
        assert not s.check(3.0, 1.2)  # kf2 < min_kf2

    def test_default_bounds_pass_anything(self):
        s = LeagueSetting(bet_type="1")
        assert s.check(100.0, 100.0)


class TestLeagueSettingRoi:
    def test_default_roi_zero(self):
        s = LeagueSetting(bet_type="1")
        assert s.roi == 0.0

    def test_roi_set(self):
        s = LeagueSetting(bet_type="1", roi=0.15)
        assert s.roi == 0.15


class TestParseRoi:
    def test_integer_percentage(self):
        from src.decision.league_loader import _parse_roi
        assert abs(_parse_roi(15) - 0.15) < 0.001

    def test_float_fraction(self):
        from src.decision.league_loader import _parse_roi
        assert abs(_parse_roi(0.15) - 0.15) < 0.001

    def test_string_percentage(self):
        from src.decision.league_loader import _parse_roi
        assert abs(_parse_roi("15%") - 0.15) < 0.001

    def test_string_number(self):
        from src.decision.league_loader import _parse_roi
        assert abs(_parse_roi("15") - 0.15) < 0.001

    def test_string_fraction(self):
        from src.decision.league_loader import _parse_roi
        assert abs(_parse_roi("0.15") - 0.15) < 0.001

    def test_comma_decimal(self):
        from src.decision.league_loader import _parse_roi
        assert abs(_parse_roi("15,5") - 0.155) < 0.001

    def test_none(self):
        from src.decision.league_loader import _parse_roi
        assert _parse_roi(None) == 0.0

    def test_empty_string(self):
        from src.decision.league_loader import _parse_roi
        assert _parse_roi("") == 0.0

    def test_garbage(self):
        from src.decision.league_loader import _parse_roi
        assert _parse_roi("abc") == 0.0

    def test_one_percent(self):
        from src.decision.league_loader import _parse_roi
        # 1 is treated as 1% = 0.01 (since > 1.0)
        assert abs(_parse_roi(1.0) - 1.0) < 0.001

    def test_exactly_one(self):
        from src.decision.league_loader import _parse_roi
        # 1.0 is NOT > 1.0, so treated as fraction
        assert _parse_roi(1.0) == 1.0


class TestNormalizeBetType:
    def test_pob1(self):
        assert normalize_bet_type("поб1") == "1"
        assert normalize_bet_type("поб 1") == "1"
        assert normalize_bet_type("Поб1") == "1"

    def test_pob2(self):
        assert normalize_bet_type("поб2") == "2"
        assert normalize_bet_type("поб 2") == "2"
        assert normalize_bet_type("Поб 2") == "2"

    def test_1x(self):
        assert normalize_bet_type("1 или Х") == "1X"
        assert normalize_bet_type("1 или х") == "1X"
        assert normalize_bet_type("1 или X") == "1X"

    def test_draw(self):
        assert normalize_bet_type("ничья") == "X"
        assert normalize_bet_type("Ничья") == "X"

    def test_already_normalized(self):
        assert normalize_bet_type("1") == "1"
        assert normalize_bet_type("2") == "2"
        assert normalize_bet_type("1X") == "1X"
        assert normalize_bet_type("X") == "X"


# ─── LeagueFilter tests ────────────────────────────────────────────────


class TestLeagueFilter:
    def test_filter_passes_allowed(self):
        settings = [LeagueSetting(bet_type="1", leagues=["England. Premier League"])]
        f = LeagueFilter(settings)
        matches = [
            _make_match(league="England. Premier League"),
            _make_match(league="Spain. La Liga"),
        ]
        result = f.filter(matches)
        assert len(result) == 1
        assert result[0].league == "England. Premier League"

    def test_filter_case_insensitive(self):
        settings = [LeagueSetting(bet_type="1", leagues=["england. premier league"])]
        f = LeagueFilter(settings)
        matches = [_make_match(league="England. Premier League")]
        result = f.filter(matches)
        assert len(result) == 1

    def test_filter_via_chemps_zamen(self):
        settings = [LeagueSetting(bet_type="1", leagues=["Англия. Премьер-Лига"])]
        chemps = {"Чемпионат Англии. Премьер-лига": "Англия. Премьер-Лига"}
        f = LeagueFilter(settings, chemps)
        matches = [_make_match(league="Чемпионат Англии. Премьер-лига")]
        result = f.filter(matches)
        assert len(result) == 1

    def test_filter_empty_settings(self):
        f = LeagueFilter([])
        matches = [_make_match()]
        result = f.filter(matches)
        assert len(result) == 0

    def test_find_setting(self):
        s = LeagueSetting(bet_type="1", leagues=["England. Premier League"])
        f = LeagueFilter([s])
        m = _make_match(league="England. Premier League")
        found = f.find_setting(m)
        assert found is s

    def test_find_setting_not_found(self):
        s = LeagueSetting(bet_type="2", leagues=["Spain. La Liga"])
        f = LeagueFilter([s])
        m = _make_match(league="England. Premier League")
        assert f.find_setting(m) is None

    def test_find_all_settings_multiple(self):
        s1 = LeagueSetting(bet_type="1", leagues=["EPL"])
        s2 = LeagueSetting(bet_type="X", leagues=["EPL"])
        f = LeagueFilter([s1, s2])
        m = _make_match(league="EPL")
        found = f.find_all_settings(m)
        assert len(found) == 2
        assert s1 in found and s2 in found

    def test_get_decisions_passes(self):
        s = LeagueSetting(
            bet_type="1",
            leagues=["England. Premier League"],
            min_kf1=1.5,
            kf_relation="kf1<kf2",
        )
        f = LeagueFilter([s])
        m = _make_match(
            league="England. Premier League",
            odds_1_end=2.0,
            odds_2_end=3.0,
        )
        decisions = f.get_decisions(m)
        assert len(decisions) == 1
        assert decisions[0].bet_type == "1"
        assert decisions[0].passes

    def test_get_decisions_fails_condition(self):
        s = LeagueSetting(
            bet_type="1",
            leagues=["England. Premier League"],
            min_kf1=1.5,
            kf_relation="kf1<kf2",
        )
        f = LeagueFilter([s])
        m = _make_match(
            league="England. Premier League",
            odds_1_end=3.0,  # kf1 > kf2 — fails kf1<kf2
            odds_2_end=2.0,
        )
        decisions = f.get_decisions(m)
        assert len(decisions) == 0

    def test_get_decisions_no_setting(self):
        f = LeagueFilter([])
        m = _make_match()
        decisions = f.get_decisions(m)
        assert len(decisions) == 0

    def test_get_kush_league(self):
        chemps = {"NB League": "Kush League"}
        f = LeagueFilter([], chemps)
        assert f.get_kush_league("NB League") == "Kush League"
        assert f.get_kush_league("Unknown") is None


# ─── chemps_zamen loader tests ─────────────────────────────────────────


class TestChempsZamen:
    def test_load_existing(self):
        chemps = load_chemps_zamen()
        assert len(chemps) > 0
        # Should have some known mappings
        assert any("Англия" in v for v in chemps.values())

    def test_load_missing_file(self):
        chemps = load_chemps_zamen("/nonexistent/path/sl_chemps_zamen.json")
        assert chemps == {}


# ─── League loader integration test (with real xlsx) ──────────────────


class TestLeagueLoaderReal:
    """Test loading the example leagues xlsx file."""

    def test_load_example_file(self):
        from src.decision.league_loader import load_league_settings

        settings = load_league_settings(
            "пример загрузочных лиг в прогу.xlsx"
        )
        assert len(settings) == 6

        # Group 1: поб1 → "1", 3 leagues, "Кф1 >= 1.5, Кф1 < Кф2"
        g1 = settings[0]
        assert g1.bet_type == "1"
        assert len(g1.leagues) == 3
        assert g1.min_kf1 == 1.5
        assert g1.kf_relation == "kf1<kf2"

        # Group 2: поб1 → "1", 3 leagues, "Кф1 > Кф2, Кф2 >= 1.4"
        g2 = settings[1]
        assert g2.bet_type == "1"
        assert len(g2.leagues) == 3
        assert g2.min_kf2 == 1.4
        assert g2.kf_relation == "kf1>kf2"

        # Group 3: 1 или Х → "1X", 3 leagues, "Кф1 >= 1.5, Кф1 <= 8"
        g3 = settings[2]
        assert g3.bet_type == "1X"
        assert len(g3.leagues) == 3
        assert g3.min_kf1 == 1.5
        assert g3.max_kf1 == 8.0

        # Group 4: Поб 2 → "2", 3 leagues, "Кф1 < Кф2, Кф1 >= 1.4"
        g4 = settings[3]
        assert g4.bet_type == "2"
        assert len(g4.leagues) == 3
        assert g4.min_kf1 == 1.4
        assert g4.kf_relation == "kf1<kf2"

        # Group 5: поб 2 → "2", 4 leagues, "Кф2 >= 1.5, Кф1 > Кф2"
        g5 = settings[4]
        assert g5.bet_type == "2"
        assert len(g5.leagues) == 4
        assert g5.min_kf2 == 1.5
        assert g5.kf_relation == "kf1>kf2"

        # Group 6: ничья → "X", 4 leagues, "Кф1 >= 1.5, Кф1 <= 8"
        g6 = settings[5]
        assert g6.bet_type == "X"
        assert len(g6.leagues) == 4
        assert g6.min_kf1 == 1.5
        assert g6.max_kf1 == 8.0

    def test_load_missing_file(self):
        from src.decision.league_loader import load_league_settings

        settings = load_league_settings("/nonexistent/leagues.xlsx")
        assert settings == []


# ─── find_leagues_xlsx tests ──────────────────────────────────────────


class TestFindLeaguesXlsx:
    """Test auto-discovery of leagues xlsx files."""

    def test_finds_xlsx_in_dir(self, tmp_path):
        from src.decision.league_loader import find_leagues_xlsx

        (tmp_path / "leagues.xlsx").write_bytes(b"fake")
        result = find_leagues_xlsx(str(tmp_path))
        assert result is not None
        assert result.endswith("leagues.xlsx")

    def test_skips_output_files(self, tmp_path):
        from src.decision.league_loader import find_leagues_xlsx

        (tmp_path / "result_2026-02-21.xlsx").write_bytes(b"fake")
        (tmp_path / "output.xlsx").write_bytes(b"fake")
        result = find_leagues_xlsx(str(tmp_path))
        assert result is None

    def test_skips_temp_files(self, tmp_path):
        from src.decision.league_loader import find_leagues_xlsx

        (tmp_path / "~$leagues.xlsx").write_bytes(b"fake")
        result = find_leagues_xlsx(str(tmp_path))
        assert result is None

    def test_returns_none_for_empty_dir(self, tmp_path):
        from src.decision.league_loader import find_leagues_xlsx

        result = find_leagues_xlsx(str(tmp_path))
        assert result is None

    def test_returns_none_for_nonexistent_dir(self):
        from src.decision.league_loader import find_leagues_xlsx

        result = find_leagues_xlsx("/nonexistent/dir/xyz")
        assert result is None

    def test_picks_first_valid_xlsx(self, tmp_path):
        from src.decision.league_loader import find_leagues_xlsx

        (tmp_path / "aaa_leagues.xlsx").write_bytes(b"fake")
        (tmp_path / "zzz_leagues.xlsx").write_bytes(b"fake")
        result = find_leagues_xlsx(str(tmp_path))
        assert result is not None
        # sorted alphabetically, should pick aaa first
        assert "aaa_leagues.xlsx" in result
