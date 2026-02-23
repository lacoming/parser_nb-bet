"""NB-Bet match data models."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Match:
    """Normalized match from NB-Bet API."""

    match_key: str  # "{league}|{home}|{away}|{date:%Y%m%d}"
    league: str
    team_home: str
    team_away: str
    start_time_utc: datetime
    nb_slug: str
    sport: str  # "soccer" | "hockey"
    odds_1_start: float | None = None
    odds_x_start: float | None = None
    odds_2_start: float | None = None
    odds_1_end: float | None = None
    odds_x_end: float | None = None
    odds_2_end: float | None = None

    @property
    def odds_1x_start(self) -> float | None:
        """Double chance 1X = min(kf1, kfX) from START odds — used in ratio formula."""
        if self.odds_1_start is not None and self.odds_x_start is not None:
            return min(self.odds_1_start, self.odds_x_start)
        return None

    @property
    def odds_1x_end(self) -> float | None:
        """Double chance 1X = min(kf1, kfX) — used in decision engine."""
        if self.odds_1_end is not None and self.odds_x_end is not None:
            return min(self.odds_1_end, self.odds_x_end)
        return None

    @staticmethod
    def make_key(league: str, home: str, away: str, dt: datetime) -> str:
        return f"{league}|{home}|{away}|{dt.strftime('%Y%m%d')}"
