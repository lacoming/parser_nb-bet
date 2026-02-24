"""Event matcher: matches NB-Bet matches to Kush events via fuzzy matching.

Algorithm:
1. Pre-filter Kush events by league (via sl_chemps_zamen mapping)
2. Normalize team names (lower, transliterate ru→en, remove punctuation)
3. Fuzzy: rapidfuzz WRatio on normalized strings, check both team orders
4. TimeScore: linear decay from 1.0 to 0.0 at tolerance boundary
5. Confidence = nameScore * 0.70 + timeScore * 0.30
6. Threshold: >= 0.80 → accepted
"""
from __future__ import annotations

import logging
import re
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


def _extract_slug_teams(slug: str) -> tuple[str, str]:
    """Extract team names from NB slug like 'al-dzhubail-al-batin-prognoz-na-match'.

    Removes the trailing '-prognoz-na-match' suffix and splits on '-vs-' or
    mid-point heuristic.
    """
    if not slug:
        return ("", "")
    # Remove common suffixes
    slug = re.sub(r"-prognoz-na-match$", "", slug)
    slug = re.sub(r"-prognozy?$", "", slug)
    # Try splitting on common separators
    for sep in ("-vs-", "-v-"):
        if sep in slug:
            parts = slug.split(sep, 1)
            return (parts[0].replace("-", " ").strip(), parts[1].replace("-", " ").strip())
    return (slug.replace("-", " ").strip(), "")


def _extract_kush_slug_teams(url: str) -> tuple[str, str]:
    """Extract team names from Kush URL like '/event/12345-team1-team2'."""
    if not url:
        return ("", "")
    m = re.search(r"/event/\d+-(.*)", url)
    if not m:
        return ("", "")
    slug = m.group(1)
    # Kush slugs use '-' as separator; try to split on '-vs-'
    for sep in ("-vs-", "-v-"):
        if sep in slug:
            parts = slug.split(sep, 1)
            return (parts[0].replace("-", " ").strip(), parts[1].replace("-", " ").strip())
    return (slug.replace("-", " ").strip(), "")


def _slug_pair_score(h1: str, a1: str, h2: str, a2: str) -> float:
    """Compute WRatio similarity between two pairs of slug-extracted team names.

    Returns score in [0, 1].
    """
    if fuzz is None:
        return 0.0
    home_score = fuzz.WRatio(h1, h2) / 100.0
    if a1 and a2:
        away_score = fuzz.WRatio(a1, a2) / 100.0
        return (home_score + away_score) / 2.0
    # If one side has no away team, use only home score (penalized)
    return home_score * 0.7


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
        kush_league_name: Optional[str] = None,
    ) -> Optional[MatchResult]:
        """Find the best matching Kush event for an NB-Bet match.

        Args:
            nb_match: The NB-Bet match to find on Kush.
            kush_events: All available Kush events.
            kush_league_name: Expected Kush league name (from sl_chemps_zamen).
                If provided, events are pre-filtered by league first.

        Returns MatchResult if confidence >= min_confidence, else None.
        """
        # Pre-filter by league if mapping is available
        candidates = kush_events
        if kush_league_name:
            filtered = [
                e for e in kush_events
                if e.league and kush_league_name.lower() in e.league.lower()
            ]
            if filtered:
                candidates = filtered
                log.debug(
                    "League pre-filter: %d -> %d events for '%s'",
                    len(kush_events), len(filtered), kush_league_name,
                )
            else:
                # No events matched by league — fall back to all events
                log.debug(
                    "League pre-filter found 0 events for '%s', using all %d",
                    kush_league_name, len(kush_events),
                )

        best: Optional[MatchResult] = None

        for event in candidates:
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
        """Score a single NB-Kush pair.

        Uses two parallel matching strategies and picks the best:
        1. Fuzzy match on Russian/original team names (existing)
        2. Fuzzy match on Latin slugs from URLs (BUG-3)
        """
        # Time score
        time_score = self._compute_time_score(
            nb_match.start_time_utc, event.start_time_utc
        )
        if time_score <= 0:
            return None

        # --- Strategy 1: fuzzy match on team names (Russian/original) ---
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

        # --- Strategy 2: fuzzy match on Latin slugs from URLs (BUG-3) ---
        slug_score, slug_swapped = self._compute_slug_score(nb_match, event)
        if slug_score > name_score:
            log.debug(
                "Slug score %.2f > name score %.2f for %s ↔ eid=%s",
                slug_score, name_score, nb_match.match_key, event.event_id,
            )
            name_score = slug_score
            swapped = slug_swapped

        confidence = name_score * self._name_weight + time_score * self._time_weight

        return MatchResult(
            nb_match_key=nb_match.match_key,
            kush_event=event,
            confidence=confidence,
            name_score=name_score,
            time_score=time_score,
            swapped=swapped,
        )

    @staticmethod
    def _compute_slug_score(
        nb_match: Match, event: KushEvent,
    ) -> tuple[float, bool]:
        """Compute name similarity using Latin slugs from URLs.

        Extracts team names from NB slug (e.g. 'al-ahli-vs-al-hilal-prognoz-na-match')
        and Kush URL (e.g. '/event/12345-al-ahli-al-hilal'), then runs WRatio
        on the extracted Latin names.

        Returns (score, swapped) tuple.
        """
        if fuzz is None:
            return (0.0, False)

        nb_h, nb_a = _extract_slug_teams(nb_match.nb_slug)
        ku_h, ku_a = _extract_kush_slug_teams(event.url)

        if not nb_h or not ku_h:
            return (0.0, False)

        # Normal order
        score_normal = _slug_pair_score(nb_h, nb_a, ku_h, ku_a)
        # Swapped order
        score_swapped = _slug_pair_score(nb_h, nb_a, ku_a, ku_h) if ku_a else 0.0

        if score_swapped > score_normal:
            return (score_swapped, True)
        return (score_normal, False)

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
