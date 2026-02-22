"""Tests for kush.bet_placer and kush.bet_result."""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, PropertyMock

from src.config.schema import ThresholdsConfig, KushConfig
from src.kush.bet_placer import BetPlacer, _extract_error
from src.kush.bet_result import BetResult
from src.kush.client import KushClient, OddsEntry
from src.kush.session import KushSession
from src.nb.models import Match


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_match(**overrides) -> Match:
    defaults = dict(
        match_key="EPL|Arsenal|Chelsea|20260221",
        league="EPL",
        team_home="Arsenal",
        team_away="Chelsea",
        start_time_utc=datetime(2026, 2, 21, 15, 0, tzinfo=timezone.utc),
        nb_slug="arsenal-chelsea",
        sport="soccer",
        odds_1_end=2.10,
        odds_x_end=3.20,
        odds_2_end=3.50,
    )
    defaults.update(overrides)
    return Match(**defaults)


def _make_odds_entry(**overrides) -> OddsEntry:
    defaults = dict(bet_type="П1", coefficient=2.30, cfid="1234567", eid="99999")
    defaults.update(overrides)
    return OddsEntry(**defaults)


def _make_placer(
    thresholds: ThresholdsConfig = None,
    kush_config: KushConfig = None,
) -> tuple[BetPlacer, MagicMock, MagicMock]:
    session = MagicMock(spec=KushSession)
    session._base_url = "https://kushvsporte.ru"
    session.csrf_token = "test_csrf"
    session.logged_in = False
    client = MagicMock(spec=KushClient)

    if thresholds is None:
        thresholds = ThresholdsConfig(
            roi=0.05,
            default_ratio=1.10,
            big_league_ratio=1.05,
            big_leagues=["EPL", "La Liga"],
        )
    if kush_config is None:
        kush_config = KushConfig(
            dry_run=True,
            default_stake=100,
            login="test",
            password="test",
        )

    placer = BetPlacer(session, client, thresholds, kush_config)
    return placer, session, client


# ---------------------------------------------------------------------------
# BetResult tests
# ---------------------------------------------------------------------------

class TestBetResult:
    def test_summary_dry_run_ok(self):
        r = BetResult(
            match_key="k", event_id="1", bet_type="П1",
            kf_nb=2.0, kf_kush=2.5, ratio=1.15, threshold=1.10,
            ratio_passes=True, placed=False, dry_run=True, success=True,
            team_home="A", team_away="B", league="L",
        )
        assert "DRY-RUN" in r.summary
        assert "OK" in r.summary

    def test_summary_real_fail(self):
        r = BetResult(
            match_key="k", event_id="1", bet_type="П1",
            kf_nb=2.0, kf_kush=2.5, ratio=1.15, threshold=1.10,
            ratio_passes=True, placed=False, dry_run=False, success=False,
            error="Login failed", team_home="A", team_away="B", league="L",
        )
        assert "REAL" in r.summary
        assert "FAIL" in r.summary
        assert "Login failed" in r.summary


# ---------------------------------------------------------------------------
# compute_ratio tests
# ---------------------------------------------------------------------------

