"""League filter: matches NB-Bet league names to strategy settings.

Uses sl_chemps_zamen.json for NB→Kush league name normalization.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from src.paths import data_path

from src.decision.models import BetDecision, LeagueSetting
from src.nb.models import Match

log = logging.getLogger("parser_nb_bet.decision.league_filter")


def load_chemps_zamen(path: Optional[str] = None) -> dict[str, str]:
    """Load sl_chemps_zamen.json: NB league name → Kush league name mapping."""
    if path is None:
        path = data_path("sl_chemps_zamen.json")
    p = Path(path).resolve()
    if not p.exists():
        log.warning("sl_chemps_zamen.json not found at %s", p)
        return {}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


class LeagueFilter:
    """Filter matches by league settings from leagues.xlsx."""

    def __init__(
        self,
        settings: list[LeagueSetting],
        chemps_zamen: Optional[dict[str, str]] = None,
    ):
        self._settings = settings
        self._chemps = chemps_zamen or {}
        # Build set of all allowed leagues (from all strategy groups)
        self._allowed_leagues: set[str] = set()
        for s in settings:
            for league in s.leagues:
                self._allowed_leagues.add(league.lower())

    def filter(self, matches: list[Match]) -> list[Match]:
        """Return only matches whose league is in the strategy settings."""
        result = []
        for m in matches:
            if self._is_league_allowed(m.league):
                result.append(m)
        log.info("LeagueFilter: %d/%d matches passed", len(result), len(matches))
        return result

    def find_setting(self, match: Match) -> Optional[LeagueSetting]:
        """Find the strategy setting that applies to this match's league."""
        for s in self._settings:
            for league in s.leagues:
                if league.lower() == match.league.lower():
                    return s
            # Try via chemps_zamen mapping
            kush_league = self._chemps.get(match.league)
            if kush_league:
                for league in s.leagues:
                    if league.lower() == kush_league.lower():
                        return s
        return None

    def find_all_settings(self, match: Match) -> list[LeagueSetting]:
        """Find all strategy settings that apply to this match's league.

        A league may appear in multiple groups with different bet types.
        """
        result = []
        for s in self._settings:
            for league in s.leagues:
                if league.lower() == match.league.lower():
                    result.append(s)
                    break
            else:
                # Try via chemps_zamen mapping
                kush_league = self._chemps.get(match.league)
                if kush_league:
                    for league in s.leagues:
                        if league.lower() == kush_league.lower():
                            result.append(s)
                            break
        return result

    def get_decisions(self, match: Match) -> list[BetDecision]:
        """Get bet decisions for a match based on its league settings.

        Finds the applicable setting, checks conditions against match odds,
        and returns a BetDecision for each matching setting.
        """
        settings = self.find_all_settings(match)
        if not settings:
            return []

        decisions = []
        kf1 = match.odds_1_end
        kf2 = match.odds_2_end

        for s in settings:
            if s.check(kf1, kf2):
                decisions.append(BetDecision(
                    bet_type=s.bet_type,
                    passes=True,
                    reasons=[f"league condition: {s.condition_raw}"],
                ))
            else:
                log.debug(
                    "Conditions not met for %s bet=%s: kf1=%s kf2=%s cond=%s",
                    match.match_key, s.bet_type, kf1, kf2, s.condition_raw,
                )
        return decisions

    def get_kush_league(self, nb_league: str) -> Optional[str]:
        """Get Kush league name for an NB league (via sl_chemps_zamen)."""
        return self._chemps.get(nb_league)

    def _is_league_allowed(self, league: str) -> bool:
        """Check if league is in allowed set (direct or via mapping)."""
        if league.lower() in self._allowed_leagues:
            return True
        # Try chemps_zamen mapping
        kush_name = self._chemps.get(league, "")
        if kush_name and kush_name.lower() in self._allowed_leagues:
            return True
        return False
