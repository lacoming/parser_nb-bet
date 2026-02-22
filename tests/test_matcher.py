"""Tests for NB-Kush event matcher."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.kush.matcher import EventMatcher
from src.kush.models import KushEvent, MatchResult
from src.nb.models import Match


def _nb_match(**kwargs) -> Match:
    defaults = dict(
        match_key="k",
        league="England. Premier League",
        team_home="Manchester United",
        team_away="Liverpool",
        start_time_utc=datetime(2026, 2, 21, 15, 0, tzinfo=timezone.utc),
        nb_slug="man-utd-vs-liverpool",
        sport="soccer",
        odds_1_end=2.50,
        odds_x_end=3.20,
        odds_2_end=2.80,
    )
    defaults.update(kwargs)
    return Match(**defaults)


def _kush_event(**kwargs) -> KushEvent:
    defaults = dict(
        event_id="123",
        league="Англия. Премьер-Лига",
        team_home="Manchester United",
        team_away="Liverpool",
        start_time_utc=datetime(2026, 2, 21, 15, 0, tzinfo=timezone.utc),
    )
    defaults.update(kwargs)
    return KushEvent(**defaults)


class TestEventMatcher:
    def test_exact_match(self):
        matcher = EventMatcher()
        nb = _nb_match()
        kush = [_kush_event()]
        result = matcher.find_best_match(nb, kush)
        assert result is not None
        assert result.confidence >= 0.80
        assert result.kush_event.event_id == "123"

    def test_no_match_wrong_teams(self):
        matcher = EventMatcher()
        nb = _nb_match()
        kush = [_kush_event(team_home="Barcelona", team_away="Real Madrid")]
        result = matcher.find_best_match(nb, kush)
        assert result is None

    def test_time_within_tolerance(self):
        matcher = EventMatcher(time_tolerance_hours=2.0)
        nb = _nb_match()
        kush = [_kush_event(
            start_time_utc=datetime(2026, 2, 21, 16, 0, tzinfo=timezone.utc)
        )]
        result = matcher.find_best_match(nb, kush)
        assert result is not None
        assert result.time_score > 0

    def test_time_outside_tolerance(self):
        matcher = EventMatcher(time_tolerance_hours=1.0)
        nb = _nb_match()
        kush = [_kush_event(
            start_time_utc=datetime(2026, 2, 21, 20, 0, tzinfo=timezone.utc)
        )]
        result = matcher.find_best_match(nb, kush)
        assert result is None

    def test_swapped_teams(self):
        matcher = EventMatcher()
        nb = _nb_match()
        kush = [_kush_event(
            team_home="Liverpool",
            team_away="Manchester United",
        )]
        result = matcher.find_best_match(nb, kush)
        assert result is not None
        assert result.swapped is True

    def test_cyrillic_vs_latin(self):
        matcher = EventMatcher()
        nb = _nb_match(team_home="Спартак Москва", team_away="ЦСКА Москва")
        kush = [_kush_event(
            team_home="Spartak Moskva",
            team_away="CSKA Moskva",
        )]
        result = matcher.find_best_match(nb, kush)
        # Transliteration should make these match
        assert result is not None

    def test_best_of_multiple(self):
        matcher = EventMatcher()
        nb = _nb_match()
        kush = [
            _kush_event(event_id="bad", team_home="Chelsea", team_away="Arsenal"),
            _kush_event(event_id="good"),  # exact match
        ]
        result = matcher.find_best_match(nb, kush)
        assert result is not None
        assert result.kush_event.event_id == "good"

    def test_empty_events_list(self):
        matcher = EventMatcher()
        nb = _nb_match()
        result = matcher.find_best_match(nb, [])
        assert result is None

    def test_confidence_threshold(self):
        matcher = EventMatcher(min_confidence=0.95)
        nb = _nb_match(team_home="Man Utd", team_away="Liverpool FC")
        kush = [_kush_event(
            team_home="Manchester United",
            team_away="Liverpool",
        )]
        result = matcher.find_best_match(nb, kush)
        # With abbreviated names, confidence may be below 0.95
        # This tests that threshold is enforced
        if result is not None:
            assert result.confidence >= 0.95

    def test_time_score_exact(self):
        matcher = EventMatcher()
        score = matcher._compute_time_score(
            datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
            datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
        )
        assert score == 1.0

    def test_time_score_at_boundary(self):
        matcher = EventMatcher(time_tolerance_hours=2.0)
        t1 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        t2 = t1 + timedelta(hours=2)
        score = matcher._compute_time_score(t1, t2)
        assert score == 0.0

    def test_time_score_half_tolerance(self):
        matcher = EventMatcher(time_tolerance_hours=2.0)
        t1 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        t2 = t1 + timedelta(hours=1)
        score = matcher._compute_time_score(t1, t2)
        assert abs(score - 0.5) < 0.01

    def test_name_score_identical(self):
        score = EventMatcher._compute_name_score(
            "Manchester United", "Liverpool",
            "Manchester United", "Liverpool",
        )
        assert score > 0.95

    def test_name_score_different(self):
        score = EventMatcher._compute_name_score(
            "Manchester United", "Liverpool",
            "Barcelona", "Real Madrid",
        )
        assert score < 0.50

    def test_slightly_different_names(self):
        matcher = EventMatcher()
        nb = _nb_match(team_home="Manchester Utd", team_away="Liverpool FC")
        kush = [_kush_event(
            team_home="Manchester United",
            team_away="Liverpool",
        )]
        result = matcher.find_best_match(nb, kush)
        assert result is not None

    def test_match_result_dataclass(self):
        r = MatchResult(
            nb_match_key="k",
            kush_event=None,
            confidence=0.85,
            name_score=0.90,
            time_score=0.73,
        )
        assert r.confidence == 0.85
        assert r.swapped is False

    def test_league_prefilter_narrows_candidates(self):
        """When kush_league_name is provided, only matching events are considered."""
        matcher = EventMatcher()
        nb = _nb_match()
        good = _kush_event(event_id="good", league="Англия. Премьер-Лига")
        bad = _kush_event(
            event_id="bad",
            league="Испания. Ла Лига",
            team_home="Manchester United",
            team_away="Liverpool",
        )
        result = matcher.find_best_match(nb, [bad, good], kush_league_name="Англия. Премьер-Лига")
        assert result is not None
        assert result.kush_event.event_id == "good"

    def test_league_prefilter_fallback_to_all(self):
        """When no events match the league, fall back to all events."""
        matcher = EventMatcher()
        nb = _nb_match()
        kush = [_kush_event(event_id="123", league="Англия. Чемпионшип")]
        result = matcher.find_best_match(nb, kush, kush_league_name="Несуществующая лига")
        # Should still find the match via fallback
        assert result is not None

    def test_league_prefilter_none_uses_all(self):
        """When kush_league_name is None, all events are searched."""
        matcher = EventMatcher()
        nb = _nb_match()
        kush = [_kush_event()]
        result = matcher.find_best_match(nb, kush, kush_league_name=None)
        assert result is not None

    def test_league_prefilter_partial_match(self):
        """League name uses 'in' matching for flexibility."""
        matcher = EventMatcher()
        nb = _nb_match()
        kush = [_kush_event(league="Англия. Премьер-Лига (осн.)")]
        result = matcher.find_best_match(nb, kush, kush_league_name="Премьер-Лига")
        assert result is not None
