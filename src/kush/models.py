"""Kush data models."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class KushEvent:
    """A match/event from kushvsporte.ru."""

    event_id: str
    league: str
    team_home: str
    team_away: str
    start_time_utc: datetime
    odds: dict[str, float] = field(default_factory=dict)
    url: str = ""


@dataclass
class MatchResult:
    """Result of matching an NB-Bet match to a Kush event."""

    nb_match_key: str
    kush_event: Optional[KushEvent]
    confidence: float  # 0.0 - 1.0
    name_score: float
    time_score: float
    swapped: bool = False  # True if home/away were swapped for matching
