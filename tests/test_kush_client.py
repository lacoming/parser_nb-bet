"""Tests for Kush session and client (HTML parsing, no real HTTP)."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from src.kush.session import KushSession, KushSessionError
from src.kush.client import (
    KushClient,
    OddsEntry,
    _parse_leagues,
    _parse_events,
    _parse_odds,
    _find_odds_entry,
    _extract_event_id,
)
from src.kush.models import KushEvent


# ---------------------------------------------------------------------------
# HTML fixtures
# ---------------------------------------------------------------------------

LEAGUES_HTML = """
<html><body>
<a class="centerEventLink" data-cid="42">
  <span class="align-super">Англия. Премьер-Лига</span>
</a>
<a class="centerEventLink" data-cid="55">
  <span class="align-super">Испания. Ла Лига</span>
</a>
<a class="centerEventLink" data-cid="">
  <span class="align-super">Empty CID</span>
</a>
</body></html>
"""

EVENTS_HTML = """
<html><body>
<div class="event-row">
  <div class="medium-text">21.02.2026</div>
  <div class="d-inline-block d-md-block">Сб 18:00</div>
  <a class="d-block" href="/event/12345-man-utd-vs-liverpool">
    <div class="medium-text">Manchester United</div>
    <div class="medium-text">Liverpool</div>
  </a>
</div>
<div class="event-row">
  <div class="medium-text">22.02.2026</div>
  <a class="d-block" href="/event/67890-chelsea-vs-arsenal">
    <div class="medium-text">Chelsea</div>
    <div class="medium-text">Arsenal</div>
  </a>
</div>
</body></html>
"""

EVENTS_HTML_MISSING_TEAMS = """
<html><body>
<a class="d-block" href="/event/99999-broken">
  <div class="medium-text">Only One Team</div>
</a>
</body></html>
"""

EVENTS_HTML_NO_HREF = """
<html><body>
<a class="d-block">
  <div class="medium-text">Team A</div>
  <div class="medium-text">Team B</div>
</a>
</body></html>
"""

ODDS_HTML = """
<html><body>
<button class="coefLink">
  <div class="d-sm-none">П1</div>
  <span>2.10</span>
</button>
<button class="coefLink">
  <div class="d-sm-none">X</div>
  <span>3.20</span>
</button>
<button class="coefLink">
  <div class="d-sm-none">П2</div>
  <span>2.80</span>
</button>
<button class="coefLink">
  <div class="d-sm-none">1X</div>
  <span>1.35</span>
</button>
</body></html>
"""

ODDS_HTML_INVALID = """
<html><body>
<button class="coefLink">
  <div class="d-sm-none">П1</div>
  <span>abc</span>
</button>
<button class="coefLink">
  <div class="d-sm-none"></div>
  <span>2.00</span>
</button>
<button class="coefLink">
  <span>3.00</span>
</button>
</body></html>
"""

ODDS_WITH_URL = """
<html><body>
<button class="coefLink" url="/coupon/add-coupon?eid=123&cfid=456">
  <div class="d-sm-none">П1</div>
  <span>2.10</span>
</button>
<button class="coefLink" url="/coupon/add-coupon?eid=123&cfid=789">
  <div class="d-sm-none">П2</div>
  <span>3.50</span>
</button>
</body></html>
"""

CSRF_PAGE_HTML = """
<html>
<head><meta name="csrf-token" content="abc123csrf456"></head>
<body></body>
</html>
"""

LOGIN_FORM_HTML = """
<html><body>
<form id="login-widget-form" action="/users/login">
  <input type="hidden" name="_csrf" value="login_csrf_token_123">
  <input type="text" name="login-form[login]">
  <input type="password" name="login-form[password]">
