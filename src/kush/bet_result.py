"""Bet result dataclass."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class BetResult:
    """Result of a bet placement attempt."""

    match_key: str
    event_id: str
    bet_type: str  # e.g. "П1", "П2", "X", "1X", "ТБ (2.50)"
    kf_nb: float  # NB-Bet coefficient
    kf_kush: float  # Kush coefficient
    ratio: float  # kf_kush * (1 + roi) / kf_nb
    threshold: float  # 1.10 or 1.05
    ratio_passes: bool
    placed: bool  # True if bet was actually placed (not dry-run)
    dry_run: bool
    success: bool  # True if placement succeeded (or dry-run passed)
    error: str = ""
    insufficient_funds: bool = False  # Kush rejected: not enough balance
    insufficient_funds: bool = False  # True if Kush rejected due to lack of funds
    timestamp: datetime = field(default_factory=lambda: datetime.now())
    league: str = ""
    team_home: str = ""
    team_away: str = ""

    @property
    def summary(self) -> str:
        mode = "DRY-RUN" if self.dry_run else "REAL"
        status = "OK" if self.success else f"FAIL: {self.error}"
        return (
            f"[{mode}] {self.team_home} vs {self.team_away} | "
            f"{self.bet_type} kf={self.kf_kush:.2f} "
            f"ratio={self.ratio:.3f}/{self.threshold:.2f} | {status}"
        )
