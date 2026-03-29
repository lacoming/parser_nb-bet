"""Tests for VkNotifier."""
from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import MagicMock, patch, call

import pytest

from src.vk.notifier import VkNotifier, SendResult


# ── VkNotifier init ──────────────────────────────────────────────


class TestNotifierInit:
    def test_enabled_with_token_and_peer(self):
        n = VkNotifier("tok123", 2000000001)
        assert n.enabled is True

    def test_disabled_no_token(self):
        n = VkNotifier("", 2000000001)
        assert n.enabled is False

    def test_disabled_no_peer(self):
        n = VkNotifier("tok", 0)
        assert n.enabled is False

    def test_rate_limit_default(self):
        n = VkNotifier("tok", 1)
        assert n.rate_limit == 1.0


# ── _send_message ────────────────────────────────────────────────


class TestSendMessage:
    def _notifier(self) -> VkNotifier:
        return VkNotifier("tok", 100, rate_limit=0)

    @patch("src.vk.notifier.requests.post")
    def test_success(self, mock_post):
        mock_post.return_value = MagicMock(
            json=lambda: {"response": 12345}
        )
        n = self._notifier()
        res = n._send_message("hello")
        assert res.ok is True
        assert res.peer_id == 100
        mock_post.assert_called_once()
        call_data = mock_post.call_args
        assert call_data[1]["data"]["peer_id"] == 100
        assert call_data[1]["data"]["message"] == "hello"
        assert "access_token" in call_data[1]["data"]

    @patch("src.vk.notifier.requests.post")
    def test_error_response(self, mock_post):
        mock_post.return_value = MagicMock(
            json=lambda: {"error": {"error_code": 901, "error_msg": "Can't send to this user"}}
        )
        n = self._notifier()
        res = n._send_message("hello")
        assert res.ok is False
        assert "Can't send" in res.error

    @patch("src.vk.notifier.requests.post")
    def test_network_error(self, mock_post):
        import requests as req
        mock_post.side_effect = req.ConnectionError("timeout")
        n = self._notifier()
        res = n._send_message("test")
        assert res.ok is False
        assert "timeout" in res.error


# ── broadcast ────────────────────────────────────────────────────


class TestBroadcast:
    @patch("src.vk.notifier.requests.post")
    def test_sends_to_peer(self, mock_post):
        mock_post.return_value = MagicMock(json=lambda: {"response": 1})
        n = VkNotifier("tok", 100, rate_limit=0)
        results = n._broadcast("hello")
        assert len(results) == 1
        assert results[0].ok

    def test_disabled_returns_empty(self):
        n = VkNotifier("", 100)
        results = n._broadcast("hello")
        assert results == []


# ── notify_placed ────────────────────────────────────────────────


class TestNotifyPlaced:
    @patch("src.vk.notifier.requests.post")
    def test_dry_run_message(self, mock_post):
        mock_post.return_value = MagicMock(json=lambda: {"response": 1})
        n = VkNotifier("tok", 100, rate_limit=0)
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
            match_time="19:30",
            match_date="21.02.2026",
            odds_1="1.80",
            odds_x="3.50",
            odds_2="4.20",
            link="https://nb-bet.com/match/123",
        )
        assert len(results) == 1
        assert results[0].ok is True
        sent_text = mock_post.call_args[1]["data"]["message"]
        assert "Kush+" in sent_text
        assert "dry" in sent_text
        assert "Arsenal" in sent_text
        assert "19:30" in sent_text
        assert "21.02.2026" in sent_text
        assert "1.80 - 3.50 - 4.20" in sent_text

    @patch("src.vk.notifier.requests.post")
    def test_real_message(self, mock_post):
        mock_post.return_value = MagicMock(json=lambda: {"response": 1})
        n = VkNotifier("tok", 100, rate_limit=0)
        results = n.notify_placed(
            match_key="k",
            bet_type="П2",
            kf_nb=1.50,
            kf_kush=1.90,
            ratio=1.33,
            threshold=1.10,
            dry_run=False,
            match_time="20:00",
            match_date="24.02.2026",
        )
        sent_text = mock_post.call_args[1]["data"]["message"]
        assert "Kush+" in sent_text
        assert "dry" not in sent_text.lower()
        assert "1.33" in sent_text

    @patch("src.vk.notifier.requests.post")
    def test_was_pending_flag(self, mock_post):
        mock_post.return_value = MagicMock(json=lambda: {"response": 1})
        n = VkNotifier("tok", 100, rate_limit=0)
        results = n.notify_placed(
            match_key="k",
            bet_type="П1",
            kf_nb=2.00,
            kf_kush=2.40,
            ratio=1.20,
            threshold=1.10,
            dry_run=True,
            was_pending=True,
        )
        sent_text = mock_post.call_args[1]["data"]["message"]
        assert "ранее ожидала" in sent_text

    @patch("src.vk.notifier.requests.post")
    def test_no_was_pending_by_default(self, mock_post):
        mock_post.return_value = MagicMock(json=lambda: {"response": 1})
        n = VkNotifier("tok", 100, rate_limit=0)
        results = n.notify_placed(
            match_key="k",
            bet_type="П1",
            kf_nb=2.00,
            kf_kush=2.40,
            ratio=1.20,
            threshold=1.10,
            dry_run=True,
        )
        sent_text = mock_post.call_args[1]["data"]["message"]
        assert "ранее ожидала" not in sent_text


