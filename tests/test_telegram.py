"""Tests for TelegramNotifier (step 07)."""
from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import MagicMock, patch, call

import pytest

from src.telegram.notifier import TelegramNotifier, SendResult, escape_md2


# ── escape_md2 ──────────────────────────────────────────────────────


class TestEscapeMd2:
    def test_plain_text(self):
        assert escape_md2("hello world") == "hello world"

    def test_special_chars(self):
        result = escape_md2("foo.bar_baz*qux")
        assert result == "foo\\.bar\\_baz\\*qux"

    def test_all_special(self):
        for ch in "_*[]()~`>#+-=|{}.!":
            assert escape_md2(ch) == f"\\{ch}"

    def test_empty_string(self):
        assert escape_md2("") == ""

    def test_mixed(self):
        assert escape_md2("A (B)") == "A \\(B\\)"


# ── TelegramNotifier init ───────────────────────────────────────────


class TestNotifierInit:
    def test_enabled_with_token_and_chats(self):
        n = TelegramNotifier("tok123", [111, 222])
        assert n.enabled is True

    def test_disabled_no_token(self):
        n = TelegramNotifier("", [111])
        assert n.enabled is False

    def test_disabled_no_chats(self):
        n = TelegramNotifier("tok", [])
        assert n.enabled is False

    def test_rate_limit_default(self):
        n = TelegramNotifier("tok", [1])
        assert n.rate_limit == 1.0


# ── _send_message ────────────────────────────────────────────────────


class TestSendMessage:
    def _notifier(self) -> TelegramNotifier:
        return TelegramNotifier("tok", [100], rate_limit=0)

    @patch("src.telegram.notifier.requests.post")
    def test_success(self, mock_post):
        mock_post.return_value = MagicMock(
            json=lambda: {"ok": True, "result": {"message_id": 1}}
        )
        n = self._notifier()
        res = n._send_message(100, "hello")
        assert res.ok is True
        assert res.chat_id == 100
        mock_post.assert_called_once()
        call_data = mock_post.call_args
        assert call_data[1]["data"]["chat_id"] == 100
        assert call_data[1]["data"]["parse_mode"] == "MarkdownV2"

    @patch("src.telegram.notifier.requests.post")
    def test_md2_fallback_to_plain(self, mock_post):
        """If MarkdownV2 fails, retry without parse_mode."""
        mock_post.return_value = MagicMock(
            json=lambda: {"ok": False, "description": "can't parse entities"}
        )
        n = self._notifier()
        # Will fail on md2, then retry plain, then fail plain too
        res = n._send_message(100, "bad *md")
        assert res.ok is False
        assert mock_post.call_count == 2
        # Second call should not have parse_mode
        second_data = mock_post.call_args_list[1][1]["data"]
        assert "parse_mode" not in second_data

    @patch("src.telegram.notifier.requests.post")
    def test_md2_fallback_success(self, mock_post):
        """MD2 fails, plain succeeds."""
        responses = [
            MagicMock(json=lambda: {"ok": False, "description": "parse error"}),
            MagicMock(json=lambda: {"ok": True, "result": {}}),
        ]
        mock_post.side_effect = responses
        n = self._notifier()
        res = n._send_message(100, "text")
        assert res.ok is True

    @patch("src.telegram.notifier.requests.post")
    def test_network_error(self, mock_post):
        import requests as req
        mock_post.side_effect = req.ConnectionError("timeout")
        n = self._notifier()
        res = n._send_message(100, "test")
        # Fallback attempt also fails
        assert res.ok is False
        assert "timeout" in res.error


# ── broadcast ────────────────────────────────────────────────────────


class TestBroadcast:
    @patch("src.telegram.notifier.requests.post")
    def test_sends_to_all_chats(self, mock_post):
        mock_post.return_value = MagicMock(json=lambda: {"ok": True, "result": {}})
        n = TelegramNotifier("tok", [100, 200, 300], rate_limit=0)
        results = n._broadcast("hello")
        assert len(results) == 3
        assert all(r.ok for r in results)

    def test_disabled_returns_empty(self):
        n = TelegramNotifier("", [100])
        results = n._broadcast("hello")
        assert results == []


# ── notify_placed ────────────────────────────────────────────────────


class TestNotifyPlaced:
    @patch("src.telegram.notifier.requests.post")
    def test_dry_run_message(self, mock_post):
        mock_post.return_value = MagicMock(json=lambda: {"ok": True, "result": {}})
        n = TelegramNotifier("tok", [100], rate_limit=0)
        results = n.notify_placed(
            match_key="EPL|Arsenal|Chelsea|20260221",
            bet_type="П1",
            kf_nb=1.80,
            kf_kush=2.10,
            ratio=1.225,
            threshold=1.10,
            dry_run=True,
            league="EPL",
            team_home="Arsenal",
            team_away="Chelsea",
        )
        assert len(results) == 1
        assert results[0].ok is True
        sent_text = mock_post.call_args[1]["data"]["text"]
        assert "DRY\\-RUN" in sent_text
        assert "Arsenal" in sent_text

    @patch("src.telegram.notifier.requests.post")
    def test_real_message(self, mock_post):
        mock_post.return_value = MagicMock(json=lambda: {"ok": True, "result": {}})
        n = TelegramNotifier("tok", [100], rate_limit=0)
        results = n.notify_placed(
            match_key="k",
            bet_type="П2",
            kf_nb=1.50,
            kf_kush=1.90,
            ratio=1.33,
            threshold=1.10,
            dry_run=False,
        )
        sent_text = mock_post.call_args[1]["data"]["text"]
        assert "REAL" in sent_text


