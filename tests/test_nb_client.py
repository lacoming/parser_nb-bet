"""Tests for NB-Bet client, models, and odds decoder."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.config.schema import NbConfig
from src.nb.client import NbClient, _parse_response, _safe_float, _date_to_timestamp_ms
from src.nb.models import Match
from src.nb.odds_decoder import decode_odds_key, load_odds_keys


# ─── Sample API response fixture ───────────────────────────────────────

SAMPLE_MATCH = {
    "3": "team1-vs-team2",
    "4": "1740000000000",  # timestamp ms
    "5": {"1": 1.85, "3": 3.40, "2": 4.20},  # end odds
    "6": {"1": 1.90, "3": 3.50, "2": 4.00},  # start odds
    "7": "Manchester United",
    "15": "Liverpool",
}

SAMPLE_RESPONSE = {
    "data": {
        "leagues": [
            {
                "1": "England",
                "3": "Premier League",
                "4": [SAMPLE_MATCH],
            }
        ]
    }
}


# ─── Match model tests ─────────────────────────────────────────────────

class TestMatchModel:
    def test_make_key(self):
        dt = datetime(2026, 2, 21, 15, 0, tzinfo=timezone.utc)
        key = Match.make_key("EPL", "Man Utd", "Liverpool", dt)
        assert key == "EPL|Man Utd|Liverpool|20260221"

    def test_odds_1x_end(self):
        # Formula: 1 / (1/1.85 + 1/3.40) = 1 / (0.5405 + 0.2941) = 1 / 0.8346 ≈ 1.198
        m = Match(
            match_key="k", league="L", team_home="A", team_away="B",
            start_time_utc=datetime.now(timezone.utc), nb_slug="s", sport="soccer",
            odds_1_end=1.85, odds_x_end=3.40,
        )
        expected = 1 / (1 / 1.85 + 1 / 3.40)
        assert abs(m.odds_1x_end - expected) < 0.001

    def test_odds_1x_end_none(self):
        m = Match(
            match_key="k", league="L", team_home="A", team_away="B",
            start_time_utc=datetime.now(timezone.utc), nb_slug="s", sport="soccer",
        )
        assert m.odds_1x_end is None

    def test_odds_1x_end_x_lower(self):
        # Formula: 1 / (1/5.00 + 1/3.20) = 1 / (0.20 + 0.3125) = 1 / 0.5125 ≈ 1.951
        m = Match(
            match_key="k", league="L", team_home="A", team_away="B",
            start_time_utc=datetime.now(timezone.utc), nb_slug="s", sport="soccer",
            odds_1_end=5.00, odds_x_end=3.20,
        )
        expected = 1 / (1 / 5.00 + 1 / 3.20)
        assert abs(m.odds_1x_end - expected) < 0.001

    def test_nb_url_events(self):
        m = Match(
            match_key="k", league="L", team_home="A", team_away="B",
            start_time_utc=datetime.now(timezone.utc),
            nb_slug="1561561-genk-dinamo-zagreb-prognoz-na-match", sport="soccer",
        )
        assert m.nb_url == "https://nb-bet.com/Events/1561561-genk-dinamo-zagreb-prognoz-na-match"

    def test_nb_url_live_events(self):
        m = Match(
            match_key="k", league="L", team_home="A", team_away="B",
            start_time_utc=datetime.now(timezone.utc),
            nb_slug="1561564-viktoriya-plzen-panatinaikos-live-prognoz-na-match", sport="soccer",
        )
        assert m.nb_url == "https://nb-bet.com/LiveEvents/1561564-viktoriya-plzen-panatinaikos-live-prognoz-na-match"

    def test_nb_url_empty_slug(self):
        m = Match(
            match_key="k", league="L", team_home="A", team_away="B",
            start_time_utc=datetime.now(timezone.utc),
            nb_slug="", sport="soccer",
        )
        assert m.nb_url == ""


# ─── Parse response tests ──────────────────────────────────────────────

class TestParseResponse:
    def test_parse_valid_response(self):
        matches = _parse_response(SAMPLE_RESPONSE, "soccer")
        assert len(matches) == 1
        m = matches[0]
        assert m.team_home == "Manchester United"
        assert m.team_away == "Liverpool"
        assert m.league == "England. Premier League"
        assert m.sport == "soccer"
        assert m.nb_slug == "team1-vs-team2"
        assert m.odds_1_end == 1.85
        assert m.odds_x_end == 3.40
        assert m.odds_2_end == 4.20
        assert m.odds_1_start == 1.90
        assert m.odds_x_start == 3.50
        assert m.odds_2_start == 4.00

    def test_parse_empty_response(self):
        matches = _parse_response({}, "soccer")
        assert matches == []

    def test_parse_no_leagues(self):
        matches = _parse_response({"data": {}}, "soccer")
        assert matches == []

    def test_parse_skips_match_without_odds(self):
        raw = {
            "data": {
                "leagues": [{
                    "1": "X", "3": "Y", "4": [{
                        "3": "slug", "4": "1740000000000",
                        "7": "Home", "15": "Away",
                        # No '5' end odds
                    }]
                }]
            }
        }
        matches = _parse_response(raw, "soccer")
        assert len(matches) == 0

    def test_parse_skips_match_without_teams(self):
        raw = {
            "data": {
                "leagues": [{
                    "1": "X", "3": "Y", "4": [{
                        "3": "slug", "4": "1740000000000",
                        "5": {"1": 1.5, "2": 2.5, "3": 3.0},
                        # Missing '7' (home) and '15' (away)
                    }]
                }]
            }
        }
        matches = _parse_response(raw, "soccer")
        assert len(matches) == 0

    def test_parse_multiple_leagues(self):
        raw = {
            "data": {
                "leagues": [
                    {
                        "1": "England", "3": "EPL",
                        "4": [SAMPLE_MATCH],
                    },
                    {
                        "1": "Spain", "3": "La Liga",
                        "4": [
                            {
                                "3": "barca-vs-real",
                                "4": "1740100000000",
                                "5": {"1": 2.10, "3": 3.30, "2": 3.50},
                                "6": {"1": 2.00, "3": 3.40, "2": 3.60},
                                "7": "Barcelona",
                                "15": "Real Madrid",
                            }
                        ],
                    },
                ]
            }
        }
        matches = _parse_response(raw, "soccer")
        assert len(matches) == 2
        assert matches[0].league == "England. EPL"
        assert matches[1].league == "Spain. La Liga"
        assert matches[1].team_home == "Barcelona"

    def test_parse_hockey(self):
        matches = _parse_response(SAMPLE_RESPONSE, "hockey")
        assert len(matches) == 1
        assert matches[0].sport == "hockey"


# ─── Utility tests ──────────────────────────────────────────────────────

class TestSafeFloat:
    def test_valid_float(self):
        assert _safe_float(1.85) == 1.85

    def test_valid_string(self):
        assert _safe_float("3.40") == 3.40

    def test_none(self):
        assert _safe_float(None) is None

    def test_empty_string(self):
        assert _safe_float("") is None

    def test_invalid(self):
        assert _safe_float("abc") is None


class TestDateToTimestamp:
    def test_produces_ms_string(self):
        dt = datetime(2026, 2, 21, 12, 0, 0, tzinfo=timezone.utc)
        ts = _date_to_timestamp_ms(dt)
        assert ts.endswith("999")
        # Should be a numeric string (except trailing 999)
        assert ts[:-3].isdigit()


# ─── Odds decoder tests ────────────────────────────────────────────────

class TestOddsDecoder:
    def test_load_keys_file(self):
        keys = load_odds_keys()
        # sl_keys.json should exist in assets/data
        assert len(keys) > 0
        assert 1 in keys
        assert keys[1] == "WIN_HOME"

    def test_decode_win_home(self):
        keys = {1: "WIN_HOME"}
        assert decode_odds_key(1, keys) == "П1"

    def test_decode_win_away(self):
        keys = {2: "WIN_AWAY"}
        assert decode_odds_key(2, keys) == "П2"

    def test_decode_draw(self):
        keys = {3: "DRAW"}
        assert decode_odds_key(3, keys) == "X"

    def test_decode_total_over(self):
        keys = {15: "TB_2_5"}
        result = decode_odds_key(15, keys)
        assert "ТБ" in result
        assert "2.5" in result

    def test_decode_total_under(self):
        keys = {16: "TM_2_5"}
        result = decode_odds_key(16, keys)
        assert "ТМ" in result

    def test_decode_unknown_key(self):
        result = decode_odds_key(99999, {})
        assert "Unknown" in result

    def test_decode_string_key(self):
        result = decode_odds_key("WIN_HOME", {})
        assert result == "П1"

    def test_decode_correct_score(self):
        result = decode_odds_key("CORRECT_SCORE_2_1", {})
        assert "Точный счет" in result
        assert "2:1" in result

    def test_decode_handicap(self):
        result = decode_odds_key("HANDICAP_MINUS_1_HOME", {})
        assert "Ф" in result

    def test_decode_first_period(self):
        result = decode_odds_key("FIRST_PERIOD_WIN_HOME", {})
        assert "1-й" in result
        assert "период" in result


# ─── NbClient integration tests (mocked HTTP) ──────────────────────────

class TestNbClient:
    def _make_client(self) -> NbClient:
        return NbClient(NbConfig())

    @patch("src.nb.client.requests.Session")
    def test_get_matches_for_date(self, mock_session_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SAMPLE_RESPONSE
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        mock_session.headers = {}

        client = NbClient(NbConfig())
        client._session = mock_session

        dt = datetime(2026, 2, 21, tzinfo=timezone.utc)
        matches = client.get_matches_for_date("soccer", dt)
        assert len(matches) == 1
        assert matches[0].team_home == "Manchester United"

    @patch("src.nb.client.requests.Session")
    def test_retry_on_failure(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session.headers = {}
        # First call fails, second succeeds
        fail_resp = MagicMock()
        fail_resp.status_code = 500
        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = SAMPLE_RESPONSE
        mock_session.get.side_effect = [fail_resp, ok_resp]

        client = NbClient(NbConfig(retries=2, retry_delay_seconds=0))
        client._session = mock_session

        dt = datetime(2026, 2, 21, tzinfo=timezone.utc)
        matches = client.get_matches_for_date("soccer", dt)
        assert len(matches) == 1
        assert mock_session.get.call_count == 2

    @patch("src.nb.client.requests.Session")
    def test_all_retries_exhausted(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session.headers = {}
        mock_session.get.side_effect = requests.ConnectionError("fail")

        client = NbClient(NbConfig(retries=2, retry_delay_seconds=0))
        client._session = mock_session

        dt = datetime(2026, 2, 21, tzinfo=timezone.utc)
        matches = client.get_matches_for_date("soccer", dt)
        assert matches == []
        assert mock_session.get.call_count == 2

    def test_proxy_rotation(self):
        client = NbClient(NbConfig(), proxy_list=["http://p1:8080", "http://p2:8080"])
        p1 = client._get_proxy()
        p2 = client._get_proxy()
        p3 = client._get_proxy()
        assert p1 == {"http": "http://p1:8080", "https": "http://p1:8080"}
        assert p2 == {"http": "http://p2:8080", "https": "http://p2:8080"}
        assert p3 == {"http": "http://p1:8080", "https": "http://p1:8080"}  # wraps

    def test_no_proxy(self):
        client = NbClient(NbConfig())
        assert client._get_proxy() is None
