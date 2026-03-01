"""Excel row data models — unified 18-column format."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class UnifiedRow:
    """Single unified row for Excel output (18 columns per customer template).

    Scenarios:
      - Bet placed on Kush:  kush_placed="+", kush_reason="",
                              kf_kush=value, kush_date/time=timestamp
      - Missing on Kush:     kush_placed="-", kush_reason="отсутствие"
      - Ratio rejected:      kush_placed="-", kush_reason="ratio", kf_kush=value
      - Far-future (pending): kush_placed="-", kush_reason="ожидание"
    """

    date: str = ""              # 1  Дата (DD.MM.YYYY)
    time: str = ""              # 2  Время (HH:MM)
    league: str = ""            # 3  Лига
    team_home: str = ""         # 4  Дома
    team_away: str = ""         # 5  Гости
    bet_type: str = ""          # 6  Ставка (1, 2, X, 1X)
    kf1_start: str = ""         # 7  Kf1 старт
    kfx_start: str = ""         # 8  KfX старт
    kf2_start: str = ""         # 9  Kf2 старт
    kf_nb: str = ""             # 10 KfNB
    min_kf_kush: str = ""       # 11 Мин KfKush
    nb_placed: str = ""         # 12 Ставка на НБ (+ / -)
    kush_placed: str = ""       # 13 Ставка на Куш (+ / -)
    kush_reason: str = ""       # 14 основания для - на куше
    kf_kush: str = ""           # 15 кф куша
    kush_date: str = ""         # 16 Дата ставки Куш (DD.MM.YYYY)
    kush_time: str = ""         # 17 Время ставки Куш (HH:MM)
    link: str = ""              # 18 Ссылка

    def as_list(self) -> list[str]:
        """Return row values in column order (18 items)."""
        return [
            self.date,
            self.time,
            self.league,
            self.team_home,
            self.team_away,
            self.bet_type,
            self.kf1_start,
            self.kfx_start,
            self.kf2_start,
            self.kf_nb,
            self.min_kf_kush,
            self.nb_placed,
            self.kush_placed,
            self.kush_reason,
            self.kf_kush,
            self.kush_date,
            self.kush_time,
            self.link,
        ]
