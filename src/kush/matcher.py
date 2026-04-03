"""Event matcher: matches NB-Bet matches to Kush events via fuzzy matching.

Algorithm:
1. Pre-filter Kush events by league (via sl_chemps_zamen mapping)
2. Normalize team names (lower, apply aliases, transliterate ru→en, remove punctuation)
3. Fuzzy: rapidfuzz WRatio on normalized strings, check both team orders
4. TimeScore: linear decay from 1.0 to 0.0 at tolerance boundary
5. Confidence = nameScore * 0.70 + timeScore * 0.30
6. Threshold: >= 0.80 → accepted
7. Near-misses (0.60-0.79) logged for manual review
8. Successful matches with name_score < 0.95 auto-saved as aliases
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Any, Optional

from src.kush.models import KushEvent, MatchResult
from src.kush.normalizer import normalize
from src.nb.models import Match

log = logging.getLogger("parser_nb_bet.kush.matcher")

try:
    from rapidfuzz import fuzz
except ImportError:
    fuzz = None
    log.warning("rapidfuzz not installed, matcher will not work")

# Near-miss confidence range
_NEAR_MISS_MIN = 0.60
_NEAR_MISS_MAX = 0.80  # exclusive (matches >= 0.80 are accepted)

# Auto-save alias threshold: matched (confidence >= 0.85) but names differ (name_score < 0.95)
_AUTO_ALIAS_CONFIDENCE = 0.85
_AUTO_ALIAS_NAME_SCORE = 0.95


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


class NearMissTracker:
    """Tracks near-misses and rejected pairs, auto-saves aliases."""

    def __init__(
        self,
        near_misses_path: str = "",
        rejected_path: str = "",
        aliases_path: str = "",
    ):
        self._near_misses_path = near_misses_path
        self._rejected_path = rejected_path
        self._aliases_path = aliases_path
        self._rejected: set[str] = set()
        self._near_misses: list[dict[str, Any]] = []
        self._load_rejected()

    def _load_rejected(self) -> None:
        """Load rejected pairs from JSON."""
        if not self._rejected_path or not os.path.isfile(self._rejected_path):
            return
        try:
            with open(self._rejected_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._rejected = set(data) if isinstance(data, list) else set()
            log.info("Loaded %d rejected team pairs", len(self._rejected))
        except Exception:
            log.exception("Failed to load rejected pairs from %s", self._rejected_path)

    @staticmethod
    def _make_pair_key(name1: str, name2: str) -> str:
        """Create a canonical key for a team pair."""
        a, b = name1.lower().strip(), name2.lower().strip()
        return f"{min(a,b)}|{max(a,b)}"

    def is_rejected(self, nb_team: str, kush_team: str) -> bool:
        """Check if a team pair was previously rejected."""
        return self._make_pair_key(nb_team, kush_team) in self._rejected

    def record_near_miss(
        self,
        nb_home: str,
        nb_away: str,
        kush_home: str,
        kush_away: str,
        confidence: float,
        name_score: float,
    ) -> None:
        """Record a near-miss for manual review."""
        # Skip if any pair is already rejected
        if self.is_rejected(nb_home, kush_home) or self.is_rejected(nb_away, kush_away):
            return

        entry = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "nb_home": nb_home,
            "nb_away": nb_away,
            "kush_home": kush_home,
            "kush_away": kush_away,
            "confidence": round(confidence, 3),
            "name_score": round(name_score, 3),
            "status": "pending",
        }
        self._near_misses.append(entry)
        log.info(
            "Near-miss recorded: %s vs %s ↔ %s vs %s (conf=%.2f)",
            nb_home, nb_away, kush_home, kush_away, confidence,
        )

    @staticmethod
    def _names_similar(name1: str, name2: str, threshold: float = 0.90) -> bool:
        """Check if two team names are similar enough to be the same team.

        Uses a high threshold (0.90) to avoid saving wrong aliases
        from partial WRatio matches (e.g. "Аль-Шорта Багдад" vs "Аль-Гарраф"
        scores 0.855 due to shared "al" prefix — must NOT be aliased).
        """
        if fuzz is None:
            return False
        score = fuzz.WRatio(normalize(name1), normalize(name2)) / 100.0
        return score >= threshold

    def auto_save_alias(
        self,
        nb_home: str,
        nb_away: str,
        kush_home: str,
        kush_away: str,
    ) -> None:
        """Auto-save team name aliases from a successful match.

        Only saves a pair if individual names are similar (WRatio >= 0.70).
        This prevents saving wrong aliases when the overall match passed
        but individual team names belong to different teams.
        """
        if not self._aliases_path:
            return
        try:
            aliases: dict[str, str] = {}
            if os.path.isfile(self._aliases_path):
                with open(self._aliases_path, "r", encoding="utf-8") as f:
                    aliases = json.load(f)

            changed = False
            for nb_name, kush_name in [(nb_home, kush_home), (nb_away, kush_away)]:
                nb_low = nb_name.lower().strip()
                kush_low = kush_name.lower().strip()
                if nb_low and kush_low and nb_low != kush_low and nb_low not in aliases:
                    if not self._names_similar(nb_name, kush_name):
                        log.debug(
                            "Skip auto-alias: '%s' ≠ '%s' (too different)",
                            nb_low, kush_low,
                        )
                        continue
                    aliases[nb_low] = kush_low
                    changed = True
                    log.info("Auto-alias: '%s' → '%s'", nb_low, kush_low)

            if changed:
                with open(self._aliases_path, "w", encoding="utf-8") as f:
                    json.dump(aliases, f, ensure_ascii=False, indent=2)
        except Exception:
            log.exception("Failed to auto-save alias")

    def flush_near_misses(self) -> None:
        """Save accumulated near-misses to JSON file."""
        if not self._near_misses or not self._near_misses_path:
            return
        try:
            existing: list[dict[str, Any]] = []
            if os.path.isfile(self._near_misses_path):
                with open(self._near_misses_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)

            existing.extend(self._near_misses)
            with open(self._near_misses_path, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)
            log.info("Saved %d near-misses to %s", len(self._near_misses), self._near_misses_path)
            self._near_misses.clear()
        except Exception:
            log.exception("Failed to save near-misses")

    def import_confirmed(self) -> int:
        """Import confirmed near-misses into aliases and clean up.

        Reads near_misses.json, finds entries with status='confirmed',
        adds them to sl_teams_zamen.json, moves rejected to sl_teams_rejected.json.

        Returns number of new aliases imported.
        """
        if not self._near_misses_path or not os.path.isfile(self._near_misses_path):
            return 0

        try:
            with open(self._near_misses_path, "r", encoding="utf-8") as f:
                entries = json.load(f)
        except Exception:
            log.exception("Failed to read near-misses for import")
            return 0

        if not entries:
            return 0

        # Load current aliases and rejected
        aliases: dict[str, str] = {}
        if self._aliases_path and os.path.isfile(self._aliases_path):
            with open(self._aliases_path, "r", encoding="utf-8") as f:
                aliases = json.load(f)

        new_aliases = 0
        remaining = []

        for entry in entries:
            status = entry.get("status", "pending")
            if status == "confirmed":
                for nb_key, kush_key in [("nb_home", "kush_home"), ("nb_away", "kush_away")]:
                    nb_name = entry.get(nb_key, "").lower().strip()
                    kush_name = entry.get(kush_key, "").lower().strip()
                    if nb_name and kush_name and nb_name != kush_name and nb_name not in aliases:
                        aliases[nb_name] = kush_name
                        new_aliases += 1
            elif status == "rejected":
                for nb_key, kush_key in [("nb_home", "kush_home"), ("nb_away", "kush_away")]:
                    nb_name = entry.get(nb_key, "").lower().strip()
                    kush_name = entry.get(kush_key, "").lower().strip()
                    if nb_name and kush_name:
                        pair_key = self._make_pair_key(nb_name, kush_name)
                        self._rejected.add(pair_key)
            else:
                remaining.append(entry)

        # Save updated aliases
        if new_aliases and self._aliases_path:
            with open(self._aliases_path, "w", encoding="utf-8") as f:
                json.dump(aliases, f, ensure_ascii=False, indent=2)
            log.info("Imported %d confirmed aliases", new_aliases)

        # Save updated rejected
        if self._rejected_path:
            with open(self._rejected_path, "w", encoding="utf-8") as f:
                json.dump(sorted(self._rejected), f, ensure_ascii=False, indent=2)

        # Keep only pending entries
        with open(self._near_misses_path, "w", encoding="utf-8") as f:
            json.dump(remaining, f, ensure_ascii=False, indent=2)

        return new_aliases


class EventMatcher:
    """Matches NB-Bet Match objects to KushEvent objects."""

    def __init__(
        self,
        time_tolerance_hours: float = 2.0,
        min_confidence: float = 0.80,
        name_weight: float = 0.70,
        time_weight: float = 0.30,
        tracker: Optional[NearMissTracker] = None,
    ):
        self._tolerance = timedelta(hours=time_tolerance_hours)
        self._min_confidence = min_confidence
        self._name_weight = name_weight
        self._time_weight = time_weight
        self._tracker = tracker

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
            # Auto-save aliases for successful matches with differing names
            if (
                self._tracker
                and best.kush_event
                and best.confidence >= _AUTO_ALIAS_CONFIDENCE
                and best.name_score < _AUTO_ALIAS_NAME_SCORE
            ):
                kev = best.kush_event
                if best.swapped:
                    self._tracker.auto_save_alias(
                        nb_match.team_home, nb_match.team_away,
                        kev.team_away, kev.team_home,
                    )
                else:
                    self._tracker.auto_save_alias(
                        nb_match.team_home, nb_match.team_away,
                        kev.team_home, kev.team_away,
                    )
            return best

        # --- Diagnostic: log why no match was found ---
        if best is not None:
            ev = best.kush_event
            log.info(
                "NO MATCH for '%s' (NB time=%s). Best candidate: eid=%s '%s vs %s' "
                "(Kush time=%s) confidence=%.2f (need %.2f) "
                "name=%.2f time=%.2f swapped=%s",
                nb_match.match_key,
                nb_match.start_time_utc.strftime("%H:%M %d.%m"),
                ev.event_id if ev else "?",
                ev.team_home if ev else "?",
                ev.team_away if ev else "?",
                ev.start_time_utc.strftime("%H:%M %d.%m") if ev else "?",
                best.confidence,
                self._min_confidence,
                best.name_score,
                best.time_score,
                best.swapped,
            )
            # Record near-miss for manual review
            if (
                self._tracker
                and ev
                and _NEAR_MISS_MIN <= best.confidence < _NEAR_MISS_MAX
            ):
                if best.swapped:
                    self._tracker.record_near_miss(
                        nb_match.team_home, nb_match.team_away,
                        ev.team_away, ev.team_home,
                        best.confidence, best.name_score,
                    )
                else:
                    self._tracker.record_near_miss(
                        nb_match.team_home, nb_match.team_away,
                        ev.team_home, ev.team_away,
                        best.confidence, best.name_score,
                    )
        else:
            log.info(
                "NO MATCH for '%s' (NB time=%s). "
                "0 candidates passed time filter (tolerance=%.1fh). "
                "Total events checked: %d",
                nb_match.match_key,
                nb_match.start_time_utc.strftime("%H:%M %d.%m"),
                self._tolerance.total_seconds() / 3600,
                len(candidates),
            )
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