# ── notify_missing ───────────────────────────────────────────────


class TestNotifyMissing:
    @patch("src.vk.notifier.requests.post")
    def test_missing_message(self, mock_post):
        mock_post.return_value = MagicMock(json=lambda: {"response": 1})
        n = VkNotifier("tok", 100, rate_limit=0)
        results = n.notify_missing(
            match_key="La Liga|Barca|Real|20260301",
            league="La Liga",
            team_home="Barca",
            team_away="Real",
            match_time="22:00",
            match_date="01.03.2026",
            bet_type="1X",
            odds_1="1.60",
            odds_x="3.80",
            odds_2="5.00",
            link="https://nb-bet.com/match/456",
        )
        assert results[0].ok is True
        sent_text = mock_post.call_args[1]["data"]["message"]
        assert "kush-off" in sent_text
        assert "Barca" in sent_text
        assert "22:00" in sent_text
        assert "1X" in sent_text


# ── notify_pending ──────────────────────────────────────────────


class TestNotifyPending:
    @patch("src.vk.notifier.requests.post")
    def test_pending_message(self, mock_post):
        mock_post.return_value = MagicMock(json=lambda: {"response": 1})
        n = VkNotifier("tok", 100, rate_limit=0)
        results = n.notify_pending(
            match_key="La Liga|Barca|Sevilla|20260310",
            league="La Liga",
            team_home="Barcelona",
            team_away="Sevilla",
            match_time="20:00",
            match_date="10.03.2026",
            bet_type="1",
            odds_1="1.80",
            odds_x="3.50",
            odds_2="4.20",
            link="https://nb-bet.com/soccer/barca-sevilla-123",
        )
        assert results[0].ok is True
        sent_text = mock_post.call_args[1]["data"]["message"]
        assert "ожидает" in sent_text
        assert "Barcelona" in sent_text
        assert "20:00" in sent_text
        assert "Ставка" in sent_text


# ── notify_ratio_rejected ───────────────────────────────────────


class TestNotifyRatioRejected:
    @patch("src.vk.notifier.requests.post")
    def test_ratio_rejected_message(self, mock_post):
        mock_post.return_value = MagicMock(json=lambda: {"response": 1})
        n = VkNotifier("tok", 100, rate_limit=0)
        results = n.notify_ratio_rejected(
            match_key="Bundesliga|Bayern|Dortmund|20260301",
            bet_type="1",
            kf_nb=1.40,
            kf_kush=1.50,
            ratio=1.05,
            threshold=1.10,
            league="Bundesliga",
            team_home="Bayern",
            team_away="Dortmund",
            match_time="18:30",
            match_date="01.03.2026",
            odds_1="1.40",
            odds_x="4.50",
            odds_2="6.00",
            link="https://nb-bet.com/match/789",
        )
        assert len(results) == 1
        assert results[0].ok is True
        sent_text = mock_post.call_args[1]["data"]["message"]
        assert "ratio-off" in sent_text
        assert "Bayern" in sent_text
        assert "18:30" in sent_text
        assert "1.05" in sent_text
        assert "1.10" in sent_text