class TestComputeRatio:
    def test_normal(self):
        placer, _, _ = _make_placer()
        # kf_kush=2.30, kf_nb=2.10, roi=0.05 (global fallback)
        # ratio = 2.30 * 1.05 / 2.10 = 1.15
        ratio = placer.compute_ratio(2.30, 2.10)
        assert abs(ratio - 1.15) < 0.01

    def test_zero_nb(self):
        placer, _, _ = _make_placer()
        assert placer.compute_ratio(2.30, 0.0) == 0.0

    def test_equal_odds(self):
        placer, _, _ = _make_placer()
        # kf_kush=2.00, kf_nb=2.00, roi=0.05 → 2.00*1.05/2.00 = 1.05
        ratio = placer.compute_ratio(2.00, 2.00)
        assert abs(ratio - 1.05) < 0.001

    def test_high_kush_odds(self):
        placer, _, _ = _make_placer()
        ratio = placer.compute_ratio(5.00, 2.00)
        # 5.00 * 1.05 / 2.00 = 2.625
        assert abs(ratio - 2.625) < 0.001

    def test_per_league_roi(self):
        placer, _, _ = _make_placer()
        # Per-league ROI = 0.15 overrides global 0.05
        # ratio = 2.30 * 1.15 / 2.10 = 1.2595
        ratio = placer.compute_ratio(2.30, 2.10, roi=0.15)
        assert abs(ratio - (2.30 * 1.15 / 2.10)) < 0.001

    def test_roi_zero_falls_back_to_global(self):
        placer, _, _ = _make_placer()
        # roi=0 should fall back to global roi=0.05
        ratio_fallback = placer.compute_ratio(2.30, 2.10, roi=0.0)
        ratio_default = placer.compute_ratio(2.30, 2.10)
        assert abs(ratio_fallback - ratio_default) < 0.001

    def test_roi_none_falls_back_to_global(self):
        placer, _, _ = _make_placer()
        ratio_none = placer.compute_ratio(2.30, 2.10, roi=None)
        ratio_default = placer.compute_ratio(2.30, 2.10)
        assert abs(ratio_none - ratio_default) < 0.001


# ---------------------------------------------------------------------------
# get_threshold tests
# ---------------------------------------------------------------------------

class TestGetThreshold:
    def test_big_league(self):
        placer, _, _ = _make_placer()
        assert placer.get_threshold("EPL") == 1.05

    def test_big_league_case_insensitive(self):
        placer, _, _ = _make_placer()
        assert placer.get_threshold("epl something") == 1.05

    def test_default_league(self):
        placer, _, _ = _make_placer()
        assert placer.get_threshold("Bundesliga") == 1.10

    def test_la_liga(self):
        placer, _, _ = _make_placer()
        assert placer.get_threshold("La Liga") == 1.05


# ---------------------------------------------------------------------------
# check_ratio tests
# ---------------------------------------------------------------------------

class TestCheckRatio:
    def test_passes(self):
        placer, _, _ = _make_placer()
        ratio, threshold, passes = placer.check_ratio(2.50, 2.10, "Bundesliga")
        assert passes is True
        assert threshold == 1.10
        assert ratio > 1.10

    def test_fails(self):
        placer, _, _ = _make_placer()
        ratio, threshold, passes = placer.check_ratio(2.00, 2.10, "Bundesliga")
        # 2.00 * 1.05 / 2.10 = 1.0 → fails
        assert passes is False

    def test_big_league_lower_threshold(self):
        placer, _, _ = _make_placer()
        # kf_kush=2.10, kf_nb=2.00 → ratio = 2.10*1.05/2.00 = 1.1025
        # EPL threshold = 1.05 → passes
        ratio, threshold, passes = placer.check_ratio(2.10, 2.00, "EPL")
        assert passes is True
        assert threshold == 1.05

    def test_exactly_at_threshold_fails(self):
        """Ratio == threshold does NOT pass (must be strictly greater)."""
        placer, _, _ = _make_placer(
            thresholds=ThresholdsConfig(roi=0.0, default_ratio=1.00),
        )
        ratio, threshold, passes = placer.check_ratio(2.00, 2.00, "X")
        assert ratio == 1.00
        assert passes is False


# ---------------------------------------------------------------------------
# place_bet tests — dry-run
# ---------------------------------------------------------------------------

