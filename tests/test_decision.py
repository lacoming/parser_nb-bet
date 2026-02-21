"""Tests for decision engine, league filter, and league loader."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.decision.engine import DecisionEngine
from src.decision.league_filter import LeagueFilter, load_chemps_zamen
from src.decision.models import BetDecision, LeagueSetting
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


# ─── LeagueFilter tests ────────────────────────────────────────────────


class TestLeagueFilter:
    def test_filter_passes_allowed(self):
        settings = [LeagueSetting(sport="football", leagues=["England. Premier League"])]
        f = LeagueFilter(settings)
        matches = [
            _make_match(league="England. Premier League"),
            _make_match(league="Spain. La Liga"),
        ]
        result = f.filter(matches)
        assert len(result) == 1
        assert result[0].league == "England. Premier League"

    def test_filter_case_insensitive(self):
        settings = [LeagueSetting(sport="football", leagues=["england. premier league"])]
        f = LeagueFilter(settings)
        matches = [_make_match(league="England. Premier League")]
        result = f.filter(matches)
        assert len(result) == 1

    def test_filter_via_chemps_zamen(self):
        settings = [LeagueSetting(sport="football", leagues=["Англия. Премьер-Лига"])]
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
        s = LeagueSetting(sport="football", leagues=["England. Premier League"], bet_nb="МП")
        f = LeagueFilter([s])
        m = _make_match(league="England. Premier League")
        found = f.find_setting(m)
        assert found is s

    def test_find_setting_not_found(self):
        s = LeagueSetting(sport="football", leagues=["Spain. La Liga"])
        f = LeagueFilter([s])
        m = _make_match(league="England. Premier League")
        assert f.find_setting(m) is None

    def test_get_kush_league(self):
        chemps = {"NB League": "Kush League"}
        f = LeagueFilter([], chemps)
        assert f.get_kush_league("NB League") == "Kush League"
        assert f.get_kush_league("Unknown") is None


# ─── LeagueSetting model tests ─────────────────────────────────────────


class TestLeagueSetting:
    def test_is_inverted_same(self):
        s = LeagueSetting(sport="football", bet_nb="МП", bet_kush="МП")
        assert not s.is_inverted

    def test_is_inverted_different(self):
        s = LeagueSetting(sport="football", bet_nb="МП", bet_kush="ПП")
        assert s.is_inverted

    def test_is_inverted_empty_kush(self):
        s = LeagueSetting(sport="football", bet_nb="МП", bet_kush="")
        assert not s.is_inverted


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