# ── notify_critical ──────────────────────────────────────────────


class TestNotifyCritical:
    @patch("src.vk.notifier.requests.post")
    def test_critical_message(self, mock_post):
        mock_post.return_value = MagicMock(json=lambda: {"response": 1})
        n = VkNotifier("tok", 100, rate_limit=0)
        results = n.notify_critical("Connection refused to nb-bet.com")
        assert results[0].ok is True
        sent_text = mock_post.call_args[1]["data"]["message"]
        assert "CRITICAL" in sent_text

    @patch("src.vk.notifier.requests.post")
    def test_truncates_long_error(self, mock_post):
        mock_post.return_value = MagicMock(json=lambda: {"response": 1})
        n = VkNotifier("tok", 100, rate_limit=0)
        long_err = "x" * 5000
        n.notify_critical(long_err)
        sent_text = mock_post.call_args[1]["data"]["message"]
        assert len(sent_text) < 3200


# ── notify_cycle_summary ────────────────────────────────────────


class TestNotifyCycleSummary:
    @patch("src.vk.notifier.requests.post")
    def test_summary(self, mock_post):
        mock_post.return_value = MagicMock(json=lambda: {"response": 1})
        n = VkNotifier("tok", 100, rate_limit=0)
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
        sent_text = mock_post.call_args[1]["data"]["message"]
        assert "Итоги цикла" in sent_text
        assert "DRY-RUN" in sent_text

    @patch("src.vk.notifier.requests.post")
    def test_summary_with_pending_and_rejected(self, mock_post):
        mock_post.return_value = MagicMock(json=lambda: {"response": 1})
        n = VkNotifier("tok", 100, rate_limit=0)
        results = n.notify_cycle_summary(
            total_matches=200,
            filtered=50,
            decided=20,
            matched=10,
            placed=5,
            missing=3,
            errors=0,
            dry_run=False,
            pending=185,
            rejected=2,
        )
        assert results[0].ok is True
        sent_text = mock_post.call_args[1]["data"]["message"]
        assert "Ожидают" in sent_text
        assert "185" in sent_text
        assert "Отклонено" in sent_text
        assert "2" in sent_text


# ── send_test ────────────────────────────────────────────────────


class TestSendTest:
    @patch("src.vk.notifier.requests.post")
    def test_test_message(self, mock_post):
        mock_post.return_value = MagicMock(json=lambda: {"response": 1})
        n = VkNotifier("tok", 100, rate_limit=0)
        results = n.send_test()
        assert len(results) == 1
        assert results[0].ok
        sent_text = mock_post.call_args[1]["data"]["message"]
        assert "Тестовое сообщение" in sent_text


# ── send_document ────────────────────────────────────────────────