class TestPlaceBetDryRun:
    def test_odds_not_found(self):
        placer, _, client = _make_placer()
        client.find_odds_entry.return_value = None
        match = _make_match()

        result = placer.place_bet(
            match, "99999", "/event/99999-x", "П1", 2.10, dry_run=True,
        )
        assert result.success is False
        assert "not found" in result.error
        assert result.kf_kush == 0.0

    def test_ratio_fails(self):
        placer, _, client = _make_placer()
        # kf_kush=1.90, kf_nb=2.10 → ratio = 1.90*1.05/2.10 = 0.95 < 1.10
        client.find_odds_entry.return_value = _make_odds_entry(coefficient=1.90)
        match = _make_match(league="Bundesliga")

        result = placer.place_bet(
            match, "99999", "/event/99999-x", "П1", 2.10, dry_run=True,
        )
        assert result.success is False
        assert result.ratio_passes is False
        assert result.ratio < 1.10

    def test_dry_run_passes(self):
        placer, _, client = _make_placer()
        # kf_kush=2.50, kf_nb=2.10, league=EPL (threshold=1.05)
        # ratio = 2.50*1.05/2.10 = 1.25 > 1.05 ✓
        client.find_odds_entry.return_value = _make_odds_entry(coefficient=2.50)
        match = _make_match(league="EPL")

        result = placer.place_bet(
            match, "99999", "/event/99999-x", "П1", 2.10, dry_run=True,
        )
        assert result.success is True
        assert result.dry_run is True
        assert result.placed is False
        assert result.ratio_passes is True
        assert result.kf_kush == 2.50

    def test_dry_run_default_league(self):
        placer, _, client = _make_placer()
        # kf_kush=2.50, kf_nb=2.10, league=Bundesliga (threshold=1.10)
        # ratio = 2.50*1.05/2.10 = 1.25 > 1.10 ✓
        client.find_odds_entry.return_value = _make_odds_entry(coefficient=2.50)
        match = _make_match(league="Bundesliga")

        result = placer.place_bet(
            match, "99999", "/event/99999-x", "П1", 2.10, dry_run=True,
        )
        assert result.success is True
        assert result.threshold == 1.10


# ---------------------------------------------------------------------------
# place_bet tests — real bet
# ---------------------------------------------------------------------------

class TestPlaceBetReal:
    def test_login_failure(self):
        placer, session, client = _make_placer(
            kush_config=KushConfig(dry_run=False, login="u", password="p"),
        )
        client.find_odds_entry.return_value = _make_odds_entry(coefficient=2.50)
        session.logged_in = False
        session.login.side_effect = Exception("Auth error")
        match = _make_match(league="EPL")

        result = placer.place_bet(
            match, "99999", "/event/99999-x", "П1", 2.10, dry_run=False,
        )
        assert result.success is False
        assert "Login failed" in result.error

    def test_add_coupon_no_form(self):
        placer, session, client = _make_placer(
            kush_config=KushConfig(dry_run=False, login="u", password="p"),
        )
        client.find_odds_entry.return_value = _make_odds_entry(coefficient=2.50)
        session.logged_in = True

        # Mock GET response with no form
        mock_resp = MagicMock()
        mock_resp.text = "<html><body>no form here</body></html>"
        session.get.return_value = mock_resp

        match = _make_match(league="EPL")
        result = placer.place_bet(
            match, "99999", "/event/99999-x", "П1", 2.10, dry_run=False,
        )
        assert result.success is False
        assert "no form tokens" in result.error

    def test_add_coupon_with_form_tokens(self):
        placer, session, client = _make_placer(
            kush_config=KushConfig(dry_run=False, login="u", password="p", default_stake=400),
        )
        client.find_odds_entry.return_value = _make_odds_entry(coefficient=2.50)
        session.logged_in = True

        # Mock add_coupon response with form
        add_resp = MagicMock()
        add_resp.text = """
        <form action="/coupon/create-coupon">
            <input name="_csrf" value="token123"/>
            <input name="Coupon[event_id]" value="99999"/>
        </form>
        """
        session.get.return_value = add_resp

        # Mock create_coupon response — success
        create_resp = MagicMock()
        create_resp.text = "Прогноз успешно добавлен"
        session.post.return_value = create_resp

        match = _make_match(league="EPL")
        result = placer.place_bet(
            match, "99999", "/event/99999-x", "П1", 2.10, dry_run=False,
        )
        assert result.success is True
        assert result.placed is True
        assert result.dry_run is False

        # Verify create_coupon was called with correct stake
        call_args = session.post.call_args
        assert call_args is not None
        form_data = call_args.kwargs.get("data") or call_args[1].get("data")
        assert form_data["Coupon[bet_amount]"] == "400"

    def test_create_coupon_error(self):
        placer, session, client = _make_placer(
            kush_config=KushConfig(dry_run=False, login="u", password="p"),
        )
        client.find_odds_entry.return_value = _make_odds_entry(coefficient=2.50)
        session.logged_in = True

        add_resp = MagicMock()
        add_resp.text = """
        <form action="/coupon/create-coupon">
            <input name="_csrf" value="t"/>
        </form>
        """
        session.get.return_value = add_resp

        create_resp = MagicMock()
        create_resp.text = '<div class="alert-danger">Недостаточно средств</div>'
        session.post.return_value = create_resp

        match = _make_match(league="EPL")
        result = placer.place_bet(
            match, "99999", "/event/99999-x", "П1", 2.10, dry_run=False,
        )
        assert result.success is False
        assert "Недостаточно средств" in result.error

    def test_create_coupon_exception(self):
        placer, session, client = _make_placer(
            kush_config=KushConfig(dry_run=False, login="u", password="p"),
        )
        client.find_odds_entry.return_value = _make_odds_entry(coefficient=2.50)
        session.logged_in = True

        add_resp = MagicMock()
        add_resp.text = """
        <form action="/coupon/create-coupon">
            <input name="_csrf" value="t"/>
        </form>
        """
        session.get.return_value = add_resp
        session.post.side_effect = Exception("Network error")

        match = _make_match(league="EPL")
        result = placer.place_bet(
            match, "99999", "/event/99999-x", "П1", 2.10, dry_run=False,
        )
        assert result.success is False
        assert "create_coupon failed" in result.error


