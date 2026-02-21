"""Decision engine data models."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LeagueSetting:
    """One strategy row from leagues.xlsx."""

    sport: str  # "football" | "hockey"
    leagues: list[str] = field(default_factory=list)
    min_kf: float = 0.0
    max_kf: float = 100.0
    bet_nb: str = ""  # bet type name on NB-Bet (e.g. "МП")
    bet_kush: str = ""  # bet type name on Kush (e.g. "МП" or inverted)

    @property
    def is_inverted(self) -> bool:
        """True if kush bet type differs from NB bet type (inverted bet)."""
        return (
            self.bet_nb.strip().lower() != self.bet_kush.strip().lower()
            and self.bet_kush.strip() != ""
        )


@dataclass
class BetDecision:
    """Result of decision engine evaluation."""

    bet_type: str  # "1X" | "1" | "2" | "X" | "skip"
    passes: bool
    reasons: list[str] = field(default_factory=list)
