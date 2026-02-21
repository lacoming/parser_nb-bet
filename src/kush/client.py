"""Kush client: fetch leagues, events, and odds from kushvsporte.ru.

Parses HTML responses from the Kush API to extract event data.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
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
        return _parse_events(resp.text, cid)

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


def _parse_events(html: str, cid: str = "") -> list[KushEvent]:
    """Parse event list HTML into KushEvent objects.

    The HTML returned by /bet/event-list contains match blocks with
    date, time, team names, and event links.
    """
    soup = BeautifulSoup(html, "lxml")
    events: list[KushEvent] = []

    # Each event row has an <a class="d-block"> containing teams and link
    event_links = soup.find_all("a", class_="d-block")

    for link_tag in event_links:
        try:
            event = _parse_single_event(link_tag, soup, cid)
            if event:
                events.append(event)
        except Exception as exc:
            log.debug("Failed to parse event element: %s", exc)

    return events


def _parse_single_event(
    link_tag: Tag, soup: BeautifulSoup, cid: str,
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

    # Try to extract date/time from sibling elements
    start_time = _extract_event_time(link_tag)

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


def _extract_event_time(tag: Tag) -> datetime:
    """Try to extract start time from surrounding HTML elements.

    Looks for date in <div class='medium-text'> and time in
    <div class='d-inline-block d-md-block'> near the event tag.

    Returns UTC datetime, defaults to now if parsing fails.
    """
    parent = tag.parent
    if parent is None:
        return datetime.now(timezone.utc)

    # Look for date text (DD.MM.YYYY format)
    date_str = ""
    time_str = ""

    # Search in parent and siblings
    for div in parent.find_all("div"):
        text = div.get_text(strip=True)
        # Date pattern: DD.MM.YYYY
        date_match = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", text)
        if date_match:
            date_str = date_match.group(0)
            continue
        # Time pattern: HH:MM or HH.MM
        time_match = re.search(r"(\d{2})[.:h](\d{2})", text)
        if time_match and not date_str:
            time_str = f"{time_match.group(1)}:{time_match.group(2)}"

    if date_str and time_str:
        try:
            dt = datetime.strptime(f"{date_str} {time_str}", "%d.%m.%Y %H:%M")
            # Kush times are Moscow time (UTC+3)
            from datetime import timedelta
            return dt.replace(tzinfo=timezone.utc) - timedelta(hours=3)
        except ValueError:
            pass

    if date_str:
        try:
            dt = datetime.strptime(date_str, "%d.%m.%Y")
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    return datetime.now(timezone.utc)


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
            bet_type = bet_div.get_text(strip=True)
            try:
                coef = float(coef_span.get_text(strip=True))
                if bet_type and coef > 0:
                    odds[bet_type] = coef
            except (ValueError, TypeError):
                continue

    return odds


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

    for btn in soup.find_all("button", class_="coefLink"):
        bet_div = btn.find("div", class_="d-sm-none")
        coef_span = btn.find("span")

        if not (bet_div and coef_span):
            continue

        bet_type = bet_div.get_text(strip=True)
        if bet_type != target_bet_type:
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

    return None
