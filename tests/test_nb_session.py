"""Tests for NbSession (JWT authentication)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.nb.session import NbSession, NbSessionError


class TestNbSessionLogin:
    """Tests for NbSession.login()."""

    def test_login_success(self):
        session = NbSession(request_delay=0)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": {
                "status": "success",
                "token": "eyJfake_token",
                "name": "testuser",
                "url": 12345,
            }
        }

        with patch.object(session, "_session") as mock_s:
            mock_s.post.return_value = mock_resp
            result = session.login("test@example.com", "pass123")

        assert result is True
        assert session.logged_in is True
        assert session.token == "eyJfake_token"

    def test_login_bad_credentials(self):
        session = NbSession(request_delay=0)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": {"status": "error", "message": "Invalid credentials"}
        }

        with patch.object(session, "_session") as mock_s:
            mock_s.post.return_value = mock_resp
            with pytest.raises(NbSessionError, match="Login failed"):
                session.login("bad@example.com", "wrong")

        assert session.logged_in is False

    def test_login_http_error(self):
        session = NbSession(request_delay=0)
        mock_resp = MagicMock()
        mock_resp.status_code = 500

        with patch.object(session, "_session") as mock_s:
            mock_s.post.return_value = mock_resp
            with pytest.raises(NbSessionError, match="HTTP 500"):
                session.login("test@example.com", "pass")

    def test_login_no_token_in_response(self):
        session = NbSession(request_delay=0)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": {"status": "success", "token": "", "name": "user"}
        }

        with patch.object(session, "_session") as mock_s:
            mock_s.post.return_value = mock_resp
            with pytest.raises(NbSessionError, match="missing token"):
                session.login("test@example.com", "pass")

    def test_login_network_error(self):
        import requests
        session = NbSession(request_delay=0)

        with patch.object(session, "_session") as mock_s:
            mock_s.post.side_effect = requests.ConnectionError("timeout")
            with pytest.raises(NbSessionError, match="request failed"):
                session.login("test@example.com", "pass")

    def test_login_sets_authorization_header(self):
        session = NbSession(request_delay=0)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": {"status": "success", "token": "jwt_abc", "name": "u"}
        }

        with patch.object(session, "_session") as mock_s:
            mock_s.headers = {}
            mock_s.post.return_value = mock_resp
            session.login("test@example.com", "pass")

        assert mock_s.headers["authorization"] == "jwt_abc"


class TestNbSessionPostJson:
    """Tests for NbSession.post_json()."""

    def test_post_json_success(self):
        session = NbSession(request_delay=0, retries=1)
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch.object(session, "_session") as mock_s:
            mock_s.post.return_value = mock_resp
            result = session.post_json("/test/path", {"key": "val"})

        assert result == mock_resp

    def test_post_json_retry_on_failure(self):
        session = NbSession(request_delay=0, retries=2, retry_delay=0)
        fail_resp = MagicMock()
        fail_resp.status_code = 500
        ok_resp = MagicMock()
        ok_resp.status_code = 200

        with patch.object(session, "_session") as mock_s:
            mock_s.post.side_effect = [fail_resp, ok_resp]
            result = session.post_json("/path", {})

        assert result == ok_resp
        assert mock_s.post.call_count == 2

    def test_post_json_all_retries_exhausted(self):
        session = NbSession(request_delay=0, retries=2, retry_delay=0)
        fail_resp = MagicMock()
        fail_resp.status_code = 500

        with patch.object(session, "_session") as mock_s:
            mock_s.post.return_value = fail_resp
            with pytest.raises(NbSessionError, match="failed after 2 attempts"):
                session.post_json("/path", {})

    def test_initial_state(self):
        session = NbSession()
        assert session.logged_in is False
        assert session.token == ""
