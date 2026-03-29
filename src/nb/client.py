"""NB-Bet JSON API client.

Fetches match data from https://app.nb-bet.com/v1/{sport}/math-analysis/page.
Supports retry with backoff, proxy rotation, and session reuse.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests

from src.config.schema import NbConfig, ProxiesConfig
from src.nb.models import Match

log = logging.getLogger("parser_nb_bet.nb.client")

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:144.0) Gecko/20100101 Firefox/144.0",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ru",
    "Accept-Encoding": "gzip, deflate",
    "Origin": "https://nb-bet.com",
    "Connection": "keep-alive",
    "Referer": "https://nb-bet.com/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
}

_API_BASE = "https://app.nb-bet.com/v1"


class NbClient:
    """Client for NB-Bet JSON API."""

    def __init__(
        self,
        config: NbConfig,
        proxies_config: Optional[ProxiesConfig] = None,
        proxy_list: Optional[list[str]] = None,
    ):
        self._config = config
        self._session = requests.Session()
        self._session.headers.update(_HEADERS)
        self._timeout = config.timeout_seconds
        self._retries = config.retries
        self._retry_delay = config.retry_delay_seconds
        self._proxy_list = proxy_list or []
        self._proxy_idx = 0

    def get_matches(
        self,
        sport: str = "soccer",
        window_days: int = 14,
    ) -> list[Match]:
        """Fetch all matches for a date range (today + window_days).

        Returns a deduplicated list of Match objects.
        """
        matches: list[Match] = []
        seen_keys: set[str] = set()
        now = datetime.now(timezone.utc)

        for day_offset in range(window_days):
            target_date = now + timedelta(days=day_offset)
            # Timestamp = end of the target day in ms (legacy format)
            ts_ms = _date_to_timestamp_ms(target_date)
            page_matches = self._fetch_page(sport, ts_ms)
            for m in page_matches:
                if m.match_key not in seen_keys:
                    seen_keys.add(m.match_key)
                    matches.append(m)
            # Rate-limit between pages
            if day_offset < window_days - 1:
                time.sleep(1.5)

        log.info("NB-Bet: fetched %d unique %s matches (%d days)", len(matches), sport, window_days)
        return matches

    def get_matches_for_date(
        self,
        sport: str,
        date: datetime,
    ) -> list[Match]:
        """Fetch matches for a specific date."""
        ts_ms = _date_to_timestamp_ms(date)
        return self._fetch_page(sport, ts_ms)

    def _fetch_page(self, sport: str, timestamp_ms: str) -> list[Match]:
        """Fetch a single page of matches."""
        url = f"{_API_BASE}/{sport}/math-analysis/page?timestamp={timestamp_ms}"
        data = self._request_with_retry(url)
        if data is None:
            return []
        return _parse_response(data, sport)

    def _request_with_retry(self, url: str) -> Optional[dict]:
        """GET request with retry + exponential backoff."""
        last_error = None
        for attempt in range(1, self._retries + 1):
            try:
                proxies = self._get_proxy()
                resp = self._session.get(
                    url,
                    timeout=self._timeout,
                    proxies=proxies,
                )
                if resp.status_code == 200:
                    return resp.json()
                log.warning(
                    "NB-Bet: HTTP %d on attempt %d/%d for %s",
                    resp.status_code, attempt, self._retries, url,
                )
            except (requests.RequestException, ValueError) as e:
                last_error = e
                log.warning(
                    "NB-Bet: error on attempt %d/%d: %s",
                    attempt, self._retries, e,
                )
            if attempt < self._retries:
                delay = self._retry_delay * attempt
                time.sleep(delay)

        log.error("NB-Bet: all %d retries exhausted. Last error: %s", self._retries, last_error)
        return None

    def _get_proxy(self) -> Optional[dict[str, str]]:
        """Get next proxy from rotation list."""
        if not self._proxy_list:
            return None
        proxy = self._proxy_list[self._proxy_idx % len(self._proxy_list)]
        self._proxy_idx += 1
        return {"http": proxy, "https": proxy}


def _date_to_timestamp_ms(dt: datetime) -> str:
    """Convert date to end-of-day unix timestamp in ms (legacy format)."""
    # Set to 23:59:59 of that day
    eod = dt.replace(hour=23, minute=59, second=59, microsecond=0)
    if eod.tzinfo is None:
        eod = eod.replace(tzinfo=timezone.utc)
    return f"{int(eod.timestamp())}999"


def _parse_response(data: dict, sport: str) -> list[Match]:
    """Parse NB-Bet JSON response into Match objects."""
    matches: list[Match] = []
    try:
        leagues = data.get("data", {}).get("leagues", [])
    except (AttributeError, TypeError):
        log.warning("NB-Bet: unexpected response structure")
        return []

    for league_data in leagues:
        try:
            country = league_data.get("1", "")
            league_name_raw = league_data.get("3", "")
            league = f"{country}. {league_name_raw}" if country else league_name_raw
            match_list = league_data.get("4", [])
        except (AttributeError, TypeError):
            continue

        for raw in match_list:
            try:
                match = _parse_match(raw, league, sport)
                if match is not None:
                    matches.append(match)
            except Exception as e:
                log.debug("NB-Bet: skip match parse error: %s", e)
                continue

    return matches


def _parse_match(raw: dict, league: str, sport: str) -> Optional[Match]:
    """Parse a single match dict from NB-Bet API."""
    slug = raw.get("3", "")
    timestamp_ms = raw.get("4")
    if not timestamp_ms:
        return None

    # Convert timestamp (ms) to MSK datetime.
    # NB-Bet API returns real UTC timestamps.  We store everything as MSK
    # (tagged with UTC tzinfo for tz-aware arithmetic) so that NB and Kush
    # times are directly comparable without conversion.
    ts_sec = int(str(timestamp_ms)[:-3])
    _MSK_OFFSET = timedelta(hours=3)
    start_time = datetime.fromtimestamp(ts_sec, tz=timezone.utc) + _MSK_OFFSET
    # Re-tag as UTC (we store MSK value in the UTC slot, same as Kush)
    start_time = start_time.replace(tzinfo=timezone.utc)

    home = raw.get("7", "")
    away = raw.get("15", "")
    if not home or not away:
        return None

    # Parse 1x2 odds
    # '5' = end odds, '6' = start odds
    # Each has: '1' = kf1 (home), '3' = kfX (draw), '2' = kf2 (away)
    start_odds = raw.get("6") or {}
    end_odds = raw.get("5") or {}

    odds_1_start = _safe_float(start_odds.get("1"))
    odds_x_start = _safe_float(start_odds.get("3"))
    odds_2_start = _safe_float(start_odds.get("2"))
    odds_1_end = _safe_float(end_odds.get("1"))
    odds_x_end = _safe_float(end_odds.get("3"))
    odds_2_end = _safe_float(end_odds.get("2"))

    # Predicted exact score (fields '46' and '47')
    score_home = _safe_int(raw.get("46"))
    score_away = _safe_int(raw.get("47"))

    # Skip matches without end odds (not useful for decision)
    if odds_1_end is None or odds_2_end is None:
        return None

    match_key = Match.make_key(league, home, away, start_time)

    return Match(
        match_key=match_key,
        league=league,
        team_home=home,
        team_away=away,
        start_time_utc=start_time,
        nb_slug=slug,
        sport=sport,
        odds_1_start=odds_1_start,
        odds_x_start=odds_x_start,
        odds_2_start=odds_2_start,
        odds_1_end=odds_1_end,
        odds_x_end=odds_x_end,
        odds_2_end=odds_2_end,
        score_home=score_home,
        score_away=score_away,
    )


def _safe_float(val) -> Optional[float]:
    """Safely convert value to float."""
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_int(val) -> Optional[int]:
    """Safely convert value to int."""
    if val is None or val == "":
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None