# ── notify_missing ───────────────────────────────────────────────────


class TestNotifyMissing:
    @patch("src.telegram.notifier.requests.post")
    def test_missing_message(self, mock_post):
        mock_post.return_value = MagicMock(json=lambda: {"ok": True, "result": {}})
        n = TelegramNotifier("tok", [100], rate_limit=0)
        results = n.notify_missing(
            match_key="La Liga|Barca|Real|20260301",
            league="La Liga",
            team_home="Barca",
            team_away="Real",
        )
        assert results[0].ok is True
        sent_text = mock_post.call_args[1]["data"]["text"]
        assert "Не найден" in sent_text
        assert "Barca" in sent_text


# ── notify_critical ──────────────────────────────────────────────────


class TestNotifyCritical:
    @patch("src.telegram.notifier.requests.post")
    def test_critical_message(self, mock_post):
        mock_post.return_value = MagicMock(json=lambda: {"ok": True, "result": {}})
        n = TelegramNotifier("tok", [100], rate_limit=0)
        results = n.notify_critical("Connection refused to nb-bet.com")
        assert results[0].ok is True
        sent_text = mock_post.call_args[1]["data"]["text"]
        assert "CRITICAL" in sent_text

    @patch("src.telegram.notifier.requests.post")
    def test_truncates_long_error(self, mock_post):
        mock_post.return_value = MagicMock(json=lambda: {"ok": True, "result": {}})
        n = TelegramNotifier("tok", [100], rate_limit=0)
        long_err = "x" * 5000
        n.notify_critical(long_err)
        sent_text = mock_post.call_args[1]["data"]["text"]
        # Should be truncated to 3000 chars of the error
        assert len(sent_text) < 3200


# ── notify_cycle_summary ────────────────────────────────────────────


class TestNotifyCycleSummary:
    @patch("src.telegram.notifier.requests.post")
    def test_summary(self, mock_post):
        mock_post.return_value = MagicMock(json=lambda: {"ok": True, "result": {}})
        n = TelegramNotifier("tok", [100], rate_limit=0)
        results = n.notify_cycle_summary(
            total_matches=50,
            filtered=30,
            decided=20,
            matched=15,
            placed=10,
            missing=5,
            errors=2,
            dry_run=True,
        )
        assert results[0].ok is True
        sent_text = mock_post.call_args[1]["data"]["text"]
        assert "Итоги цикла" in sent_text
        assert "DRY\\-RUN" in sent_text


# ── send_test ────────────────────────────────────────────────────────


class TestSendTest:
    @patch("src.telegram.notifier.requests.post")
    def test_test_message(self, mock_post):
        mock_post.return_value = MagicMock(json=lambda: {"ok": True, "result": {}})
        n = TelegramNotifier("tok", [100, 200], rate_limit=0)
        results = n.send_test()
        assert len(results) == 2
        assert all(r.ok for r in results)
        sent_text = mock_post.call_args[1]["data"]["text"]
        assert "Тестовое сообщение" in sent_text


# ── send_document ────────────────────────────────────────────────────


class TestSendDocument:
    @patch("src.telegram.notifier.requests.post")
    def test_send_file(self, mock_post):
        mock_post.return_value = MagicMock(json=lambda: {"ok": True, "result": {}})
        n = TelegramNotifier("tok", [100], rate_limit=0)

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            f.write(b"fake excel data")
            tmp_path = f.name

        try:
            results = n.send_document(tmp_path, caption="Results")
            assert len(results) == 1
            assert results[0].ok is True
            call_data = mock_post.call_args
            assert call_data[1]["data"]["caption"] == "Results"
            assert "document" in call_data[1]["files"]
        finally:
            os.unlink(tmp_path)

    def test_file_not_found(self):
        n = TelegramNotifier("tok", [100], rate_limit=0)
        results = n.send_document("/nonexistent/file.xlsx")
        assert len(results) == 1
        assert results[0].ok is False

    def test_disabled_returns_empty(self):
        n = TelegramNotifier("", [100], rate_limit=0)
        results = n.send_document("file.xlsx")
        assert results == []


# ── rate limiting ────────────────────────────────────────────────────


class TestRateLimit:
    @patch("src.telegram.notifier.time.sleep")
    @patch("src.telegram.notifier.requests.post")
    @patch("src.telegram.notifier.time.time")
    def test_rate_limit_sleeps(self, mock_time, mock_post, mock_sleep):
        mock_post.return_value = MagicMock(json=lambda: {"ok": True, "result": {}})
        # _wait_rate_limit calls time.time() once → 100.3
        # _last_send is 100.0, rate_limit is 1.0, elapsed=0.3 → sleep(0.7)
        # After send, time.time() is called to set _last_send → 100.3
        mock_time.side_effect = [100.3, 100.3]
        n = TelegramNotifier("tok", [100], rate_limit=1.0)
        n._last_send = 100.0  # Simulate previous send at t=100
        n._send_message(100, "hello")
        mock_sleep.assert_called()
        sleep_val = mock_sleep.call_args[0][0]
        assert 0.6 < sleep_val < 0.8
