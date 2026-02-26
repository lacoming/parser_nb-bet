"""NB-Bet JWT session manager.

Handles login via POST /v1/login and stores JWT token for subsequent requests.
Follows the same patterns as KushSession (retry, rate-limit, session reuse).
"""
from __future__ import annotations

import logging
import time
from typing import Optional

import requests

log = logging.getLogger("parser_nb_bet.nb.session")

_API_BASE = "https://app.nb-bet.com/v1"

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) "
        "Gecko/20100101 Firefox/144.0"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ru",
    "Accept-Encoding": "gzip, deflate",
    "Origin": "https://nb-bet.com",
    "Connection": "keep-alive",
    "Referer": "https://nb-bet.com/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "timezone-offset": "-180",
}


class NbSession:
    """Manages authenticated session with nb-bet.com (JWT)."""

    def __init__(
        self,
        api_base: str = _API_BASE,
        proxy: Optional[str] = None,
        timeout: int = 30,
        retries: int = 3,
        retry_delay: float = 5.0,
        request_delay: float = 1.5,
    ):
        self._api_base = api_base.rstrip("/")
        self._timeout = timeout
        self._retries = retries
        self._retry_delay = retry_delay
        self._request_delay = request_delay

        self._session = requests.Session()
        self._session.headers.update(_DEFAULT_HEADERS)
        if proxy:
            self._session.proxies = {"http": proxy, "https": proxy}

        self._token: str = ""
        self._logged_in: bool = False
        self._last_request_time: float = 0.0

    @property
    def logged_in(self) -> bool:
        return self._logged_in

    @property
    def token(self) -> str:
        return self._token

    def login(self, email: str, password: str) -> bool:
        """Authenticate with NB-Bet and store JWT token.

        Args:
            email: NB-Bet account email.
            password: NB-Bet account password.

        Returns:
            True if login was successful.

        Raises:
            NbSessionError: If login fails.
        """
        url = f"{self._api_base}/login"
        payload = {"userEmail": email, "userPassword": password}

        try:
            self._rate_limit()
            resp = self._session.post(url, json=payload, timeout=self._timeout)
        except requests.RequestException as exc:
            raise NbSessionError(f"Login request failed: {exc}") from exc

        if resp.status_code != 200:
            raise NbSessionError(f"Login HTTP {resp.status_code}")

        try:
            data = resp.json()
        except ValueError as exc:
            raise NbSessionError(f"Login response not JSON: {exc}") from exc

        inner = data.get("data", {})
        if inner.get("status") != "success":
            raise NbSessionError(f"Login failed: {inner}")

        token = inner.get("token", "")
        if not token:
            raise NbSessionError("Login response missing token")

        self._token = token
        self._session.headers["authorization"] = token
        self._logged_in = True
        name = inner.get("name", "")
        log.info("NB-Bet logged in as %s", name)
        return True

    def post_json(self, path: str, data: dict) -> requests.Response:
        """POST JSON to NB-Bet API with retry and rate-limiting.

        Args:
            path: API path (e.g. /soccer/events/tips/slug/1).
            data: JSON body.

        Returns:
            Response object.

        Raises:
            NbSessionError: If all retries exhausted.
        """
        url = f"{self._api_base}{path}"
        last_error: Optional[Exception] = None

        for attempt in range(1, self._retries + 1):
            self._rate_limit()
            try:
                resp = self._session.post(
                    url, json=data, timeout=self._timeout,
                )
                if resp.status_code == 200:
                    return resp
                log.warning(
                    "NB POST %s: HTTP %d (attempt %d/%d)",
                    path, resp.status_code, attempt, self._retries,
                )
                last_error = NbSessionError(f"HTTP {resp.status_code}")
            except requests.RequestException as exc:
                last_error = exc
                log.warning(
                    "NB POST %s: error (attempt %d/%d): %s",
                    path, attempt, self._retries, exc,
                )

            if attempt < self._retries:
                time.sleep(self._retry_delay * attempt)

        raise NbSessionError(
            f"POST {path} failed after {self._retries} attempts: {last_error}"
        )

    def _rate_limit(self) -> None:
        """Enforce minimum delay between requests."""
        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < self._request_delay:
            time.sleep(self._request_delay - elapsed)
        self._last_request_time = time.monotonic()


class NbSessionError(Exception):
    """Error from NB-Bet session operations."""
