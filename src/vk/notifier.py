"""VK API notifier.

Sends notifications about placed bets, missing events, critical errors,
and cycle summaries via VK messages.send API.
"""
from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from typing import Any

import requests

log = logging.getLogger("parser_nb_bet.vk.notifier")

# VK API base URL
_API = "https://api.vk.com/method/{method}"
_API_VERSION = "5.199"


@dataclass
class SendResult:
    """Result of a VK API call."""
    ok: bool
    peer_id: int
    error: str = ""


class VkNotifier:
    """Sends VK notifications via messages.send API.

    Args:
        token: VK API access token (from community/user).
        peer_id: VK peer ID (user, chat, or community conversation).
        rate_limit: Minimum seconds between messages (default 1.0).
        timeout: HTTP timeout in seconds (default 15).
    """

    def __init__(
        self,
        token: str,
        peer_id: int,
        rate_limit: float = 1.0,
        timeout: int = 15,
    ) -> None:
        self.token = token
        self.peer_id = peer_id
        self.rate_limit = rate_limit
        self.timeout = timeout
        self._last_send: float = 0.0

    @property
    def enabled(self) -> bool:
        return bool(self.token and self.peer_id)

    def _wait_rate_limit(self) -> None:
        """Wait to respect rate limit between messages."""
        if self.rate_limit <= 0:
            return
        elapsed = time.time() - self._last_send
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)

    def _api_call(
        self,
        method: str,
        params: dict[str, Any],
        files: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make a VK API call."""
        url = _API.format(method=method)
        params["access_token"] = self.token
        params["v"] = _API_VERSION
        try:
            if files:
                resp = requests.post(url, data=params, files=files, timeout=self.timeout)
            else:
                resp = requests.post(url, data=params, timeout=self.timeout)
            return resp.json()
        except requests.RequestException as e:
            return {"error": {"error_msg": str(e)}}

    def _send_message(self, text: str, peer_id: int = 0) -> SendResult:
        """Send a text message to one peer."""
        target = peer_id or self.peer_id
        self._wait_rate_limit()
        params = {
            "peer_id": target,
            "message": text,
            "random_id": random.randint(1, 2**31),
            "dont_parse_links": 1,
        }
        result = self._api_call("messages.send", params)
        self._last_send = time.time()

        if "response" in result:
            return SendResult(ok=True, peer_id=target)

        error = result.get("error", {})
        error_msg = error.get("error_msg", "unknown error") if isinstance(error, dict) else str(error)
        log.error("VK send failed for peer %s: %s", target, error_msg)
        return SendResult(ok=False, peer_id=target, error=error_msg)

    def _broadcast(self, text: str) -> list[SendResult]:
        """Send a message to the configured peer."""
        if not self.enabled:
            log.warning("VK not configured (no token or peer_id)")
            return []

        res = self._send_message(text)
        if res.ok:
            log.debug("Sent to peer %s", self.peer_id)
        else:
            log.error("Failed to send to peer %s: %s", self.peer_id, res.error)
        return [res]

    # ── Public notification methods ──────────────────────────────────

    def notify_placed(
        self,
        match_key: str,
        bet_type: str,
        kf_nb: float,
        kf_kush: float,
        ratio: float,
        threshold: float,
        dry_run: bool,
        league: str = "",
        team_home: str = "",
        team_away: str = "",
        match_time: str = "",
        match_date: str = "",
        odds_1: str = "",
        odds_x: str = "",
        odds_2: str = "",
        link: str = "",
        was_pending: bool = False,
    ) -> list[SendResult]:
        """Notify about a placed (or dry-run) bet."""
        status = "Kush+" if not dry_run else "Kush+ (dry)"
        lines = [
            status,
            f"{match_time} / {match_date}",
            league,
            f"{team_home} - {team_away}",
            f"{odds_1} - {odds_x} - {odds_2}",
            f"{bet_type}, КфКуша: {kf_kush:.2f}",
            f"Ratio: {ratio:.2f}",
        ]
        if was_pending:
            lines.append("ранее ожидала")
        if link:
            lines.append(link)
        text = "\n".join(lines)
        return self._broadcast(text)

    def notify_missing(
        self,
        match_key: str,
        league: str = "",
        team_home: str = "",
        team_away: str = "",
        match_time: str = "",
        match_date: str = "",
        bet_type: str = "",
        odds_1: str = "",
        odds_x: str = "",
        odds_2: str = "",
        link: str = "",
    ) -> list[SendResult]:
        """Notify that a match is missing on Kush."""
        lines = [
            "kush-off",
            f"{match_time} / {match_date}",
            league,
            f"{team_home} - {team_away}",
            f"{odds_1} - {odds_x} - {odds_2}",
        ]
        if bet_type:
            lines.append(f"Ставка: {bet_type}")
        if link:
            lines.append(link)
        text = "\n".join(lines)
        return self._broadcast(text)

    def notify_pending(
        self,
        match_key: str,
        league: str = "",
        team_home: str = "",
        team_away: str = "",
        match_time: str = "",
        match_date: str = "",
        bet_type: str = "",
        odds_1: str = "",
        odds_x: str = "",
        odds_2: str = "",
        link: str = "",
    ) -> list[SendResult]:
        """Notify that a match is pending (far-future, awaiting Kush window)."""
        lines = [
            "ожидает",
            f"{match_time} / {match_date}",
            league,
            f"{team_home} - {team_away}",
            f"{odds_1} - {odds_x} - {odds_2}",
        ]
        if bet_type:
            lines.append(f"Ставка: {bet_type}")
        if link:
            lines.append(link)
        text = "\n".join(lines)
        return self._broadcast(text)

    def notify_ratio_rejected(
        self,
        match_key: str,
        bet_type: str,
        kf_nb: float,
        kf_kush: float,
        ratio: float,
        threshold: float,
        league: str = "",
        team_home: str = "",
        team_away: str = "",
        match_time: str = "",
        match_date: str = "",
        odds_1: str = "",
        odds_x: str = "",
        odds_2: str = "",
        link: str = "",
    ) -> list[SendResult]:
        """Notify that a match was rejected by ratio threshold."""
        lines = [
            "ratio-off",
            f"{match_time} / {match_date}",
            league,
            f"{team_home} - {team_away}",
            f"{odds_1} - {odds_x} - {odds_2}",
            f"{bet_type}, КфКуша: {kf_kush:.2f}",
            f"Ratio: {ratio:.2f} (порог {threshold:.2f})",
        ]
        if link:
            lines.append(link)
        text = "\n".join(lines)
        return self._broadcast(text)

    def notify_insufficient_funds(
        self,
        platform: str,
        league: str = "",
        team_home: str = "",
        team_away: str = "",
        bet_type: str = "",
        error_detail: str = "",
    ) -> list[SendResult]:
        """Notify that a bet failed due to insufficient funds."""
        lines = [
            f"Не хватает средств на {platform}",
            f"Ставки на {platform} остановлены до следующего цикла.",
        ]
        if league:
            lines.append(f"Матч: {league}")
        if team_home and team_away:
            lines.append(f"{team_home} - {team_away}")
        if bet_type:
            lines.append(f"Ставка: {bet_type}")
        if error_detail:
            lines.append(f"Ответ: {error_detail[:500]}")
        text = "\n".join(lines)
        return self._broadcast(text)

    def notify_critical(self, error_text: str) -> list[SendResult]:
        """Notify about a critical error."""
        text = f"CRITICAL ERROR\n\n{error_text[:3000]}"
        return self._broadcast(text)

    def notify_cycle_summary(
        self,
        total_matches: int,
        filtered: int,
        decided: int,
        matched: int,
        placed: int,
        missing: int,
        errors: int,
        dry_run: bool,
        pending: int = 0,
        rejected: int = 0,
        nb_placed: int = 0,
    ) -> list[SendResult]:
        """Notify with a summary of one cycle run."""
        mode = "DRY-RUN" if dry_run else "LIVE"
        lines = [
            f"Итоги цикла ({mode})",
            f"Матчей NB: {total_matches}",
            f"Прошли фильтр: {filtered}",
            f"Решение: {decided}",
            f"Прогнозы NB: {nb_placed}",
            f"Найдено на Куше: {matched}",
            f"Ставки Куш: {placed}",
            f"Не найдено: {missing}",
            f"Ожидают: {pending}",
            f"Отклонено: {rejected}",
            f"Ошибки: {errors}",
        ]
        text = "\n".join(lines)
        return self._broadcast(text)

    def send_test(self) -> list[SendResult]:
        """Send a test message to verify configuration."""
        text = "parser_nb-bet\nТестовое сообщение. Бот работает!"
        return self._broadcast(text)

    def send_document(self, file_path: str, caption: str = "") -> list[SendResult]:
        """Send a document (e.g. Excel file) via VK.

        VK upload flow:
        1. docs.getMessagesUploadServer → upload_url
        2. POST file to upload_url → {file: ...}
        3. docs.save → doc owner_id + id
        4. messages.send with attachment=doc{owner_id}_{id}
        """
        if not self.enabled:
            log.warning("VK not configured (no token or peer_id)")
            return []

        import os

        if not os.path.isfile(file_path):
            log.error("File not found: %s", file_path)
            return [SendResult(ok=False, peer_id=self.peer_id, error=f"File not found: {file_path}")]

        # Step 1: get upload server
        self._wait_rate_limit()
        resp1 = self._api_call("docs.getMessagesUploadServer", {
            "type": "doc",
            "peer_id": self.peer_id,
        })
        self._last_send = time.time()

        upload_url = resp1.get("response", {}).get("upload_url") if isinstance(resp1.get("response"), dict) else None
        if not upload_url:
            err = resp1.get("error", {})
            msg = err.get("error_msg", "no upload_url") if isinstance(err, dict) else str(err)
            log.error("docs.getMessagesUploadServer failed: %s", msg)
            return [SendResult(ok=False, peer_id=self.peer_id, error=f"getUploadServer: {msg}")]

        # Step 2: upload file to VK server (with retry — VK upload servers can be slow)
        filename = os.path.basename(file_path)
        upload_data = None
        last_upload_err = None
        for attempt in range(1, 3):
            try:
                with open(file_path, "rb") as f:
                    upload_resp = requests.post(
                        upload_url,
                        files={"file": (filename, f)},
                        timeout=60,
                    )
                upload_data = upload_resp.json()
                break
            except requests.RequestException as e:
                last_upload_err = e
                log.warning("File upload attempt %d failed: %s", attempt, e)
                if attempt < 2:
                    time.sleep(3)
        if upload_data is None:
            log.error("File upload failed after retries: %s", last_upload_err)
            return [SendResult(ok=False, peer_id=self.peer_id, error=f"upload: {last_upload_err}")]

        file_field = upload_data.get("file")
        if not file_field:
            err_msg = upload_data.get("error", "no file field in upload response")
            log.error("Upload response missing 'file': %s", err_msg)
            return [SendResult(ok=False, peer_id=self.peer_id, error=f"upload: {err_msg}")]

        # Step 3: save document
        self._wait_rate_limit()
        resp3 = self._api_call("docs.save", {
            "file": file_field,
            "title": filename,
        })
        self._last_send = time.time()

        doc_info = None
        resp3_response = resp3.get("response")
        if isinstance(resp3_response, dict):
            doc_info = resp3_response.get("doc")
        elif isinstance(resp3_response, list) and resp3_response:
            doc_info = resp3_response[0]

        if not doc_info or not isinstance(doc_info, dict):
            err = resp3.get("error", {})
            msg = err.get("error_msg", "no doc in response") if isinstance(err, dict) else str(err)
            log.error("docs.save failed: %s", msg)
            return [SendResult(ok=False, peer_id=self.peer_id, error=f"docs.save: {msg}")]

        owner_id = doc_info["owner_id"]
        doc_id = doc_info["id"]
        attachment = f"doc{owner_id}_{doc_id}"

        # Step 4: send message with attachment
        self._wait_rate_limit()
        params: dict[str, Any] = {
            "peer_id": self.peer_id,
            "attachment": attachment,
            "random_id": random.randint(1, 2**31),
        }
        if caption:
            params["message"] = caption
        result = self._api_call("messages.send", params)
        self._last_send = time.time()

        if "response" in result:
            log.info("Document sent to peer %s: %s", self.peer_id, filename)
            return [SendResult(ok=True, peer_id=self.peer_id)]

        error = result.get("error", {})
        error_msg = error.get("error_msg", "unknown error") if isinstance(error, dict) else str(error)
        log.error("messages.send with doc failed for peer %s: %s", self.peer_id, error_msg)
        return [SendResult(ok=False, peer_id=self.peer_id, error=error_msg)]
