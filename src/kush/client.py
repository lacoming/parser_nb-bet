"""Kush client: fetch leagues, events, and odds from kushvsporte.ru.

Parses HTML responses from the Kush API to extract event data.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from bs4 import BeautifulSoup, Tag

from src.kush.models import KushEvent
from src.kush.session import KushSession

log = logging.getLogger("parser_nb_bet.kush.client")


class KushClient:
    """Client for interacting with kushvsporte.ru event data."""

    def __init__(self, session: KushSession):
        self._session = session

    def get_leagues(self, day: int = 0) -> dict[str, str]:
        """Fetch available football leagues.

        Args:
            day: 0 = today, 1 = tomorrow.

        Returns:
            Dict mapping league_id (cid) → league_name.
        """
        url = f"{self._session._base_url}/centerbet/football"
        params = {"day": str(day), "_pjax": "#center-bet"}

        resp = self._session.get(url, params=params)
        return _parse_leagues(resp.text)

    def get_events(self, cid: str, day: int = 0) -> list[KushEvent]:
        """Fetch events for a specific league (cid).

        Args:
            cid: League/country ID from get_leagues().
            day: 0 = today, 1 = tomorrow.

        Returns:
            List of KushEvent objects.
        """
        url = f"{self._session._base_url}/bet/event-list"
        data = {"cid": str(cid), "day": str(day), "status": ""}

        resp = self._session.post(url, data=data)
        return _parse_events(resp.text, cid, day=day)

    def get_all_events(self, day: int = 0) -> list[KushEvent]:
        """Fetch events from all available leagues.

        Args:
            day: 0 = today, 1 = tomorrow.

        Returns:
            Combined list of KushEvent from all leagues.
        """
        leagues = self.get_leagues(day)
        all_events: list[KushEvent] = []

        for cid, league_name in leagues.items():
            try:
                events = self.get_events(cid, day)
                for ev in events:
                    if not ev.league:
                        ev.league = league_name
                all_events.extend(events)
                log.debug(
                    "League %s (%s): %d events", cid, league_name, len(events),
                )
            except Exception as exc:
                log.warning("Failed to get events for league %s: %s", cid, exc)

        log.info("Total Kush events fetched: %d (day=%d)", len(all_events), day)
        return all_events

    def get_odds(self, event_id: str) -> dict[str, float]:
        """Fetch odds (coefficients) for an event.

        Args:
            event_id: The event ID (eid).

        Returns:
            Dict mapping bet_type → coefficient (e.g. {"П1": 2.10, "X": 3.20}).
        """
        url = f"{self._session._base_url}/bet/cf-list"
        data = {"eid": str(event_id)}

        resp = self._session.post(url, data=data)
        return _parse_odds(resp.text)

    def find_odds_entry(
        self,
        event_id: str,
        bet_type: str,
        min_kf: float = 0.0,
        max_kf: float = 999.0,
    ) -> Optional[OddsEntry]:
        """Find a specific odds entry matching bet type and coefficient range.

        Args:
            event_id: The event ID.
            bet_type: Bet type to look for (e.g. "П1", "П2", "X", "1X").
            min_kf: Minimum coefficient.
            max_kf: Maximum coefficient.

        Returns:
            OddsEntry if found, None otherwise.
        """
        url = f"{self._session._base_url}/bet/cf-list"
        data = {"eid": str(event_id)}

        resp = self._session.post(url, data=data)
        return _find_odds_entry(resp.text, bet_type, min_kf, max_kf)


class OddsEntry:
    """A single odds entry with its coupon URL and coefficient."""

    __slots__ = ("bet_type", "coefficient", "cfid", "eid")

    def __init__(self, bet_type: str, coefficient: float, cfid: str, eid: str):
        self.bet_type = bet_type
        self.coefficient = coefficient
        self.cfid = cfid
        self.eid = eid

    def __repr__(self) -> str:
        return f"OddsEntry({self.bet_type!r}, kf={self.coefficient}, cfid={self.cfid})"


# ---------------------------------------------------------------------------
# HTML parsing helpers
# ---------------------------------------------------------------------------

def _parse_leagues(html: str) -> dict[str, str]:
    """Parse league list from centerbet page HTML.

    Returns:
        Dict mapping league_id → league_name.
    """
    soup = BeautifulSoup(html, "lxml")
    leagues: dict[str, str] = {}

    for link in soup.find_all("a", class_="centerEventLink"):
        cid = link.get("data-cid", "")
        if not cid:
            continue
        span = link.find("span", class_="align-super")
        name = span.get_text(strip=True) if span else ""
        if name:
            leagues[str(cid)] = name

    return leagues


def _parse_events(html: str, cid: str = "", day: int = 0) -> list[KushEvent]:
    """Parse event list HTML into KushEvent objects.

    The HTML returned by /bet/event-list contains match blocks with
    date, time, team names, and event links.

    Args:
        day: 0 = today, 1 = tomorrow. Used to resolve dates.
    """
    soup = BeautifulSoup(html, "lxml")
    events: list[KushEvent] = []

    # Each event row has an <a class="d-block"> containing teams and link
    event_links = soup.find_all("a", class_="d-block")

    for link_tag in event_links:
        try:
            event = _parse_single_event(link_tag, soup, cid, day)
            if event:
                events.append(event)
        except Exception as exc:
            log.debug("Failed to parse event element: %s", exc)

    return events


def _parse_single_event(
    link_tag: Tag, soup: BeautifulSoup, cid: str, day: int = 0,
) -> Optional[KushEvent]:
    """Parse a single event from an <a class='d-block'> tag."""
    href = link_tag.get("href", "")
    if not href:
        return None

    # Extract event ID from href (e.g. /event/12345-team1-team2 → 12345)
    event_id = _extract_event_id(href)
    if not event_id:
        return None

    # Extract team names from <div class='medium-text'> inside the link
    team_divs = link_tag.find_all("div", class_="medium-text")
    if len(team_divs) < 2:
        return None

    team_home = team_divs[0].get_text(strip=True)
    team_away = team_divs[1].get_text(strip=True)

    if not team_home or not team_away:
        return None

    # Try to extract date/time from link title and surrounding elements
    start_time = _extract_event_time(link_tag, day)

    return KushEvent(
        event_id=event_id,
        league="",  # filled by caller
        team_home=team_home,
        team_away=team_away,
        start_time_utc=start_time,
        url=href,
    )


def _extract_event_id(href: str) -> str:
    """Extract event ID from href like '/event/12345-xxx'."""
    # Pattern: /event/{id}-... or just numeric ID
    m = re.search(r"/event/(\d+)", href)
    if m:
        return m.group(1)
    # Fallback: try to find any number
    m = re.search(r"(\d+)", href)
    return m.group(1) if m else ""


def _extract_event_time(tag: Tag, day: int = 0) -> datetime:
    """Extract start time from the event's link tag and surrounding HTML.

    Strategy:
    1. Parse date+time from link's title attribute (e.g. "22 Февраля 17:00")
    2. Parse time from sibling column in the event row (e.g. "17:00")
       and combine with the date derived from the `day` parameter.
    3. Fallback: datetime.now(UTC)

    All Kush times are Moscow time (UTC+3).

    Args:
        tag: The <a class="d-block"> link tag for the event.
        day: 0 = today, 1 = tomorrow (used for date resolution).
    """
    MSK_OFFSET = timedelta(hours=3)

    # --- Strategy 1: parse from title attribute ---
    title = tag.get("title", "")
    if title:
        dt = _parse_title_datetime(title)
        if dt is not None:
            # dt is MSK (naive), convert to UTC
            return dt.replace(tzinfo=timezone.utc) - MSK_OFFSET

    # --- Strategy 2: find time in sibling column, date from day param ---
    time_str = _find_time_in_row(tag)
    if time_str:
        # Build date from day parameter (MSK today/tomorrow)
        now_msk = datetime.now(timezone.utc) + MSK_OFFSET
        target_date = now_msk.date() + timedelta(days=day)
        try:
            hh, mm = time_str.split(":")
            dt = datetime(
                target_date.year, target_date.month, target_date.day,
                int(hh), int(mm),
            )
            return dt.replace(tzinfo=timezone.utc) - MSK_OFFSET
        except (ValueError, TypeError):
            pass

    return datetime.now(timezone.utc)


# Russian month names for title parsing
_RU_MONTHS = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
    "мая": 5, "июня": 6, "июля": 7, "августа": 8,
    "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}


def _parse_title_datetime(title: str) -> Optional[datetime]:
    """Parse date and time from link title like '... 22 Февраля 17:00'.

    Returns a naive datetime (MSK) or None.
    """
    # Pattern: DD MonthName HH:MM (anywhere in the title)
    m = re.search(
        r"(\d{1,2})\s+([а-яА-ЯёЁ]+)\s+(\d{1,2}):(\d{2})",
        title,
    )
    if not m:
        return None

    day_num = int(m.group(1))
    month_name = m.group(2).lower()
    hour = int(m.group(3))
    minute = int(m.group(4))

    month = _RU_MONTHS.get(month_name)
    if month is None:
        return None

    # Determine year: use current year, but if the date is in the past by
    # more than 30 days, assume next year.
    now_msk = datetime.now(timezone.utc) + timedelta(hours=3)
    year = now_msk.year
    try:
        dt = datetime(year, month, day_num, hour, minute)
    except ValueError:
        return None

    if (now_msk.replace(tzinfo=None) - dt).days > 30:
        dt = dt.replace(year=year + 1)

    return dt


def _find_time_in_row(tag: Tag) -> Optional[str]:
    """Find time string (HH:MM) in the event row surrounding the link tag.

    The Kush HTML structure is:
        <div class="row ... event-centerbet">   ← event row
            <div class="col-6 col-md-1 ...">    ← time column
                <div class="medium-text ...">17:00</div>
                <div ...>Суббота</div>
            </div>
            <div class="col-sm-4 ...">           ← teams column
                <a class="d-block" ...>          ← this is `tag`
            </div>
        </div>
    """
    # Navigate up to the event row
    row = tag.parent
    if row is None:
        return None
    # tag.parent is the teams column; go up to the row
    row = row.parent
    if row is None:
        return None

    # Search all divs in the row for a time pattern
    for div in row.find_all("div"):
        text = div.get_text(strip=True)
        tm = re.match(r"^(\d{1,2}):(\d{2})$", text)
        if tm:
            return f"{int(tm.group(1)):02d}:{tm.group(2)}"

    return None


def _parse_odds(html: str) -> dict[str, float]:
    """Parse odds from /bet/cf-list HTML response.

    Returns:
        Dict mapping bet_type → coefficient.
    """
    soup = BeautifulSoup(html, "lxml")
    odds: dict[str, float] = {}

    for btn in soup.find_all("button", class_="coefLink"):
        bet_div = btn.find("div", class_="d-sm-none")
        coef_span = btn.find("span")

        if bet_div and coef_span:
            bet_type = _normalize_bet_type(bet_div.get_text(strip=True))
            try:
                coef = float(coef_span.get_text(strip=True))
                if bet_type and coef > 0:
                    odds[bet_type] = coef
            except (ValueError, TypeError):
                continue

    return odds


def _normalize_bet_type(s: str) -> str:
    """Normalize bet type string: Cyrillic Х ↔ Latin X, strip whitespace."""
    # Replace Cyrillic Х/х with Latin X/x for uniform comparison
    return s.strip().replace("\u0425", "X").replace("\u0445", "x")


def _find_odds_entry(
    html: str,
    target_bet_type: str,
    min_kf: float,
    max_kf: float,
) -> Optional[OddsEntry]:
    """Find a specific odds entry in cf-list HTML.

    Args:
        html: The HTML response from /bet/cf-list.
        target_bet_type: Bet type to search for.
        min_kf: Minimum coefficient threshold.
        max_kf: Maximum coefficient threshold.

    Returns:
        OddsEntry if found, None otherwise.
    """
    soup = BeautifulSoup(html, "lxml")
    target_norm = _normalize_bet_type(target_bet_type)

    available_types: list[str] = []
    for btn in soup.find_all("button", class_="coefLink"):
        bet_div = btn.find("div", class_="d-sm-none")
        coef_span = btn.find("span")

        if not (bet_div and coef_span):
            continue

        bet_type = bet_div.get_text(strip=True)
        available_types.append(bet_type)
        if _normalize_bet_type(bet_type) != target_norm:
            continue

        try:
            coef = float(coef_span.get_text(strip=True))
        except (ValueError, TypeError):
            continue

        if min_kf <= coef <= max_kf:
            # Extract cfid from button URL attribute
            cfid = btn.get("url", "") or btn.get("data-cfid", "")
            # Try to extract eid and cfid from URL params
            eid = ""
            if cfid and "eid=" in cfid:
                eid_match = re.search(r"eid=(\d+)", cfid)
                cfid_match = re.search(r"cfid=(\d+)", cfid)
                eid = eid_match.group(1) if eid_match else ""
                cfid = cfid_match.group(1) if cfid_match else cfid

            return OddsEntry(
                bet_type=bet_type,
                coefficient=coef,
                cfid=cfid,
                eid=eid,
            )

    if available_types:
        log.debug(
            "Odds entry '%s' not found. Available: %s",
            target_bet_type, ", ".join(available_types),
        )
    else:
        log.warning("cf-list returned 0 odds entries (empty response or parse error)")
    return None