# ---------------------------------------------------------------------------
# _extract_error tests
# ---------------------------------------------------------------------------

class TestExtractError:
    def test_empty(self):
        assert _extract_error("") == "Empty response"

    def test_alert_danger(self):
        html = '<div class="alert-danger">Ошибка ставки</div>'
        assert "Ошибка ставки" in _extract_error(html)

    def test_help_block(self):
        html = '<div class="help-block">Поле обязательно</div>'
        assert "Поле обязательно" in _extract_error(html)

    def test_unknown(self):
        html = "<html><body>Something</body></html>"
        assert "Unknown error" in _extract_error(html)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_missing_eid_cfid(self):
        placer, session, client = _make_placer(
            kush_config=KushConfig(dry_run=False, login="u", password="p"),
        )
        # OddsEntry with empty eid and cfid
        client.find_odds_entry.return_value = OddsEntry(
            bet_type="П1", coefficient=2.50, cfid="", eid="",
        )
        session.logged_in = True
        match = _make_match(league="EPL")

        result = placer.place_bet(
            match, "99999", "/event/99999-x", "П1", 2.10, dry_run=False,
        )
        # Should extract eid from URL but cfid is empty → fail
        assert result.success is False
        assert "Missing eid or cfid" in result.error

    def test_bet_type_mapping(self):
        """Verify we can handle various Kush bet types."""
        placer, _, client = _make_placer()

        for bt in ["П1", "П2", "X", "1X", "ТБ (2.50)", "ТМ (2.50)", "Обе забьют Да"]:
            client.find_odds_entry.return_value = _make_odds_entry(
                bet_type=bt, coefficient=3.00,
            )
            match = _make_match(league="EPL")
            result = placer.place_bet(
                match, "99999", "/event/99999-x", bt, 2.00, dry_run=True,
            )
            # ratio = 3.00 * 1.05 / 2.00 = 1.575 > 1.05 → passes
            assert result.success is True, f"Failed for bet_type={bt}"
            assert result.bet_type == bt
