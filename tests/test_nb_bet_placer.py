"""Tests for NbBetPlacer and NbBetResult."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.config.schema import NbConfig
from src.nb.bet_placer import (
    NbBetPlacer, NbBetResult, _extract_tip_id,
    _is_already_placed, _response_has_user_tip,
)
from src.nb.models import Match
from src.nb.session import NbSession


def _make_match(slug: str = "arsenal-chelsea-123") -> Match:
    dt = datetime(2026, 2, 22, 15, 0, tzinfo=timezone.utc)
    return Match(
        match_key=Match.make_key("Premier League", "Arsenal", "Chelsea", dt),
        league="Premier League",
        team_home="Arsenal",
        team_away="Chelsea",
        start_time_utc=dt,
        nb_slug=slug,
        sport="soccer",
        odds_1_start=2.00,
        odds_x_start=3.10,
        odds_2_start=3.40,
        odds_1_end=2.10,
        odds_x_end=3.20,
        odds_2_end=3.50,
    )


class TestOddTypeMapping:
    """Tests for bet_type → odd_type mapping."""

    def test_bet_type_1(self):
        session = MagicMock(spec=NbSession)
        config = NbConfig(default_stake=500)
        placer = NbBetPlacer(session, config)
        result = placer.place_tip(_make_match(), "1", dry_run=True)
        assert result.success is True
        assert result.odd_type == 1

    def test_bet_type_2(self):
        session = MagicMock(spec=NbSession)
        config = NbConfig()
        placer = NbBetPlacer(session, config)
        result = placer.place_tip(_make_match(), "2", dry_run=True)
        assert result.odd_type == 2

    def test_bet_type_X(self):
        session = MagicMock(spec=NbSession)
        config = NbConfig()
        placer = NbBetPlacer(session, config)
        result = placer.place_tip(_make_match(), "X", dry_run=True)
        assert result.odd_type == 3

    def test_bet_type_1X(self):
        session = MagicMock(spec=NbSession)
        config = NbConfig()
        placer = NbBetPlacer(session, config)
        result = placer.place_tip(_make_match(), "1X", dry_run=True)
        assert result.odd_type == 4

    def test_bet_type_P1(self):
        session = MagicMock(spec=NbSession)
        config = NbConfig()
        placer = NbBetPlacer(session, config)
        result = placer.place_tip(_make_match(), "П1", dry_run=True)
        assert result.odd_type == 1

    def test_unknown_bet_type(self):
        session = MagicMock(spec=NbSession)
        config = NbConfig()
        placer = NbBetPlacer(session, config)
        result = placer.place_tip(_make_match(), "ТБ(2.5)", dry_run=True)
        assert result.success is False
        assert "Unknown bet_type" in result.error


class TestDryRun:
    """Tests for dry-run mode."""

    def test_dry_run_returns_success(self):
        session = MagicMock(spec=NbSession)
        config = NbConfig(default_stake=1000)
        placer = NbBetPlacer(session, config)
        result = placer.place_tip(_make_match(), "1", dry_run=True)

        assert result.success is True
        assert result.dry_run is True
        assert result.stake == 1000
        assert result.odd_type == 1
        # Session should NOT be called in dry-run
        session.post_json.assert_not_called()

    def test_dry_run_sets_match_key(self):
        session = MagicMock(spec=NbSession)
        config = NbConfig()
        match = _make_match()
        placer = NbBetPlacer(session, config)
        result = placer.place_tip(match, "2", dry_run=True)

        assert result.match_key == match.match_key
        assert result.bet_type == "2"


class TestRealPlacement:
    """Tests for real tip placement."""

    def _mock_no_existing_tip(self, session: MagicMock) -> None:
        """Set up get_json to return empty tips (no existing tip)."""
        get_resp = MagicMock()
        get_resp.json.return_value = {"data": {"1": []}}
        session.get_json.return_value = get_resp

    def test_real_placement_success_with_tip_id(self):
        session = MagicMock(spec=NbSession)
        config = NbConfig(default_stake=1000)
        placer = NbBetPlacer(session, config)
        self._mock_no_existing_tip(session)

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": {"1": [{"1": 42, "13": True}]}
        }
        session.post_json.return_value = mock_resp

        result = placer.place_tip(_make_match(), "1", dry_run=False)

        assert result.success is True
        assert result.dry_run is False
        assert result.tip_id == 42
        assert result.already_placed is False
        session.post_json.assert_called_once()
        call_args = session.post_json.call_args
        assert "/soccer/events/tips/arsenal-chelsea-123/1" in call_args[0][0]
        assert call_args[0][1]["odd_type"] == 1
        assert call_args[0][1]["stake"] == 1000

    def test_real_placement_success_no_tip_id(self):
        session = MagicMock(spec=NbSession)
        config = NbConfig()
        placer = NbBetPlacer(session, config)
        self._mock_no_existing_tip(session)

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": {}}
        session.post_json.return_value = mock_resp

        result = placer.place_tip(_make_match(), "2", dry_run=False)
        assert result.success is True
        assert result.tip_id is None

    def test_real_placement_request_failure(self):
        session = MagicMock(spec=NbSession)
        config = NbConfig()
        placer = NbBetPlacer(session, config)
        self._mock_no_existing_tip(session)

        session.post_json.side_effect = Exception("Network error")

        result = placer.place_tip(_make_match(), "1", dry_run=False)
        assert result.success is False
        assert "Request failed" in result.error

    def test_real_placement_non_json_response(self):
        session = MagicMock(spec=NbSession)
        config = NbConfig()
        placer = NbBetPlacer(session, config)
        self._mock_no_existing_tip(session)

        mock_resp = MagicMock()
        mock_resp.json.side_effect = ValueError("not JSON")
        session.post_json.return_value = mock_resp

        result = placer.place_tip(_make_match(), "X", dry_run=False)
        assert result.success is False
        assert "not JSON" in result.error


class TestNoSlug:
    """Test handling of matches without nb_slug."""

    def test_no_slug_returns_error(self):
        session = MagicMock(spec=NbSession)
        config = NbConfig()
        placer = NbBetPlacer(session, config)
        match = _make_match(slug="")
        result = placer.place_tip(match, "1", dry_run=False)

        assert result.success is False
        assert "no nb_slug" in result.error


class TestExtractTipId:
    """Tests for _extract_tip_id helper."""

    def test_normal_response(self):
        body = {"data": {"1": [{"1": 999, "13": True}]}}
        assert _extract_tip_id(body) == 999

    def test_empty_tips_list(self):
        body = {"data": {"1": []}}
        assert _extract_tip_id(body) is None

    def test_missing_data(self):
        assert _extract_tip_id({}) is None

    def test_no_tip_key(self):
        body = {"data": {"1": [{"13": True}]}}
        assert _extract_tip_id(body) is None

    def test_string_tip_id(self):
        body = {"data": {"1": [{"1": "42", "13": True}]}}
        assert _extract_tip_id(body) == 42


class TestDuplicateDetection:
    """Tests for NB-Bet tip duplicate detection."""

    def test_is_already_placed_russian(self):
        assert _is_already_placed("Вы уже делали прогноз") is True
        assert _is_already_placed("Прогноз уже существует") is True
        assert _is_already_placed("вы уже сделали ставку") is True

    def test_is_already_placed_english(self):
        assert _is_already_placed("Tip already exists") is True
        assert _is_already_placed("duplicate entry") is True

    def test_is_already_placed_negative(self):
        assert _is_already_placed("Insufficient balance") is False
        assert _is_already_placed("Network error") is False
        assert _is_already_placed("") is False

    def test_response_has_user_tip_field_13(self):
        """Field '13' == True means the tip belongs to current user."""
        body = {"data": {"1": [{"1": 42, "13": True}]}}
        assert _response_has_user_tip(body) is True

    def test_response_has_user_tip_no_own_tip(self):
        """Other users' tips (field '13' not True) should not match."""
        body = {"data": {"1": [{"1": 42, "13": False}]}}
        assert _response_has_user_tip(body) is False

    def test_response_has_user_tip_empty(self):
        body = {"data": {"1": []}}
        assert _response_has_user_tip(body) is False

    def test_response_has_user_tip_no_data(self):
        assert _response_has_user_tip({}) is False
        assert _response_has_user_tip({"data": {}}) is False

    def test_response_has_user_tip_error_message(self):
        """Error message indicating existing tip should be detected."""
        body = {"error": "Вы уже делали прогноз на этот матч"}
        assert _response_has_user_tip(body) is True

    def test_check_existing_tip_found(self):
        """check_existing_tip returns True when user's tip exists."""
        session = MagicMock(spec=NbSession)
        config = NbConfig()
        placer = NbBetPlacer(session, config)

        get_resp = MagicMock()
        get_resp.json.return_value = {"data": {"1": [{"1": 99, "13": True}]}}
        session.get_json.return_value = get_resp

        assert placer.check_existing_tip(_make_match()) is True

    def test_check_existing_tip_not_found(self):
        """check_existing_tip returns False when no user's tip."""
        session = MagicMock(spec=NbSession)
        config = NbConfig()
        placer = NbBetPlacer(session, config)

        get_resp = MagicMock()
        get_resp.json.return_value = {"data": {"1": []}}
        session.get_json.return_value = get_resp

        assert placer.check_existing_tip(_make_match()) is False

    def test_check_existing_tip_network_error(self):
        """Network error should return False (fail-open: proceed to place)."""
        session = MagicMock(spec=NbSession)
        config = NbConfig()
        placer = NbBetPlacer(session, config)

        session.get_json.side_effect = Exception("timeout")

        assert placer.check_existing_tip(_make_match()) is False

    def test_place_tip_skips_when_already_exists(self):
        """place_tip should skip POST when pre-check finds existing tip."""
        session = MagicMock(spec=NbSession)
        config = NbConfig()
        placer = NbBetPlacer(session, config)

        get_resp = MagicMock()
        get_resp.json.return_value = {"data": {"1": [{"1": 77, "13": True}]}}
        session.get_json.return_value = get_resp

        result = placer.place_tip(_make_match(), "1", dry_run=False)

        assert result.success is True
        assert result.already_placed is True
        assert result.stake == 0  # no stake used
        session.post_json.assert_not_called()  # POST never called

    def test_place_tip_handles_duplicate_post_error(self):
        """If pre-check misses but POST returns 'already placed', handle gracefully."""
        session = MagicMock(spec=NbSession)
        config = NbConfig()
        placer = NbBetPlacer(session, config)

        # Pre-check returns empty (miss)
        get_resp = MagicMock()
        get_resp.json.return_value = {"data": {"1": []}}
        session.get_json.return_value = get_resp

        # POST returns "already placed" error
        post_resp = MagicMock()
        post_resp.json.return_value = {"error": "Вы уже делали прогноз"}
        session.post_json.return_value = post_resp

        result = placer.place_tip(_make_match(), "2", dry_run=False)

        assert result.success is True
        assert result.already_placed is True

    def test_dry_run_skips_check(self):
        """Dry-run should NOT call check_existing_tip."""
        session = MagicMock(spec=NbSession)
        config = NbConfig()
        placer = NbBetPlacer(session, config)

        result = placer.place_tip(_make_match(), "1", dry_run=True)

        assert result.success is True
        assert result.dry_run is True
        session.get_json.assert_not_called()
        session.post_json.assert_not_called()


class TestNbBetResult:
    """Tests for NbBetResult dataclass."""

    def test_summary_dry_run(self):
        r = NbBetResult(
            match_key="test", bet_type="1", odd_type=1,
            stake=1000, success=True, dry_run=True,
        )
        assert "DRY-RUN" in r.summary
        assert "OK" in r.summary

    def test_summary_fail(self):
        r = NbBetResult(
            match_key="test", bet_type="X", odd_type=3,
            error="Network error",
        )
        assert "FAIL" in r.summary
        assert "Network error" in r.summary
