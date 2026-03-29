"""Decision engine: applies betting rules from the spec (ТЗ).

Rules (updated per customer 2026-03-18):
  1. Поб1 (bet_type "1"): kf1 < kf2, kf1 >= 1.5, kf2 >= 1.5, score_diff > 0
  2. Поб2 (bet_type "2"): kf2 < kf1, kf1 >= 1.5, kf2 >= 1.5, score_diff < 0
  3. Ничья (bet_type "X"): kf1 > kf2, kf1 <= 8, kf1 >= 1.5, kf2 >= 1.5, score_diff == 0

  When kf1 == kf2: skip (no decision)
  When score_diff is None: score condition is skipped (passes by default)
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
        score_diff = match.score_diff

        if kf1 is None or kf2 is None:
            return [BetDecision(bet_type="skip", passes=False, reasons=["missing odds"])]

        if kf1 == kf2:
            return [BetDecision(bet_type="skip", passes=False, reasons=["kf1 == kf2"])]

        decisions: list[BetDecision] = []

        if kf1 < kf2:
            # Поб1 branch
            decisions.append(self._decide_pob1(kf1, kf2, score_diff))
        else:
            # kf1 > kf2 — Поб2 and Ничья branches
            decisions.append(self._decide_pob2(kf1, kf2, score_diff))
            decisions.append(self._decide_draw(kf1, kf2, score_diff))

        return decisions

    def get_passing_decisions(self, match: Match) -> list[BetDecision]:
        """Return only decisions that pass."""
        return [d for d in self.decide(match) if d.passes]

    # ── Поб1: kf1 < kf2 ──────────────────────────────────────────────

    @staticmethod
    def _decide_pob1(
        kf1: float, kf2: float, score_diff: int | None,
    ) -> BetDecision:
        """Поб1: kf1 < kf2, kf1 >= 1.5, kf2 >= 1.5, score_diff > 0."""
        reasons = []
        passes = True

        if kf1 < 1.5:
            reasons.append(f"kf1={kf1} < 1.5")
            passes = False
        if kf2 < 1.5:
            reasons.append(f"kf2={kf2} < 1.5")
            passes = False
        if score_diff is not None and score_diff <= 0:
            reasons.append(f"score_diff={score_diff} <= 0")
            passes = False

        if passes:
            reasons.append(
                f"kf1={kf1}>=1.5, kf2={kf2}>=1.5, score_diff={score_diff}"
            )
        return BetDecision(bet_type="1", passes=passes, reasons=reasons)

    # ── Поб2: kf2 < kf1 ──────────────────────────────────────────────

    @staticmethod
    def _decide_pob2(
        kf1: float, kf2: float, score_diff: int | None,
    ) -> BetDecision:
        """Поб2: kf2 < kf1, kf1 >= 1.5, kf2 >= 1.5, score_diff < 0."""
        reasons = []
        passes = True

        if kf1 < 1.5:
            reasons.append(f"kf1={kf1} < 1.5")
            passes = False
        if kf2 < 1.5:
            reasons.append(f"kf2={kf2} < 1.5")
            passes = False
        if score_diff is not None and score_diff >= 0:
            reasons.append(f"score_diff={score_diff} >= 0")
            passes = False

        if passes:
            reasons.append(
                f"kf1={kf1}>=1.5, kf2={kf2}>=1.5, score_diff={score_diff}"
            )
        return BetDecision(bet_type="2", passes=passes, reasons=reasons)

    # ── Ничья: kf1 > kf2 ─────────────────────────────────────────────

    @staticmethod
    def _decide_draw(
        kf1: float, kf2: float, score_diff: int | None,
    ) -> BetDecision:
        """Ничья: kf1 > kf2, kf1 <= 8, kf1 >= 1.5, kf2 >= 1.5, score_diff == 0."""
        reasons = []
        passes = True

        if kf1 > 8:
            reasons.append(f"kf1={kf1} > 8")
            passes = False
        if kf1 < 1.5:
            reasons.append(f"kf1={kf1} < 1.5")
            passes = False
        if kf2 < 1.5:
            reasons.append(f"kf2={kf2} < 1.5")
            passes = False
        if score_diff is not None and score_diff != 0:
            reasons.append(f"score_diff={score_diff} != 0")
            passes = False

        if passes:
            reasons.append(
                f"kf1={kf1}<=8, kf1>={1.5}, kf2={kf2}>=1.5, score_diff={score_diff}"
            )
        return BetDecision(bet_type="X", passes=passes, reasons=reasons)
