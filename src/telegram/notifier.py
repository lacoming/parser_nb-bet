"""Telegram Bot API notifier.

Sends notifications about placed bets, missing events, critical errors,
and cycle summaries. Supports MarkdownV2 with fallback to plain text.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import requests

log = logging.getLogger("parser_nb_bet.telegram.notifier")

# Telegram Bot API base URL
_API = "https://api.telegram.org/bot{token}/{method}"

# Characters that must be escaped in MarkdownV2
_MD2_ESCAPE = r"_*[]()~`>#+-=|{}.!"


def escape_md2(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    result = []
    for ch in text:
        if ch in _MD2_ESCAPE:
            result.append("\\")
        result.append(ch)
    return "".join(result)


@dataclass
class SendResult:
    """Result of a Telegram API call."""
    ok: bool
    chat_id: int
    error: str = ""


class TelegramNotifier:
    """Sends Telegram notifications via Bot API.

    Args:
        token: Bot API token.
        chat_ids: List of chat IDs to send to.
        rate_limit: Minimum seconds between messages (default 1.0).
        timeout: HTTP timeout in seconds (default 15).
    """

    def __init__(
        self,
        token: str,
        chat_ids: list[int],
        rate_limit: float = 1.0,
        timeout: int = 15,
    ) -> None:
        self.token = token
        self.chat_ids = list(chat_ids)
        self.rate_limit = rate_limit
        self.timeout = timeout
        self._last_send: float = 0.0

    @property
    def enabled(self) -> bool:
        return bool(self.token and self.chat_ids)

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
        data: dict[str, Any],
        files: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make a Telegram Bot API call."""
        url = _API.format(token=self.token, method=method)
        try:
            resp = requests.post(url, data=data, files=files, timeout=self.timeout)
            return resp.json()
        except requests.RequestException as e:
            return {"ok": False, "description": str(e)}

    def _send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: str | None = "MarkdownV2",
    ) -> SendResult:
        """Send a text message to one chat."""
        self._wait_rate_limit()
        data: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if parse_mode:
            data["parse_mode"] = parse_mode

        result = self._api_call("sendMessage", data)
        self._last_send = time.time()

        if result.get("ok"):
            return SendResult(ok=True, chat_id=chat_id)

        # Fallback: if MarkdownV2 fails, retry as plain text
        if parse_mode == "MarkdownV2":
            log.warning(
                "MarkdownV2 failed for chat %s (%s), retrying plain text",
                chat_id,
                result.get("description", ""),
            )
            return self._send_message(chat_id, text, parse_mode=None)

        error = result.get("description", "unknown error")
        log.error("Telegram send failed for chat %s: %s", chat_id, error)
        return SendResult(ok=False, chat_id=chat_id, error=error)

    def _broadcast(self, text: str, parse_mode: str | None = "MarkdownV2") -> list[SendResult]:
        """Send a message to all configured chats."""
        if not self.enabled:
            log.warning("Telegram not configured (no token or chat_ids)")
            return []

        results = []
        for cid in self.chat_ids:
            res = self._send_message(cid, text, parse_mode)
            results.append(res)
            if res.ok:
                log.debug("Sent to chat %s", cid)
            else:
                log.error("Failed to send to chat %s: %s", cid, res.error)
        return results

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
        esc = escape_md2
        status = "Kush\\+" if not dry_run else "Kush\\+ \\(dry\\)"
        lines = [
            f"*{status}*",
            f"{esc(match_time)} / {esc(match_date)}",
            f"{esc(league)}",
            f"{esc(team_home)} \\- {esc(team_away)}",
            f"{esc(odds_1)} \\- {esc(odds_x)} \\- {esc(odds_2)}",
            f"{esc(bet_type)}, КфКуша: `{kf_kush:.2f}`",
            f"Ratio: `{ratio:.2f}`",
        ]
        if was_pending:
            lines.append("_ранее ожидала_")
        if link:
            lines.append(esc(link))
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
        esc = escape_md2
        lines = [
            "*kush\\-off*",
            f"{esc(match_time)} / {esc(match_date)}",
            f"{esc(league)}",
            f"{esc(team_home)} \\- {esc(team_away)}",
            f"{esc(odds_1)} \\- {esc(odds_x)} \\- {esc(odds_2)}",
        ]
        if bet_type:
            lines.append(f"Ставка: {esc(bet_type)}")
        if link:
            lines.append(esc(link))
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
        esc = escape_md2
        lines = [
            "*ожидает*",
            f"{esc(match_time)} / {esc(match_date)}",
            f"{esc(league)}",
            f"{esc(team_home)} \\- {esc(team_away)}",
            f"{esc(odds_1)} \\- {esc(odds_x)} \\- {esc(odds_2)}",
        ]
        if bet_type:
            lines.append(f"Ставка: {esc(bet_type)}")
        if link:
            lines.append(esc(link))
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
        esc = escape_md2
        lines = [
            "*ratio\\-off*",
            f"{esc(match_time)} / {esc(match_date)}",
            f"{esc(league)}",
            f"{esc(team_home)} \\- {esc(team_away)}",
            f"{esc(odds_1)} \\- {esc(odds_x)} \\- {esc(odds_2)}",
            f"{esc(bet_type)}, КфКуша: `{kf_kush:.2f}`",
            f"Ratio: `{ratio:.2f}` \\(порог `{threshold:.2f}`\\)",
        ]
        if link:
            lines.append(esc(link))
        text = "\n".join(lines)
        return self._broadcast(text)

    def notify_critical(self, error_text: str) -> list[SendResult]:
        """Notify about a critical error."""
        esc = escape_md2
        text = f"*CRITICAL ERROR*\n\n`{esc(error_text[:3000])}`"
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
        mode = "DRY\\-RUN" if dry_run else "LIVE"
        lines = [
            f"*Итоги цикла \\({mode}\\)*",
            f"Матчей NB: `{total_matches}`",
            f"Прошли фильтр: `{filtered}`",
            f"Решение: `{decided}`",
            f"Прогнозы NB: `{nb_placed}`",
            f"Найдено на Куше: `{matched}`",
            f"Ставки Куш: `{placed}`",
            f"Не найдено: `{missing}`",
            f"Ожидают: `{pending}`",
            f"Отклонено: `{rejected}`",
            f"Ошибки: `{errors}`",
        ]
        text = "\n".join(lines)
        return self._broadcast(text)

    def send_test(self) -> list[SendResult]:
        """Send a test message to verify configuration."""
        esc = escape_md2
        text = f"*parser\\_nb\\-bet*\n{esc('Тестовое сообщение. Бот работает!')}"
        return self._broadcast(text)

    def send_document(self, file_path: str, caption: str = "") -> list[SendResult]:
        """Send a document (e.g. Excel file) to all chats."""
        if not self.enabled:
            log.warning("Telegram not configured (no token or chat_ids)")
            return []

        results = []
        for cid in self.chat_ids:
            self._wait_rate_limit()
            try:
                with open(file_path, "rb") as f:
                    data: dict[str, Any] = {"chat_id": cid}
                    if caption:
                        data["caption"] = caption
                    result = self._api_call("sendDocument", data, files={"document": f})
                    self._last_send = time.time()

                    if result.get("ok"):
                        results.append(SendResult(ok=True, chat_id=cid))
                        log.debug("Document sent to chat %s", cid)
                    else:
                        error = result.get("description", "unknown error")
                        results.append(SendResult(ok=False, chat_id=cid, error=error))
                        log.error("Document send failed for chat %s: %s", cid, error)
            except OSError as e:
                results.append(SendResult(ok=False, chat_id=cid, error=str(e)))
                log.error("Failed to open file %s: %s", file_path, e)

        return results
