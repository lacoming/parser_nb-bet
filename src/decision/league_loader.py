"""League settings loader from leagues.xlsx (openpyxl).

Expected Excel format:
- Column A: Sport (football/hockey) — marks start of a new strategy block
- Column B: League name (one per row, multiple rows per strategy)
- Column C: MinKf (minimum coefficient)
- Column D: MaxKf (maximum coefficient)
- Column E: Bet type on NB (e.g. "МП", "1X")
- Column F: Bet type on Kush (e.g. "МП" — same or different for inverted)
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from src.decision.models import LeagueSetting

log = logging.getLogger("parser_nb_bet.decision.league_loader")


def load_league_settings(path: str = "leagues.xlsx") -> list[LeagueSetting]:
    """Load strategy settings from leagues.xlsx."""
    p = Path(path)
    if not p.exists():
        log.warning("leagues.xlsx not found at %s, returning empty settings", p)
        return []

    try:
        from openpyxl import load_workbook
    except ImportError:
        log.error("openpyxl not installed, cannot read leagues.xlsx")
        return []

    wb = load_workbook(filename=str(p), data_only=True)
    ws = wb.active
    if ws is None:
        log.warning("No active sheet in leagues.xlsx")
        return []

    settings: list[LeagueSetting] = []
    current: Optional[LeagueSetting] = None

    for row in range(2, (ws.max_row or 1) + 1):
        sport_cell = ws.cell(row=row, column=1).value
        league_cell = ws.cell(row=row, column=2).value
        min_kf_cell = ws.cell(row=row, column=3).value
        max_kf_cell = ws.cell(row=row, column=4).value
        bet_nb_cell = ws.cell(row=row, column=5).value
        bet_kush_cell = ws.cell(row=row, column=6).value

        # New strategy block starts when column A has a value
        if sport_cell is not None and str(sport_cell).strip():
            current = LeagueSetting(sport=str(sport_cell).strip().lower())
            settings.append(current)

        if current is None:
            continue

        # Add league name
        if league_cell is not None:
            league = str(league_cell).strip()
            if league and league != "None":
                current.leagues.append(league)

        # Update numeric/text fields (last non-empty value wins)
        if min_kf_cell is not None and min_kf_cell != "":
            current.min_kf = _parse_float(min_kf_cell)
        if max_kf_cell is not None and max_kf_cell != "":
            current.max_kf = _parse_float(max_kf_cell)
        if bet_nb_cell is not None and str(bet_nb_cell).strip():
            current.bet_nb = str(bet_nb_cell).strip()
        if bet_kush_cell is not None and str(bet_kush_cell).strip():
            current.bet_kush = str(bet_kush_cell).strip()

    wb.close()
    log.info("Loaded %d strategy blocks from %s", len(settings), path)
    return settings


def _parse_float(val) -> float:
    """Parse float from cell value, handling comma as decimal separator."""
    try:
        return float(str(val).replace(",", "."))
    except (ValueError, TypeError):
        return 0.0
