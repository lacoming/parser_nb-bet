"""Event matcher: matches NB-Bet matches to Kush events via fuzzy matching.

Algorithm (from ARCHITECTURE.md):
1. Normalize team names (lower, transliterate ru→en, remove punctuation)
2. Fuzzy: rapidfuzz WRatio on normalized strings, check both team orders
3. TimeScore: linear decay from 1.0 to 0.0 at tolerance boundary
4. Confidence = nameScore * 0.70 + timeScore * 0.30
5. Threshold: >= 0.80 → accepted
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from src.kush.models import KushEvent, MatchResult
from src.kush.normalizer import normalize
from src.nb.models import Match

log = logging.getLogger("parser_nb_bet.kush.matcher")

try:
    from rapidfuzz import fuzz
except ImportError:
    fuzz = None
    log.warning("rapidfuzz not installed, matcher will not work")


class EventMatcher:
    """Matches NB-Bet Match objects to KushEvent objects."""

    def __init__(
        self,
        time_tolerance_hours: float = 2.0,
        min_confidence: float = 0.80,
        name_weight: float = 0.70,
        time_weight: float = 0.30,
    ):
        self._tolerance = timedelta(hours=time_tolerance_hours)
        self._min_confidence = min_confidence
        self._name_weight = name_weight
        self._time_weight = time_weight

    def find_best_match(
        self,
        nb_match: Match,
        kush_events: list[KushEvent],
    ) -> Optional[MatchResult]:
        """Find the best matching Kush event for an NB-Bet match.

        Returns MatchResult if confidence >= min_confidence, else None.
        """
        best: Optional[MatchResult] = None

        for event in kush_events:
            result = self._score(nb_match, event)
            if result is None:
                continue
            if best is None or result.confidence > best.confidence:
                best = result

        if best is not None and best.confidence >= self._min_confidence:
            log.debug(
                "Matched %s ↔ %s (confidence=%.2f)",
                nb_match.match_key, best.kush_event.event_id if best.kush_event else "?",
                best.confidence,
            )
            return best

        return None

    def _score(self, nb_match: Match, event: KushEvent) -> Optional[MatchResult]:
        """Score a single NB-Kush pair."""
        # Time score
        time_score = self._compute_time_score(
            nb_match.start_time_utc, event.start_time_utc
        )
        if time_score <= 0:
            return None

        # Name score: try both orders (home/away normal and swapped)
        name_score_normal = self._compute_name_score(
            nb_match.team_home, nb_match.team_away,
            event.team_home, event.team_away,
        )
        name_score_swapped = self._compute_name_score(
            nb_match.team_home, nb_match.team_away,
            event.team_away, event.team_home,
        )

        if name_score_swapped > name_score_normal:
            name_score = name_score_swapped
            swapped = True
        else:
            name_score = name_score_normal
            swapped = False

        confidence = name_score * self._name_weight + time_score * self._time_weight

        return MatchResult(
            nb_match_key=nb_match.match_key,
            kush_event=event,
            confidence=confidence,
            name_score=name_score,
            time_score=time_score,
            swapped=swapped,
        )

    def _compute_time_score(self, t1: datetime, t2: datetime) -> float:
        """Linear decay: 1.0 at exact match, 0.0 at tolerance boundary."""
        diff = abs((t1 - t2).total_seconds())
        max_seconds = self._tolerance.total_seconds()
        if max_seconds <= 0:
            return 1.0 if diff == 0 else 0.0
        if diff >= max_seconds:
            return 0.0
        return 1.0 - (diff / max_seconds)

    @staticmethod
    def _compute_name_score(
        home1: str, away1: str, home2: str, away2: str,
    ) -> float:
        """Compute name similarity using rapidfuzz WRatio.

        Returns score in [0, 1].
        """
        if fuzz is None:
            return 0.0

        h1 = normalize(home1)
        h2 = normalize(home2)
        a1 = normalize(away1)
        a2 = normalize(away2)

        # WRatio returns 0-100
        home_score = fuzz.WRatio(h1, h2) / 100.0
        away_score = fuzz.WRatio(a1, a2) / 100.0

        return (home_score + away_score) / 2.0
