"""Tests for NbBetPlacer and NbBetResult."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.config.schema import NbConfig
from src.nb.bet_placer import NbBetPlacer, NbBetResult, _extract_tip_id
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

    def test_real_placement_success_with_tip_id(self):
        session = MagicMock(spec=NbSession)
        config = NbConfig(default_stake=1000)
        placer = NbBetPlacer(session, config)

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "data": {"1": [{"1": 42, "13": True}]}
        }
        session.post_json.return_value = mock_resp

        result = placer.place_tip(_make_match(), "1", dry_run=False)

        assert result.success is True
        assert result.dry_run is False
        assert result.tip_id == 42
        session.post_json.assert_called_once()
        call_args = session.post_json.call_args
        assert "/soccer/events/tips/arsenal-chelsea-123/1" in call_args[0][0]
        assert call_args[0][1]["odd_type"] == 1
        assert call_args[0][1]["stake"] == 1000

    def test_real_placement_success_no_tip_id(self):
        session = MagicMock(spec=NbSession)
        config = NbConfig()
        placer = NbBetPlacer(session, config)

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

        session.post_json.side_effect = Exception("Network error")

        result = placer.place_tip(_make_match(), "1", dry_run=False)
        assert result.success is False
        assert "Request failed" in result.error

    def test_real_placement_non_json_response(self):
        session = MagicMock(spec=NbSession)
        config = NbConfig()
        placer = NbBetPlacer(session, config)

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
