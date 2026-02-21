"""Odds key decoder: translates numeric key IDs to human-readable bet names.

Uses sl_keys.json mapping (1000+ entries) loaded once at module init.
The decode logic is ported from legacy Python code (decode_key.py).
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

log = logging.getLogger("parser_nb_bet.nb.odds_decoder")

# Translation table for bet name components
_TR = {
    "home": "1", "away": "2", "total": "Т", "individualTotal": "ИТ",
    "over": "Б", "under": "М", "handicap": "Ф", "win": "П", "draw": "X",
    "yes": "Да", "no": "Нет", "correctScore": "Точный счет",
    "bothTeamsToScore": "Обе забьют", "totalEven": "Тотал чет",
    "first": "1-й", "second": "2-й", "third": "3-й",
    "period": "период", "corners": "Угловые", "yellowCards": "ЖК",
    "winToNilShort": "СП",
}


def load_odds_keys(path: Optional[str] = None) -> dict[int, str]:
    """Load sl_keys.json → {int_id: string_key}."""
    if path is None:
        path = os.path.join(
            os.path.dirname(__file__), "..", "..", "assets", "data", "sl_keys.json"
        )
    p = Path(path).resolve()
    if not p.exists():
        log.warning("sl_keys.json not found at %s", p)
        return {}
    with open(p, encoding="utf-8") as f:
        raw = json.load(f)
    return {int(k): v for k, v in raw.items()}


def decode_odds_key(odds_key: int | str, keys_map: dict[int, str]) -> str:
    """Translate an odds key ID (or string key) to a human-readable name."""
    if isinstance(odds_key, int):
        key_str = keys_map.get(odds_key, "")
        if not key_str:
            return f"Unknown:{odds_key}"
    else:
        key_str = str(odds_key)

    if not key_str:
        return "Unknown"

    # 1x2 basic outcomes
    simple = {
        "WIN_HOME": f"{_TR['win']}{_TR['home']}",
        "WIN_AWAY": f"{_TR['win']}{_TR['away']}",
        "DRAW": _TR["draw"],
        "HOME_OR_X": f"{_TR['home']} или X",
        "AWAY_OR_X": f"{_TR['away']} или X",
        "HOME_OR_AWAY": f"{_TR['home']} или {_TR['away']}",
    }
    if key_str in simple:
        return simple[key_str]

    # Totals
    if key_str.startswith("TB_"):
        val = key_str[3:].replace("_", ".")
        return f"{_TR['total']}{_TR['over']} ({val})"
    if key_str.startswith("TM_"):
        val = key_str[3:].replace("_", ".")
        return f"{_TR['total']}{_TR['under']} ({val})"

    # Individual totals
    if key_str.startswith("ITB_") or key_str.startswith("ITM_"):
        return _decode_individual_total(key_str)

    # Handicaps
    if key_str.startswith("HANDICAP_"):
        return _decode_handicap(key_str)

    # Correct score
    if key_str.startswith("CORRECT_SCORE_"):
        score = key_str[14:].replace("_", ":")
        return f"{_TR['correctScore']} {score}"

    # Period keys
    for prefix, label in [
        ("FIRST_PERIOD_", _TR["first"]),
        ("SECOND_PERIOD_", _TR["second"]),
        ("THIRD_PERIOD_", _TR["third"]),
    ]:
        if key_str.startswith(prefix):
            rest = key_str[len(prefix):]
            inner = decode_odds_key(rest, {})
            return f"{label} {_TR['period']} - {inner}"

    # Fallback: return raw key
    return key_str


def _decode_individual_total(key_str: str) -> str:
    parts = key_str.split("_")
    if len(parts) >= 3:
        bet_type = parts[0]  # ITB or ITM
        value = parts[1]
        team = parts[2] if len(parts) > 2 else "HOME"
        team_num = _TR["home"] if team == "HOME" else _TR["away"]
        direction = _TR["over"] if bet_type == "ITB" else _TR["under"]
        return f"{_TR['individualTotal']}{team_num} {direction} ({value.replace('_', '.')})"
    return key_str


def _decode_handicap(key_str: str) -> str:
    parts = key_str.split("_")
    if len(parts) >= 3:
        direction = parts[1]
        value = parts[2]
        team = parts[3] if len(parts) > 3 else "HOME"
        team_num = "1" if team == "HOME" else "2"
        if direction == "MINUS":
            sign = "-"
        elif direction == "PLUS":
            sign = "+"
        else:
            sign = ""
        return f"{_TR['handicap']}{team_num} ({sign}{value.replace('_', '.')})"
    return key_str