</form>
</body></html>
"""

LOGIN_FAIL_HTML = """
<html><body>
<div>Неправильный логин или пароль</div>
</body></html>
"""


# ---------------------------------------------------------------------------
# Tests: _parse_leagues
# ---------------------------------------------------------------------------

class TestParseLeagues:
    def test_basic(self):
        result = _parse_leagues(LEAGUES_HTML)
        assert result == {"42": "Англия. Премьер-Лига", "55": "Испания. Ла Лига"}

    def test_skips_empty_cid(self):
        result = _parse_leagues(LEAGUES_HTML)
        assert "" not in result
        assert len(result) == 2

    def test_empty_html(self):
        assert _parse_leagues("<html></html>") == {}

    def test_no_leagues(self):
        assert _parse_leagues("<html><body><div>nothing</div></body></html>") == {}


# ---------------------------------------------------------------------------
# Tests: _parse_events
# ---------------------------------------------------------------------------

class TestParseEvents:
    def test_basic(self):
        events = _parse_events(EVENTS_HTML, cid="42")
        assert len(events) == 2
        assert events[0].event_id == "12345"
        assert events[0].team_home == "Manchester United"
        assert events[0].team_away == "Liverpool"
        assert events[1].event_id == "67890"
        assert events[1].team_home == "Chelsea"
        assert events[1].team_away == "Arsenal"

    def test_url_preserved(self):
        events = _parse_events(EVENTS_HTML, cid="42")
        assert events[0].url == "/event/12345-man-utd-vs-liverpool"

    def test_skips_missing_teams(self):
        events = _parse_events(EVENTS_HTML_MISSING_TEAMS)
        assert len(events) == 0

    def test_skips_no_href(self):
        events = _parse_events(EVENTS_HTML_NO_HREF)
        assert len(events) == 0

    def test_empty_html(self):
        assert _parse_events("<html></html>") == []


# ---------------------------------------------------------------------------
# Tests: _parse_odds
# ---------------------------------------------------------------------------

class TestParseOdds:
    def test_basic(self):
        odds = _parse_odds(ODDS_HTML)
        assert odds == {"П1": 2.10, "X": 3.20, "П2": 2.80, "1X": 1.35}

    def test_invalid_values_skipped(self):
        odds = _parse_odds(ODDS_HTML_INVALID)
        assert len(odds) == 0

    def test_empty_html(self):
        assert _parse_odds("<html></html>") == {}


# ---------------------------------------------------------------------------
# Tests: _find_odds_entry
# ---------------------------------------------------------------------------

class TestFindOddsEntry:
    def test_found(self):
        entry = _find_odds_entry(ODDS_HTML, "П1", 1.0, 5.0)
        assert entry is not None
        assert entry.bet_type == "П1"
        assert entry.coefficient == 2.10

    def test_not_found_wrong_type(self):
        entry = _find_odds_entry(ODDS_HTML, "Тотал", 1.0, 5.0)
        assert entry is None

    def test_not_found_out_of_range(self):
        entry = _find_odds_entry(ODDS_HTML, "П1", 3.0, 5.0)
        assert entry is None

    def test_url_extraction(self):
        entry = _find_odds_entry(ODDS_WITH_URL, "П1", 1.0, 5.0)
        assert entry is not None
        assert entry.cfid == "456"
        assert entry.eid == "123"

    def test_entry_repr(self):
        e = OddsEntry("П1", 2.10, "456", "123")
        assert "П1" in repr(e)
        assert "2.1" in repr(e)


# ---------------------------------------------------------------------------
# Tests: _extract_event_id
# ---------------------------------------------------------------------------

class TestExtractEventId:
    def test_standard(self):
        assert _extract_event_id("/event/12345-something") == "12345"

    def test_numeric_only(self):
        assert _extract_event_id("/event/99999") == "99999"

    def test_no_match(self):
        assert _extract_event_id("/some/path") == ""

    def test_empty(self):
        assert _extract_event_id("") == ""


# ---------------------------------------------------------------------------
# Tests: KushSession
# ---------------------------------------------------------------------------

class TestKushSession:
    def test_init_defaults(self):
        s = KushSession()
        assert s.csrf_token == ""
        assert s.logged_in is False

    def test_init_csrf_success(self):
        s = KushSession(request_delay=0)
        mock_resp = MagicMock()
        mock_resp.text = CSRF_PAGE_HTML
        mock_resp.status_code = 200

        with patch.object(s._session, "get", return_value=mock_resp):
            token = s.init_csrf()
            assert token == "abc123csrf456"
            assert s.csrf_token == "abc123csrf456"

    def test_init_csrf_no_meta_raises(self):
        s = KushSession(request_delay=0)
        mock_resp = MagicMock()
        mock_resp.text = "<html><head></head></html>"
        mock_resp.status_code = 200

        with patch.object(s._session, "get", return_value=mock_resp):
            with pytest.raises(KushSessionError, match="CSRF"):
                s.init_csrf()

    def test_login_success(self):
        s = KushSession(request_delay=0)
        # First GET returns login form
        login_resp = MagicMock()
        login_resp.text = LOGIN_FORM_HTML
        login_resp.status_code = 200
        # POST returns success (no error message)
        post_resp = MagicMock()
        post_resp.text = "<html><body>Welcome</body></html>"
        post_resp.status_code = 200
        # init_csrf after login
        csrf_resp = MagicMock()
        csrf_resp.text = CSRF_PAGE_HTML
        csrf_resp.status_code = 200

        with patch.object(s._session, "get", side_effect=[login_resp, csrf_resp]):
            with patch.object(s._session, "post", return_value=post_resp):
                result = s.login("user", "pass")
                assert result is True
                assert s.logged_in is True

    def test_login_bad_credentials(self):
        s = KushSession(request_delay=0)
        login_resp = MagicMock()
        login_resp.text = LOGIN_FORM_HTML
        login_resp.status_code = 200
        fail_resp = MagicMock()
        fail_resp.text = LOGIN_FAIL_HTML
        fail_resp.status_code = 200

        with patch.object(s._session, "get", return_value=login_resp):
            with patch.object(s._session, "post", return_value=fail_resp):
                with pytest.raises(KushSessionError, match="Invalid"):
                    s.login("user", "wrong")

    def test_proxy_set(self):
        s = KushSession(proxy="http://1.2.3.4:8080")
        assert s._session.proxies["http"] == "http://1.2.3.4:8080"


# ---------------------------------------------------------------------------
# Tests: KushClient (integration with mocked session)
# ---------------------------------------------------------------------------

class TestKushClient:
    def _mock_session(self):
        session = MagicMock(spec=KushSession)
        session._base_url = "https://kushvsporte.ru"
        return session

    def test_get_leagues(self):
        session = self._mock_session()
        resp = MagicMock()
        resp.text = LEAGUES_HTML
        session.get.return_value = resp

        client = KushClient(session)
        leagues = client.get_leagues(day=0)
        assert "42" in leagues
        assert leagues["42"] == "Англия. Премьер-Лига"

    def test_get_events(self):
        session = self._mock_session()
        resp = MagicMock()
        resp.text = EVENTS_HTML
        session.post.return_value = resp

        client = KushClient(session)
        events = client.get_events("42", day=0)
        assert len(events) == 2
        assert events[0].team_home == "Manchester United"

    def test_get_all_events(self):
        session = self._mock_session()
        # get_leagues response
        leagues_resp = MagicMock()
        leagues_resp.text = LEAGUES_HTML
        session.get.return_value = leagues_resp
        # get_events response (same for both leagues)
        events_resp = MagicMock()
        events_resp.text = EVENTS_HTML
        session.post.return_value = events_resp

        client = KushClient(session)
        events = client.get_all_events(day=0)
        # 2 leagues * 2 events each
        assert len(events) == 4

    def test_get_odds(self):
        session = self._mock_session()
        resp = MagicMock()
        resp.text = ODDS_HTML
        session.post.return_value = resp

        client = KushClient(session)
        odds = client.get_odds("12345")
        assert odds["П1"] == 2.10
        assert odds["X"] == 3.20
        assert odds["П2"] == 2.80

    def test_find_odds_entry(self):
        session = self._mock_session()
        resp = MagicMock()
        resp.text = ODDS_WITH_URL
        session.post.return_value = resp

        client = KushClient(session)
        entry = client.find_odds_entry("123", "П1", 1.0, 5.0)
        assert entry is not None
        assert entry.coefficient == 2.10
        assert entry.cfid == "456"

    def test_find_odds_entry_not_found(self):
        session = self._mock_session()
        resp = MagicMock()
        resp.text = ODDS_HTML
        session.post.return_value = resp

        client = KushClient(session)
        entry = client.find_odds_entry("123", "NonExistent", 1.0, 5.0)
        assert entry is None
