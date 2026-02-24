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


# ---------------------------------------------------------------------------
# BUG-2: Both sites use MSK — no conversion, tolerance handles small diffs
# ---------------------------------------------------------------------------

class TestBug2_MskTimesNoConversion:
    """BUG-2: NB and Kush both use MSK. Times stored as-is, no UTC shift."""

    def test_same_msk_time_matches(self):
        """Same MSK time on both sides → perfect time score."""
        matcher = EventMatcher(time_tolerance_hours=5.0)
        # Both show 18:00 MSK (stored as-is)
        nb = _nb_match(start_time_utc=datetime(2026, 2, 25, 18, 0, tzinfo=timezone.utc))
        kush = [_kush_event(start_time_utc=datetime(2026, 2, 25, 18, 0, tzinfo=timezone.utc))]
        result = matcher.find_best_match(nb, kush)
        assert result is not None
        assert result.time_score == 1.0

    def test_3h_diff_matches_with_5h_tolerance(self):
        """NB=22:30 MSK Feb 25, Kush=1:30 MSK Feb 26 (3h diff) — must match.

        time_score = 1 - 3/5 = 0.40
        confidence = 1.0 * 0.70 + 0.40 * 0.30 = 0.82 >= 0.80 ✓
        """
        matcher = EventMatcher(time_tolerance_hours=5.0)
        # NB shows 22:30 on Feb 25 (MSK)
        nb = _nb_match(start_time_utc=datetime(2026, 2, 25, 22, 30, tzinfo=timezone.utc))
        # Kush shows 1:30 on Feb 26 (MSK, stored as-is without UTC shift)
        kush = [_kush_event(start_time_utc=datetime(2026, 2, 26, 1, 30, tzinfo=timezone.utc))]
        result = matcher.find_best_match(nb, kush)
        assert result is not None
        assert result.confidence >= 0.80
        # Time score: 3h diff / 5h tolerance = 0.40
        assert abs(result.time_score - 0.40) < 0.01

    def test_3h_diff_fails_with_2h_tolerance(self):
        """3h diff exceeds 2h tolerance — should not match (time_score=0)."""
        matcher = EventMatcher(time_tolerance_hours=2.0)
        nb = _nb_match(start_time_utc=datetime(2026, 2, 25, 22, 30, tzinfo=timezone.utc))
        kush = [_kush_event(start_time_utc=datetime(2026, 2, 26, 1, 30, tzinfo=timezone.utc))]
        result = matcher.find_best_match(nb, kush)
        # 3h > 2h tolerance → time_score=0 → confidence < 0.80
        assert result is None


# ---------------------------------------------------------------------------
# BUG-3: Latin slug matching (parallel to Russian fuzzy matching)
# ---------------------------------------------------------------------------

class TestBug3_SlugMatching:
    """BUG-3: Match events using Latin slug-names from URLs."""

    def test_slug_match_when_russian_names_differ(self):
        """Slug match should rescue a match where Russian names diverge."""
        matcher = EventMatcher()
        # NB has slug with Latin names; Russian names are very different on Kush
        nb = _nb_match(
            team_home="Аль-Ахли",
            team_away="Аль-Хиляль",
            nb_slug="al-ahli-vs-al-hilal-prognoz-na-match",
        )
        kush = [_kush_event(
            team_home="Аль Ахли Джидда",
            team_away="Аль Хилал Рияд",
            url="/event/99999-al-ahli-al-hilal",
        )]
        result = matcher.find_best_match(nb, kush)
        assert result is not None
        assert result.confidence >= 0.80

    def test_slug_match_exact_latin(self):
        """Both slugs have near-identical Latin names → high slug score."""
        matcher = EventMatcher()
        nb = _nb_match(
            team_home="Foo",
            team_away="Bar",
            nb_slug="manchester-united-vs-liverpool-prognoz-na-match",
        )
        kush = [_kush_event(
            team_home="Манчестер Юнайтед",
            team_away="Ливерпуль",
            url="/event/100-manchester-united-vs-liverpool",
        )]
        result = matcher.find_best_match(nb, kush)
        assert result is not None
        assert result.name_score > 0.70

    def test_slug_no_url_falls_back_to_russian(self):
        """If Kush event has no URL, only Russian matching is used."""
        matcher = EventMatcher()
        nb = _nb_match(
            nb_slug="man-utd-vs-liverpool-prognoz-na-match",
        )
        kush = [_kush_event(url="")]
        result = matcher.find_best_match(nb, kush)
        # Should still match via Russian names
        assert result is not None

    def test_slug_no_nb_slug_falls_back_to_russian(self):
        """If NB match has empty slug, only Russian matching is used."""
        matcher = EventMatcher()
        nb = _nb_match(nb_slug="")
        kush = [_kush_event(url="/event/100-man-utd-liverpool")]
        result = matcher.find_best_match(nb, kush)
        # Should still match via Russian names
        assert result is not None

    def test_slug_picks_better_of_two_strategies(self):
        """The matcher should pick the higher score from slug vs Russian."""
        matcher = EventMatcher()
        # Russian names are identical → name_score ~1.0
        nb = _nb_match(
            team_home="Manchester United",
            team_away="Liverpool",
            nb_slug="totally-wrong-slug-prognoz-na-match",
        )
        kush = [_kush_event(
            team_home="Manchester United",
            team_away="Liverpool",
            url="/event/100-other-slug",
        )]
        result = matcher.find_best_match(nb, kush)
        assert result is not None
        # Russian match should dominate (slug is garbage)
        assert result.name_score > 0.90

    def test_slug_swapped_order(self):
        """Slug matching should handle swapped home/away."""
        matcher = EventMatcher()
        nb = _nb_match(
            team_home="Foo",
            team_away="Bar",
            nb_slug="arsenal-vs-chelsea-prognoz-na-match",
        )
        kush = [_kush_event(
            team_home="Foo2",
            team_away="Bar2",
            url="/event/100-chelsea-arsenal",
        )]
        result = matcher.find_best_match(nb, kush)
        # Slug names are swapped but should still score well
        assert result is not None
