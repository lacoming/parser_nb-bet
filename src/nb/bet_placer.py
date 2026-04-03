"""NB-Bet tip placement.

Places tips (predictions) on nb-bet.com via POST /v1/soccer/events/tips/{slug}/1.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from src.config.schema import NbConfig
from src.nb.models import Match
from src.nb.session import NbSession

log = logging.getLogger("parser_nb_bet.nb.bet_placer")

# Decision engine bet type → NB odd_type
_BET_TYPE_TO_ODD_TYPE: dict[str, int] = {
    "1": 1,       # WIN_HOME
    "П1": 1,
    "2": 2,       # WIN_AWAY
    "П2": 2,
    "X": 3,       # DRAW
    "1X": 4,      # HOME_OR_X
}


@dataclass
class NbBetResult:
    """Result of an NB-Bet tip placement attempt."""

    match_key: str = ""
    bet_type: str = ""
    odd_type: int = 0
    stake: int = 0
    success: bool = False
    dry_run: bool = False
    error: str = ""
    insufficient_funds: bool = False  # NB rejected: not enough balance
    already_placed: bool = False  # NB rejected: tip already exists for this match
    tip_id: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def summary(self) -> str:
        mode = "DRY-RUN" if self.dry_run else "REAL"
        status = "OK" if self.success else f"FAIL: {self.error}"
        return f"[NB {mode}] {self.bet_type} odd_type={self.odd_type} | {status}"


_INSUFFICIENT_FUNDS_MARKERS = [
    "недостаточно",
    "не хватает",
    "нет средств",
    "insufficient",
    "not enough",
    "balance",
    "баланс",
]

_ALREADY_PLACED_MARKERS = [
    "уже сделали",
    "уже делали",
    "уже существует",
    "already",
    "duplicate",
    "вы уже",
    "прогноз уже",
    "ранее",
]


def _is_insufficient_funds_nb(text: str) -> bool:
    """Check if NB API error indicates insufficient funds."""
    lower = text.lower()
    return any(marker in lower for marker in _INSUFFICIENT_FUNDS_MARKERS)


def _is_already_placed(text: str) -> bool:
    """Check if NB API error indicates tip was already placed."""
    lower = text.lower()
    return any(marker in lower for marker in _ALREADY_PLACED_MARKERS)


class NbBetPlacer:
    """Places tips on NB-Bet."""

    def __init__(self, session: NbSession, config: NbConfig):
        self._session = session
        self._config = config

    def check_existing_tip(self, match: Match) -> bool:
        """Check if a tip already exists for this match on NB-Bet.

        Fetches the tips page for the match slug and looks for an existing
        tip by the current user. Returns True if tip already exists.
        """
        if not match.nb_slug:
            return False

        path = f"/soccer/events/tips/{match.nb_slug}/1"
        try:
            resp = self._session.get_json(path)
            body = resp.json()
        except Exception as exc:
            log.debug("check_existing_tip failed for %s: %s", match.nb_slug, exc)
            return False

        return _response_has_user_tip(body)

    def place_tip(
        self,
        match: Match,
        bet_type: str,
        dry_run: bool = True,
    ) -> NbBetResult:
        """Place a tip on NB-Bet for the given match.

        Args:
            match: The NB-Bet match (must have nb_slug).
            bet_type: Decision engine bet type ("1", "2", "X", "1X").
            dry_run: If True, only log without actually placing.

        Returns:
            NbBetResult with outcome details.
        """
        odd_type = _BET_TYPE_TO_ODD_TYPE.get(bet_type)
        if odd_type is None:
            return NbBetResult(
                match_key=match.match_key,
                bet_type=bet_type,
                error=f"Unknown bet_type: {bet_type}",
            )

        if not match.nb_slug:
            return NbBetResult(
                match_key=match.match_key,
                bet_type=bet_type,
                odd_type=odd_type,
                error="Match has no nb_slug",
            )

        stake = self._config.default_stake

        # Pre-check: does a tip already exist for this match?
        if not dry_run and self.check_existing_tip(match):
            log.info(
                "NB tip SKIP (already exists): %s %s on %s",
                bet_type, odd_type, match.nb_slug,
            )
            return NbBetResult(
                match_key=match.match_key,
                bet_type=bet_type,
                odd_type=odd_type,
                stake=0,
                success=True,  # treat as success — tip exists, no action needed
                already_placed=True,
            )

        if dry_run:
            log.info(
                "NB DRY-RUN: %s odd_type=%d stake=%d on %s (%s vs %s)",
                bet_type, odd_type, stake, match.nb_slug,
                match.team_home, match.team_away,
            )
            return NbBetResult(
                match_key=match.match_key,
                bet_type=bet_type,
                odd_type=odd_type,
                stake=stake,
                success=True,
                dry_run=True,
            )

        # Real placement
        path = f"/soccer/events/tips/{match.nb_slug}/1"
        payload = {
            "odd_type": odd_type,
            "description": "",
            "stake": stake,
        }

        try:
            resp = self._session.post_json(path, payload)
        except Exception as exc:
            log.warning("NB tip request failed for %s: %s", match.match_key, exc)
            return NbBetResult(
                match_key=match.match_key,
                bet_type=bet_type,
                odd_type=odd_type,
                stake=stake,
                error=f"Request failed: {exc}",
            )

        # Parse response
        try:
            body = resp.json()
        except ValueError:
            return NbBetResult(
                match_key=match.match_key,
                bet_type=bet_type,
                odd_type=odd_type,
                stake=stake,
                error="Response not JSON",
            )

        # Check for error/insufficient funds/duplicate in response body
        error_msg = _extract_nb_error(body)
        if error_msg:
            no_funds = _is_insufficient_funds_nb(error_msg)
            dup = _is_already_placed(error_msg)
            if dup:
                log.info("NB tip already placed (POST): %s — %s", match.match_key, error_msg)
                return NbBetResult(
                    match_key=match.match_key,
                    bet_type=bet_type,
                    odd_type=odd_type,
                    stake=stake,
                    success=True,  # treat as success — tip exists
                    already_placed=True,
                )
            if no_funds:
                log.warning("Insufficient funds on NB: %s", error_msg)
            else:
                log.warning("NB tip error: %s", error_msg)
            return NbBetResult(
                match_key=match.match_key,
                bet_type=bet_type,
                odd_type=odd_type,
                stake=stake,
                error=error_msg,
                insufficient_funds=no_funds,
            )

        tip_id = _extract_tip_id(body)

        if tip_id is not None:
            log.info(
                "NB tip placed: %s %s odd_type=%d tip_id=%d",
                match.match_key, bet_type, odd_type, tip_id,
            )
            return NbBetResult(
                match_key=match.match_key,
                bet_type=bet_type,
                odd_type=odd_type,
                stake=stake,
                success=True,
                dry_run=False,
                tip_id=tip_id,
            )

        # If we got HTTP 200 but can't extract tip_id, still treat as success
        # (the API responded, tip was likely created)
        log.info(
            "NB tip placed (no tip_id extracted): %s %s odd_type=%d",
            match.match_key, bet_type, odd_type,
        )
        return NbBetResult(
            match_key=match.match_key,
            bet_type=bet_type,
            odd_type=odd_type,
            stake=stake,
            success=True,
            dry_run=False,
        )


def _extract_nb_error(body: dict) -> Optional[str]:
    """Extract error message from NB-Bet API response, if any.

    Known patterns:
      {"error": "..."} or {"data": {"error": "..."}} or {"message": "..."}
      {"data": {"status": "error", "message": "..."}}
    Returns None if no error detected.
    """
    if not isinstance(body, dict):
        return None
    # Top-level error
    for key in ("error", "message", "error_message"):
        val = body.get(key)
        if isinstance(val, str) and val:
            return val
    # Nested in data
    data = body.get("data")
    if isinstance(data, dict):
        status = data.get("status", "")
        if isinstance(status, str) and status.lower() in ("error", "fail", "failed"):
            msg = data.get("message") or data.get("error") or status
            return str(msg)
        for key in ("error", "message", "error_message"):
            val = data.get(key)
            if isinstance(val, str) and val:
                return val
    return None


def _extract_tip_id(body: dict) -> Optional[int]:
    """Try to extract tip_id from NB-Bet API response.

    Response format: {"data": {"1": [{"1": tip_id, "13": true, ...}, ...]}}
    The first element with "13" == true is our tip.
    """
    try:
        data = body.get("data", {})
        tips_list = data.get("1", [])
        if isinstance(tips_list, list) and tips_list:
            first = tips_list[0]
            if isinstance(first, dict):
                tid = first.get("1")
                if tid is not None:
                    return int(tid)
    except (TypeError, ValueError, KeyError):
        pass
    return None


def _response_has_user_tip(body: dict) -> bool:
    """Check if NB-Bet tips response already contains a tip by the current user.

    The tips page response format: {"data": {"1": [{"1": tip_id, "13": true, ...}, ...]}}
    Field "13" == true indicates the tip belongs to the logged-in user.

    Also checks for error messages that indicate an existing tip.
    """
    if not isinstance(body, dict):
        return False

    # Check if error message indicates existing tip
    error_msg = _extract_nb_error(body)
    if error_msg and _is_already_placed(error_msg):
        return True

    # Check tips list for user's own tip (field "13" = is_mine)
    try:
        data = body.get("data", {})
        if not isinstance(data, dict):
            return False
        tips_list = data.get("1", [])
        if not isinstance(tips_list, list):
            return False
        for tip in tips_list:
            if isinstance(tip, dict) and tip.get("13") is True:
                log.debug(
                    "Found existing user tip: id=%s",
                    tip.get("1", "?"),
                )
                return True
    except (TypeError, KeyError):
        pass

    return False