class TestSendDocument:
    def _mock_upload_flow(self, mock_post):
        """Set up mock responses for the 4-step upload flow."""
        mock_post.side_effect = [
            # Step 1: docs.getMessagesUploadServer
            MagicMock(json=lambda: {"response": {"upload_url": "https://pu.vk.com/upload"}}),
            # Step 2: upload file to VK server
            MagicMock(json=lambda: {"file": "uploaded_file_token_abc"}),
            # Step 3: docs.save
            MagicMock(json=lambda: {"response": {"doc": {"owner_id": -200, "id": 456}}}),
            # Step 4: messages.send with attachment
            MagicMock(json=lambda: {"response": 12345}),
        ]

    @patch("src.vk.notifier.requests.post")
    def test_full_upload_flow(self, mock_post):
        self._mock_upload_flow(mock_post)
        n = VkNotifier("tok", 100, rate_limit=0)
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            f.write(b"fake excel")
            tmp = f.name
        try:
            results = n.send_document(tmp, caption="Результаты цикла")
            assert len(results) == 1
            assert results[0].ok is True

            # Verify all 4 API calls were made
            assert mock_post.call_count == 4

            # Step 4: messages.send should have attachment
            send_call = mock_post.call_args_list[3]
            send_data = send_call[1]["data"] if "data" in send_call[1] else send_call[0][1]
            assert send_data["attachment"] == "doc-200_456"
            assert send_data["message"] == "Результаты цикла"
        finally:
            os.unlink(tmp)

    @patch("src.vk.notifier.requests.post")
    def test_upload_without_caption(self, mock_post):
        self._mock_upload_flow(mock_post)
        n = VkNotifier("tok", 100, rate_limit=0)
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            f.write(b"fake")
            tmp = f.name
        try:
            results = n.send_document(tmp)
            assert results[0].ok is True
            send_data = mock_post.call_args_list[3][1]["data"]
            assert "message" not in send_data
        finally:
            os.unlink(tmp)

    def test_disabled_returns_empty(self):
        n = VkNotifier("", 100, rate_limit=0)
        results = n.send_document("file.xlsx")
        assert results == []

    def test_file_not_found(self):
        n = VkNotifier("tok", 100, rate_limit=0)
        results = n.send_document("/nonexistent/file.xlsx")
        assert len(results) == 1
        assert results[0].ok is False
        assert "not found" in results[0].error.lower()

    @patch("src.vk.notifier.requests.post")
    def test_get_upload_server_fails(self, mock_post):
        mock_post.return_value = MagicMock(
            json=lambda: {"error": {"error_code": 15, "error_msg": "Access denied"}}
        )
        n = VkNotifier("tok", 100, rate_limit=0)
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            f.write(b"data")
            tmp = f.name
        try:
            results = n.send_document(tmp)
            assert results[0].ok is False
            assert "Access denied" in results[0].error
        finally:
            os.unlink(tmp)

    @patch("src.vk.notifier.requests.post")
    def test_file_upload_fails(self, mock_post):
        mock_post.side_effect = [
            MagicMock(json=lambda: {"response": {"upload_url": "https://pu.vk.com/upload"}}),
            MagicMock(json=lambda: {"error": "upload failed"}),
        ]
        n = VkNotifier("tok", 100, rate_limit=0)
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            f.write(b"data")
            tmp = f.name
        try:
            results = n.send_document(tmp)
            assert results[0].ok is False
            assert "upload" in results[0].error.lower()
        finally:
            os.unlink(tmp)

    @patch("src.vk.notifier.requests.post")
    def test_docs_save_fails(self, mock_post):
        mock_post.side_effect = [
            MagicMock(json=lambda: {"response": {"upload_url": "https://pu.vk.com/upload"}}),
            MagicMock(json=lambda: {"file": "token"}),
            MagicMock(json=lambda: {"error": {"error_msg": "save failed"}}),
        ]
        n = VkNotifier("tok", 100, rate_limit=0)
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            f.write(b"data")
            tmp = f.name
        try:
            results = n.send_document(tmp)
            assert results[0].ok is False
            assert "save" in results[0].error.lower()
        finally:
            os.unlink(tmp)

    @patch("src.vk.notifier.requests.post")
    def test_docs_save_list_format(self, mock_post):
        """VK sometimes returns docs.save response as a list instead of dict."""
        mock_post.side_effect = [
            MagicMock(json=lambda: {"response": {"upload_url": "https://pu.vk.com/upload"}}),
            MagicMock(json=lambda: {"file": "token"}),
            MagicMock(json=lambda: {"response": [{"owner_id": -200, "id": 789}]}),
            MagicMock(json=lambda: {"response": 1}),
        ]
        n = VkNotifier("tok", 100, rate_limit=0)
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            f.write(b"data")
            tmp = f.name
        try:
            results = n.send_document(tmp)
            assert results[0].ok is True
            send_data = mock_post.call_args_list[3][1]["data"]
            assert send_data["attachment"] == "doc-200_789"
        finally:
            os.unlink(tmp)


# ── rate limiting ────────────────────────────────────────────────


class TestRateLimit:
    @patch("src.vk.notifier.time.sleep")
    @patch("src.vk.notifier.requests.post")
    @patch("src.vk.notifier.time.time")
    def test_rate_limit_sleeps(self, mock_time, mock_post, mock_sleep):
        mock_post.return_value = MagicMock(json=lambda: {"response": 1})
        mock_time.side_effect = [100.3, 100.3]
        n = VkNotifier("tok", 100, rate_limit=1.0)
        n._last_send = 100.0
        n._send_message("hello")
        mock_sleep.assert_called()
        sleep_val = mock_sleep.call_args[0][0]
        assert 0.6 < sleep_val < 0.8
