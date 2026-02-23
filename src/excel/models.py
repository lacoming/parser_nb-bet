"""Excel row data models."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class ExcelRow:
    """One row of output Excel data.

    Fields map to legacy columns:
    A=date, B=time, C=league, D=home, E=away,
    F-I=scores, J-O=odds(start/end), P-S=exact score,
    T-V=match prop, W-Y=player prop, Z=link,
    AA=bet_type, AB=kf_kush, AC=ratio
    """

    # Basic match info
    date: str = ""  # DD.MM.YYYY
    time: str = ""  # HH:MM
    league: str = ""
    team_home: str = ""
    team_away: str = ""

    # Scores
    score_home: str = ""
    score_away: str = ""
    score_total: str = ""
    score_diff: str = ""

    # Odds (1X2) — start / end
    odds_1_start: str = ""
    odds_1_end: str = ""
    odds_x_start: str = ""
    odds_x_end: str = ""
    odds_2_start: str = ""
    odds_2_end: str = ""

    # Exact score props
    exact_score_home: str = ""
    exact_score_away: str = ""
    exact_score_kf_start: str = ""
    exact_score_kf_end: str = ""

    # Match prop (МП)
    mp_name: str = ""
    mp_kf_start: str = ""
    mp_kf_end: str = ""

    # Player prop (ПП)
    pp_name: str = ""
    pp_kf_start: str = ""
    pp_kf_end: str = ""

    # Link / slug
    link: str = ""

    # Bet result (added by our system)
    bet_type: str = ""  # "П1", "П2", "X", "1X"
    kf_kush: str = ""
    ratio: str = ""

    def as_list(self) -> list[str]:
        """Return row values in column order."""
        return [
            self.date,
            self.time,
            self.league,
            self.team_home,
            self.team_away,
            self.score_home,
            self.score_away,
            self.score_total,
            self.score_diff,
            self.odds_1_start,
            self.odds_1_end,
            self.odds_x_start,
            self.odds_x_end,
            self.odds_2_start,
            self.odds_2_end,
            self.exact_score_home,
            self.exact_score_away,
            self.exact_score_kf_start,
            self.exact_score_kf_end,
            self.mp_name,
            self.mp_kf_start,
            self.mp_kf_end,
            self.pp_name,
            self.pp_kf_start,
            self.pp_kf_end,
            self.link,
            self.bet_type,
            self.kf_kush,
            self.ratio,
        ]


@dataclass
class MissingRow:
    """Row for matches not found on Kush (written to 'НЕ НАЙДЕНО' sheet)."""

    date: str = ""  # DD.MM.YYYY
    time: str = ""  # HH:MM
    league: str = ""
    team_home: str = ""
    team_away: str = ""
    bet_type: str = ""
    odds_1_start: str = ""
    odds_x_start: str = ""
    odds_2_start: str = ""
    kf_nb: str = ""
    min_kf_kush: str = ""
    link: str = ""

    def as_list(self) -> list[str]:
        return [
            self.date, self.time, self.league,
            self.team_home, self.team_away, self.bet_type,
            self.odds_1_start, self.odds_x_start, self.odds_2_start,
            self.kf_nb, self.min_kf_kush, self.link,
        ]

    @staticmethod
    def headers() -> list[str]:
        return [
            "Дата", "Время", "Лига",
            "Дома", "Гости", "Ставка",
            "Kf1 старт", "KfX старт", "Kf2 старт",
            "KfNB", "Мин KfKush", "Ссылка",
        ]

    @staticmethod
    def widths() -> list[float]:
        return [12, 8, 25, 20, 20, 8, 10, 10, 10, 10, 12, 30]
