"""Kush session manager: requests.Session + CSRF + cookies + login.

Handles the CSRF chain required by kushvsporte.ru:
1. GET page → extract meta csrf-token + PHPSESSID + _csrf cookies
2. Use tokens in subsequent POST requests
"""
from __future__ import annotations

import logging
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup

log = logging.getLogger("parser_nb_bet.kush.session")

_BASE_URL = "https://kushvsporte.ru"

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) "
        "Gecko/20100101 Firefox/144.0"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Sec-GPC": "1",
}

_AJAX_HEADERS = {
    "Accept": "*/*",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": _BASE_URL,
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}


class KushSession:
    """Manages authenticated session with kushvsporte.ru."""

    def __init__(
        self,
        base_url: str = _BASE_URL,
        proxy: Optional[str] = None,
        request_delay: float = 1.8,
        retries: int = 3,
        timeout: int = 30,
    ):
        self._base_url = base_url.rstrip("/")
        self._proxy = proxy
        self._request_delay = request_delay
        self._retries = retries
        self._timeout = timeout

        self._session = requests.Session()
        self._session.headers.update(_DEFAULT_HEADERS)
        if proxy:
            self._session.proxies = {"http": proxy, "https": proxy}

        self._csrf_token: str = ""
        self._logged_in: bool = False
        self._last_request_time: float = 0.0

    @property
    def csrf_token(self) -> str:
        return self._csrf_token

    @property
    def logged_in(self) -> bool:
        return self._logged_in

    def init_csrf(self, day: int = 0) -> str:
        """Fetch initial page and extract CSRF token + cookies.

        Args:
            day: 0 = today, 1 = tomorrow.

        Returns:
            The CSRF token string.

        Raises:
            KushSessionError: If CSRF token cannot be extracted.
        """
        url = f"{self._base_url}/centerbet/football"
        params = {"day": str(day), "_pjax": "#center-bet"}

        resp = self._get(url, params=params)
        soup = BeautifulSoup(resp.text, "lxml")

        meta = soup.find("meta", {"name": "csrf-token"})
        if meta and meta.get("content"):
            self._csrf_token = meta["content"]
            log.debug("CSRF token obtained: %s...", self._csrf_token[:16])
            return self._csrf_token

        raise KushSessionError("Failed to extract CSRF token from page")

    def refresh_csrf(self) -> None:
        """Re-fetch CSRF token silently. Safe to call between requests."""
        try:
            self.init_csrf()
        except Exception:
            log.warning("refresh_csrf failed, will retry on next request")

    def login(self, username: str, password: str) -> bool:
        """Authenticate with kushvsporte.ru.

        Args:
            username: Login username.
            password: Login password.

        Returns:
            True if login was successful.

        Raises:
            KushSessionError: If login fails.
        """
        # Step 1: GET main page to get login form CSRF
        resp = self._get(self._base_url)
        soup = BeautifulSoup(resp.text, "lxml")

        # Extract CSRF from login form hidden field
        form = soup.find("form", {"id": "login-widget-form"})
        if form is None:
            form = soup.find("form", {"action": "/users/login"})

        csrf_input = None
        if form:
            csrf_input = form.find("input", {"name": "_csrf"})

        login_csrf = csrf_input["value"] if csrf_input else self._csrf_token
        if not login_csrf:
            raise KushSessionError("Cannot find CSRF token for login form")

        # Step 2: POST login
        data = {
            "login-form[login]": username,
            "login-form[password]": password,
            "login-form[rememberMe]": "0",
            "_csrf": login_csrf,
        }

        resp = self._post(
            f"{self._base_url}/users/login",
            data=data,
            ajax=False,
        )

        # Check for error in response
        # 302 = redirect after successful login; 200 = page rendered directly
        if resp.status_code in (200, 302):
            text_lower = resp.text.lower()
            if "неправильный логин или пароль" in text_lower:
                raise KushSessionError("Invalid username or password")
            self._logged_in = True
            # Re-fetch CSRF after login
            self.init_csrf()
            log.info("Successfully logged in to kushvsporte.ru")
            return True

        raise KushSessionError(f"Login failed with status {resp.status_code}")

    def get(self, url: str, **kwargs) -> requests.Response:
        """Public GET with rate-limiting and retry."""
        return self._get(url, **kwargs)

    def post(self, url: str, data: dict = None, ajax: bool = True) -> requests.Response:
        """Public POST with rate-limiting, CSRF header, and retry."""
        return self._post(url, data=data, ajax=ajax)

    def _get(self, url: str, **kwargs) -> requests.Response:
        """Internal GET with rate-limiting and retry."""
        self._rate_limit()
        kwargs.setdefault("timeout", self._timeout)

        for attempt in range(self._retries):
            try:
                resp = self._session.get(url, **kwargs)
                resp.raise_for_status()
                return resp
            except requests.RequestException as exc:
                log.warning(
                    "GET %s attempt %d/%d failed: %s",
                    url, attempt + 1, self._retries, exc,
                )
                if attempt < self._retries - 1:
                    time.sleep(1.5)

        raise KushSessionError(f"GET {url} failed after {self._retries} attempts")

    def _post(
        self, url: str, data: dict = None, ajax: bool = True
    ) -> requests.Response:
        """Internal POST with rate-limiting, CSRF header, and retry."""
        self._rate_limit()

        headers = {}
        if ajax:
            headers.update(_AJAX_HEADERS)
        if self._csrf_token:
            headers["X-CSRF-Token"] = self._csrf_token

        for attempt in range(self._retries):
            try:
                resp = self._session.post(
                    url, data=data, headers=headers, timeout=self._timeout,
                    allow_redirects=False,
                )
                # Allow 2xx and 3xx (redirects from login, etc.)
                if resp.status_code < 400:
                    return resp
                resp.raise_for_status()
                return resp
            except requests.RequestException as exc:
                log.warning(
                    "POST %s attempt %d/%d failed: %s",
                    url, attempt + 1, self._retries, exc,
                )
                if attempt < self._retries - 1:
                    time.sleep(1.5)

        raise KushSessionError(f"POST {url} failed after {self._retries} attempts")

    def _rate_limit(self) -> None:
        """Enforce minimum delay between requests."""
        now = time.monotonic()
        elapsed = now - self._last_request_time
        if elapsed < self._request_delay:
            time.sleep(self._request_delay - elapsed)
        self._last_request_time = time.monotonic()


class KushSessionError(Exception):
    """Error from Kush session operations."""
