"""Decision engine: applies betting rules from the spec (ТЗ).

Rules:
  When kf1 > kf2 (home is underdog):
    - 1X: passes if kf1 ≤ 8, kf1X ≥ 1.5, kf2 ≥ 1.4
    - 1:  passes if kf1 ≤ 8, kf2 ≥ 1.4
    - 2:  passes if kf2 ≥ 1.5
    - X:  same conditions as 1X

  When kf2 > kf1 (away is underdog):
    - 2:  passes if kf2 ≤ 8, kf1 ≥ 1.4
    - 1:  passes if kf1 ≥ 1.5

  When kf1 == kf2: skip (no decision)
"""
from __future__ import annotations

import logging

from src.decision.models import BetDecision
from src.nb.models import Match

log = logging.getLogger("parser_nb_bet.decision.engine")


class DecisionEngine:
    """Evaluate match odds and produce bet decisions."""

    def decide(self, match: Match) -> list[BetDecision]:
        """Return list of applicable bet decisions for this match.

        Uses START (opening) odds for branch selection and threshold checks,
        because current odds can be manipulated by bettors ("прогнуты").
        """
        kf1 = match.odds_1_start
        kf2 = match.odds_2_start
        kfx = match.odds_x_start
        kf1x = match.odds_1x_start

        if kf1 is None or kf2 is None:
            return [BetDecision(bet_type="skip", passes=False, reasons=["missing odds"])]

        if kf1 == kf2:
            return [BetDecision(bet_type="skip", passes=False, reasons=["kf1 == kf2"])]

        decisions: list[BetDecision] = []

        if kf1 > kf2:
            # Home is underdog (higher odds)
            decisions.append(self._decide_1x(kf1, kf2, kfx, kf1x))
            decisions.append(self._decide_1_home_underdog(kf1, kf2))
            decisions.append(self._decide_2_home_underdog(kf2))
            decisions.append(self._decide_x(kf1, kf2, kfx, kf1x))
        else:
            # Away is underdog (kf2 > kf1)
            decisions.append(self._decide_2_away_underdog(kf1, kf2))
            decisions.append(self._decide_1_away_underdog(kf1))

        return decisions

    def get_passing_decisions(self, match: Match) -> list[BetDecision]:
        """Return only decisions that pass."""
        return [d for d in self.decide(match) if d.passes]

    # ── kf1 > kf2 branch ───────────────────────────────────────────────

    @staticmethod
    def _decide_1x(
        kf1: float, kf2: float, kfx: float | None, kf1x: float | None,
    ) -> BetDecision:
        reasons = []
        passes = True

        if kf1 > 8:
            reasons.append(f"kf1={kf1} > 8")
            passes = False
        if kf1x is not None and kf1x < 1.5:
            reasons.append(f"kf1x={kf1x} < 1.5")
            passes = False
        if kf1x is None:
            reasons.append("kf1x is None")
            passes = False
        if kf2 < 1.4:
            reasons.append(f"kf2={kf2} < 1.4")
            passes = False

        if passes:
            reasons.append(f"kf1={kf1}<=8, kf1x={kf1x}>=1.5, kf2={kf2}>=1.4")
        return BetDecision(bet_type="1X", passes=passes, reasons=reasons)

    @staticmethod
    def _decide_1_home_underdog(kf1: float, kf2: float) -> BetDecision:
        reasons = []
        passes = True

        if kf1 > 8:
            reasons.append(f"kf1={kf1} > 8")
            passes = False
        if kf2 < 1.4:
            reasons.append(f"kf2={kf2} < 1.4")
            passes = False

        if passes:
            reasons.append(f"kf1={kf1}<=8, kf2={kf2}>=1.4")
        return BetDecision(bet_type="1", passes=passes, reasons=reasons)

    @staticmethod
    def _decide_2_home_underdog(kf2: float) -> BetDecision:
        reasons = []
        passes = True

        if kf2 < 1.5:
            reasons.append(f"kf2={kf2} < 1.5")
            passes = False

        if passes:
            reasons.append(f"kf2={kf2}>=1.5")
        return BetDecision(bet_type="2", passes=passes, reasons=reasons)

    @staticmethod
    def _decide_x(
        kf1: float, kf2: float, kfx: float | None, kf1x: float | None,
    ) -> BetDecision:
        # Same conditions as 1X per spec
        reasons = []
        passes = True

        if kf1 > 8:
            reasons.append(f"kf1={kf1} > 8")
            passes = False
        if kf1x is not None and kf1x < 1.5:
            reasons.append(f"kf1x={kf1x} < 1.5")
            passes = False
        if kf1x is None:
            reasons.append("kf1x is None")
            passes = False
        if kf2 < 1.4:
            reasons.append(f"kf2={kf2} < 1.4")
            passes = False

        if passes:
            reasons.append(f"kf1={kf1}<=8, kf1x={kf1x}>=1.5, kf2={kf2}>=1.4")
        return BetDecision(bet_type="X", passes=passes, reasons=reasons)

    # ── kf2 > kf1 branch ───────────────────────────────────────────────

    @staticmethod
    def _decide_2_away_underdog(kf1: float, kf2: float) -> BetDecision:
        reasons = []
        passes = True

        if kf2 > 8:
            reasons.append(f"kf2={kf2} > 8")
            passes = False
        if kf1 < 1.4:
            reasons.append(f"kf1={kf1} < 1.4")
            passes = False

        if passes:
            reasons.append(f"kf2={kf2}<=8, kf1={kf1}>=1.4")
        return BetDecision(bet_type="2", passes=passes, reasons=reasons)

    @staticmethod
    def _decide_1_away_underdog(kf1: float) -> BetDecision:
        reasons = []
        passes = True

        if kf1 < 1.5:
            reasons.append(f"kf1={kf1} < 1.5")
            passes = False

        if passes:
            reasons.append(f"kf1={kf1}>=1.5")
        return BetDecision(bet_type="1", passes=passes, reasons=reasons)
