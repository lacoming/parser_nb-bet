"""Decision engine data models."""
from __future__ import annotations

from dataclasses import dataclass, field


# Mapping: Russian bet type text → normalized bet type code
_BET_TYPE_MAP: dict[str, str] = {
    "поб1": "1",
    "поб 1": "1",
    "п1": "1",
    "1": "1",
    "поб2": "2",
    "поб 2": "2",
    "п2": "2",
    "2": "2",
    "1 или х": "1X",
    "1 или x": "1X",  # Latin X
    "1x": "1X",
    "1х": "1X",  # Cyrillic Х
    "ничья": "X",
    "x": "X",
    "х": "X",  # Cyrillic Х
}


def normalize_bet_type(raw: str) -> str:
    """Normalize Russian bet type text to code: '1' | '1X' | '2' | 'X'."""
    key = raw.strip().lower()
    return _BET_TYPE_MAP.get(key, key.upper())


@dataclass
class LeagueSetting:
    """One strategy group from leagues.xlsx.

    Represents a set of leagues that share the same bet type and conditions.

    Excel format (3 columns):
      A: Вид ставки (bet type)   — starts a new group
      B: Лиги (league names)     — one per row
      C: условие (condition text) — on first row of group
    """

    bet_type: str  # "1" | "1X" | "2" | "X"
    leagues: list[str] = field(default_factory=list)
    condition_raw: str = ""  # Original condition text from Excel

    # ROI percentage for this league group (e.g. 0.15 = 15%)
    roi: float = 0.0

    # Parsed condition bounds (set by condition parser)
    min_kf1: float = 0.0
    max_kf1: float = 999.0
    min_kf2: float = 0.0
    max_kf2: float = 999.0
    kf_relation: str = ""  # "kf1>kf2" | "kf1<kf2" | ""

    def check(self, kf1: float | None, kf2: float | None) -> bool:
        """Check if match odds satisfy this setting's conditions.

        Returns False if odds are None or don't meet the constraints.
        """
        if kf1 is None or kf2 is None:
            return False
        if kf1 < self.min_kf1 or kf1 > self.max_kf1:
            return False
        if kf2 < self.min_kf2 or kf2 > self.max_kf2:
            return False
        if self.kf_relation == "kf1>kf2" and not (kf1 > kf2):
            return False
        if self.kf_relation == "kf1<kf2" and not (kf1 < kf2):
            return False
        return True


@dataclass
class BetDecision:
    """Result of decision engine evaluation."""

    bet_type: str  # "1X" | "1" | "2" | "X" | "skip"
    passes: bool
    reasons: list[str] = field(default_factory=list)
