"""Kush bet placer: ratio check + coupon placement + dry-run.

Flow:
1. Find odds entry on Kush matching the bet type
2. Compute ratio: kf_kush * (1 + ROI) / kf_nb
3. If ratio > threshold → place bet (or dry-run log)
4. Real bet: login → add_coupon (GET) → create_coupon (POST)
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from bs4 import BeautifulSoup

from src.config.schema import ThresholdsConfig, KushConfig
from src.kush.bet_result import BetResult
from src.kush.client import KushClient, OddsEntry
from src.kush.session import KushSession
from src.nb.models import Match

log = logging.getLogger("parser_nb_bet.kush.bet_placer")


class BetPlacer:
    """Places bets on kushvsporte.ru or performs dry-run."""

    def __init__(
        self,
        session: KushSession,
        client: KushClient,
        thresholds: ThresholdsConfig,
        kush_config: KushConfig,
    ):
        self._session = session
        self._client = client
        self._thresholds = thresholds
        self._kush_config = kush_config

    def compute_ratio(self, kf_kush: float, kf_nb: float, roi: Optional[float] = None) -> float:
        """Compute ratio: kf_kush * (1 + ROI) / kf_nb.

        Args:
            roi: Per-league ROI. Falls back to global config if None or 0.
        """
        if kf_nb <= 0:
            return 0.0
        effective_roi = roi if roi else self._thresholds.roi
        return kf_kush * (1 + effective_roi) / kf_nb

    def get_threshold(self, league: str) -> float:
        """Return ratio threshold for a league (big or default)."""
        for big in self._thresholds.big_leagues:
            if big.lower() in league.lower():
                return self._thresholds.big_league_ratio
        return self._thresholds.default_ratio

    def check_ratio(
        self, kf_kush: float, kf_nb: float, league: str,
        roi: Optional[float] = None,
    ) -> tuple[float, float, bool]:
        """Check if ratio passes threshold.

        Args:
            roi: Per-league ROI override. Falls back to global config if None/0.

        Returns:
            (ratio, threshold, passes)
        """
        ratio = self.compute_ratio(kf_kush, kf_nb, roi=roi)
        threshold = self.get_threshold(league)
        return ratio, threshold, ratio > threshold

    def place_bet(
        self,
        match: Match,
        kush_event_id: str,
        kush_event_url: str,
        bet_type_kush: str,
        kf_nb: float,
        dry_run: bool = True,
        roi: Optional[float] = None,
    ) -> BetResult:
        """Attempt to place a bet on Kush.

        Args:
            match: The NB-Bet match.
            kush_event_id: Kush event ID.
            kush_event_url: Kush event URL (e.g. /event/12345-xxx).
            bet_type_kush: Bet type string on Kush (e.g. "П1", "ТБ (2.50)").
            kf_nb: The NB-Bet coefficient for ratio calculation.
            dry_run: If True, do not actually place the bet.
            roi: Per-league ROI override. Falls back to global config if None/0.

        Returns:
            BetResult with outcome details.
        """
        # Step 1: Find matching odds entry
        odds_entry = self._client.find_odds_entry(
            event_id=kush_event_id,
            bet_type=bet_type_kush,
        )

        if odds_entry is None:
            return BetResult(
                match_key=match.match_key,
                event_id=kush_event_id,
                bet_type=bet_type_kush,
                kf_nb=kf_nb,
                kf_kush=0.0,
                ratio=0.0,
                threshold=self.get_threshold(match.league),
                ratio_passes=False,
                placed=False,
                dry_run=dry_run,
                success=False,
                error=f"Odds entry not found for {bet_type_kush}",
                league=match.league,
                team_home=match.team_home,
                team_away=match.team_away,
            )

        kf_kush = odds_entry.coefficient

        # Step 2: Check ratio
        ratio, threshold, passes = self.check_ratio(kf_kush, kf_nb, match.league, roi=roi)

        if not passes:
            log.info(
                "Ratio check failed: %.3f <= %.2f for %s (%s vs %s)",
                ratio, threshold, bet_type_kush,
                match.team_home, match.team_away,
            )
            return BetResult(
                match_key=match.match_key,
                event_id=kush_event_id,
                bet_type=bet_type_kush,
                kf_nb=kf_nb,
                kf_kush=kf_kush,
                ratio=ratio,
                threshold=threshold,
                ratio_passes=False,
                placed=False,
                dry_run=dry_run,
                success=False,
                error=f"Ratio {ratio:.3f} <= threshold {threshold:.2f}",
                league=match.league,
                team_home=match.team_home,
                team_away=match.team_away,
            )

        # Step 3: Dry-run or real bet
        if dry_run:
            log.info(
                "DRY-RUN: Would place %s on %s vs %s (kf=%.2f, ratio=%.3f)",
                bet_type_kush, match.team_home, match.team_away,
                kf_kush, ratio,
            )
            return BetResult(
                match_key=match.match_key,
                event_id=kush_event_id,
                bet_type=bet_type_kush,
                kf_nb=kf_nb,
                kf_kush=kf_kush,
                ratio=ratio,
                threshold=threshold,
                ratio_passes=True,
                placed=False,
                dry_run=True,
                success=True,
                league=match.league,
                team_home=match.team_home,
                team_away=match.team_away,
            )

        # Step 4: Real bet placement
        return self._place_real_bet(
            match=match,
            odds_entry=odds_entry,
            kush_event_url=kush_event_url,
            kf_nb=kf_nb,
            ratio=ratio,
            threshold=threshold,
        )

    def _place_real_bet(
        self,
        match: Match,
        odds_entry: OddsEntry,
        kush_event_url: str,
        kf_nb: float,
        ratio: float,
        threshold: float,
    ) -> BetResult:
        """Execute real bet placement via add_coupon + create_coupon.

        Refreshes CSRF before each attempt. On failure, re-logins and retries once.
        """
        eid = odds_entry.eid or kush_event_url.split("/event/")[1].split("-")[0] if "/event/" in kush_event_url else odds_entry.eid
        cfid = odds_entry.cfid

        if not eid or not cfid:
            return self._make_result(
                match, odds_entry, kf_nb, ratio, threshold,
                placed=False, success=False,
                error="Missing eid or cfid from odds entry",
            )

        # Ensure logged in
        if not self._session.logged_in:
            try:
                self._session.login(
                    self._kush_config.login,
                    self._kush_config.password,
                )
            except Exception as exc:
                return self._make_result(
                    match, odds_entry, kf_nb, ratio, threshold,
                    placed=False, success=False,
                    error=f"Login failed: {exc}",
                )

        for attempt in range(2):
            # Refresh CSRF before every bet attempt
            self._session.refresh_csrf()

            # Step 4a: add_coupon — GET to extract form tokens
            try:
                tokens = self._add_coupon(eid, cfid, kush_event_url)
            except Exception as exc:
                if attempt == 0:
                    log.warning("add_coupon failed (attempt 1), re-login & retry: %s", exc)
                    self._relogin()
                    continue
                return self._make_result(
                    match, odds_entry, kf_nb, ratio, threshold,
                    placed=False, success=False,
                    error=f"add_coupon failed: {exc}",
                )

            if not tokens:
                if attempt == 0:
                    log.warning("add_coupon returned no tokens (attempt 1), re-login & retry")
                    self._relogin()
                    continue
                return self._make_result(
                    match, odds_entry, kf_nb, ratio, threshold,
                    placed=False, success=False,
                    error="add_coupon returned no form tokens",
                )

            # Step 4b: create_coupon — POST to submit the bet
            try:
                success, message = self._create_coupon(
                    tokens, kush_event_url,
                )
            except Exception as exc:
                if attempt == 0:
                    log.warning("create_coupon failed (attempt 1), re-login & retry: %s", exc)
                    self._relogin()
                    continue
                return self._make_result(
                    match, odds_entry, kf_nb, ratio, threshold,
                    placed=False, success=False,
                    error=f"create_coupon failed: {exc}",
                )

            if success:
                return self._make_result(
                    match, odds_entry, kf_nb, ratio, threshold,
                    placed=True, success=True, error="",
                )

            # Bet failed — retry once with re-login
            if attempt == 0:
                log.warning("Bet failed (attempt 1): %s — re-login & retry", message)
                self._relogin()
                continue

            return self._make_result(
                match, odds_entry, kf_nb, ratio, threshold,
                placed=False, success=False,
                error=message,
            )

        # Should not reach here, but safety fallback
        return self._make_result(
            match, odds_entry, kf_nb, ratio, threshold,
            placed=False, success=False,
            error="Max retry attempts reached",
        )

    def _relogin(self) -> None:
        """Re-login to Kush, swallowing exceptions."""
        try:
            self._session.login(
                self._kush_config.login,
                self._kush_config.password,
            )
        except Exception:
            log.warning("Re-login failed during retry")

    def _add_coupon(
        self, eid: str, cfid: str, event_url: str,
    ) -> Optional[dict[str, str]]:
        """GET /coupon/add-coupon to extract form tokens.

        Returns:
            Dict of form field name → value, or None on failure.
        """
        base = self._session._base_url
        url = f"{base}/coupon/add-coupon?eid={eid}&cfid={cfid}&_pjax=%23coupon"

        headers = {
            "Accept": "text/html, */*; q=0.01",
            "Referer": f"{base}{event_url}?abtest=9",
            "X-PJAX": "true",
            "X-PJAX-Container": "#coupon",
            "X-Requested-With": "XMLHttpRequest",
        }
        if self._session.csrf_token:
            headers["X-CSRF-Token"] = self._session.csrf_token

        resp = self._session.get(url, headers=headers)
        soup = BeautifulSoup(resp.text, "lxml")

        form = soup.find("form", {"action": "/coupon/create-coupon"})
        if not form:
            log.warning("add_coupon: form not found in response")
            return None

        tokens: dict[str, str] = {}
        for inp in form.find_all("input"):
            name = inp.get("name", "")
            value = inp.get("value", "")
            if name:
                tokens[name] = value

        log.debug("add_coupon: extracted %d form tokens", len(tokens))
        return tokens

    def _create_coupon(
        self, tokens: dict[str, str], event_url: str,
    ) -> tuple[bool, str]:
        """POST /coupon/create-coupon to submit the bet.

        Returns:
            (success, message)
        """
        base = self._session._base_url

        form_data = dict(tokens)
        form_data["Coupon[bet_amount]"] = str(self._kush_config.default_stake)
        form_data["Coupon[comment]"] = ""
        form_data["addReviewButton2"] = ""
        form_data["_pjax"] = "#coupon"

        headers = {
            "Accept": "text/html, */*; q=0.01",
            "Referer": f"{base}{event_url}?abtest=9",
            "X-PJAX": "true",
            "X-PJAX-Container": "#coupon",
            "X-Requested-With": "XMLHttpRequest",
        }
        if self._session.csrf_token:
            headers["X-CSRF-Token"] = self._session.csrf_token

        resp = self._session.post(
            f"{base}/coupon/create-coupon",
            data=form_data,
        )

        text = resp.text if resp else ""

        if "Прогноз успешно добавлен" in text:
            log.info("Bet placed successfully")
            return True, "Прогноз успешно добавлен"

        # Try to extract error message
        error_msg = _extract_error(text)
        log.warning("Bet placement failed: %s", error_msg)
        return False, error_msg

    def _make_result(
        self,
        match: Match,
        odds_entry: OddsEntry,
        kf_nb: float,
        ratio: float,
        threshold: float,
        placed: bool,
        success: bool,
        error: str,
    ) -> BetResult:
        return BetResult(
            match_key=match.match_key,
            event_id=odds_entry.eid,
            bet_type=odds_entry.bet_type,
            kf_nb=kf_nb,
            kf_kush=odds_entry.coefficient,
            ratio=ratio,
            threshold=threshold,
            ratio_passes=ratio > threshold,
            placed=placed,
            dry_run=self._kush_config.dry_run,
            success=success,
            error=error,
            league=match.league,
            team_home=match.team_home,
            team_away=match.team_away,
        )


def _extract_error(html: str) -> str:
    """Try to extract a human-readable error from Kush response HTML."""
    if not html:
        return "Empty response"
    soup = BeautifulSoup(html, "lxml")
    # Look for error divs/spans in order of specificity
    selectors = [
        ("div", "alert-danger"),
        ("div", "alert-warning"),
        ("div", "help-block"),
        ("p", "help-block-error"),
        ("span", "help-block"),
        ("div", "error-summary"),
    ]
    for tag, cls in selectors:
        el = soup.find(tag, class_=cls)
        if el:
            text = el.get_text(strip=True)
            if text:
                return text
    # Try finding any element with "error" or "ошибк" text
    for el in soup.find_all(["div", "p", "span", "li"]):
        text = el.get_text(strip=True)
        if text and ("ошибк" in text.lower() or "error" in text.lower() or "не удалось" in text.lower()):
            return text[:300]
    # Log HTML snippet at WARNING for diagnostics
    snippet = html[:1000].replace("\n", " ").replace("\r", "")
    log.warning("_extract_error: no error selector matched. HTML snippet: %s", snippet)
    return f"Unknown error (no success message). Response length: {len(html)} chars"
