"""Team name normalizer for fuzzy matching between NB-Bet and Kush.

Pipeline: lowercase → apply aliases → transliterate (ru→en) → remove punctuation → collapse whitespace.
"""
from __future__ import annotations

import json
import logging
import os
import re
import unicodedata

log = logging.getLogger("parser_nb_bet.kush.normalizer")

# Cyrillic → Latin transliteration table
_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_SPACE_RE = re.compile(r"\s+")

# Common abbreviations and short forms
_ABBREVIATIONS = {
    "fc": "", "fk": "", "фк": "", "sc": "", "ск": "",
    "ac": "", "as": "", "cf": "",
}

# Team name aliases: loaded from sl_teams_zamen.json
_aliases: dict[str, str] = {}


def load_aliases(path: str) -> int:
    """Load team name aliases from JSON file.

    Args:
        path: Path to sl_teams_zamen.json.

    Returns:
        Number of aliases loaded.
    """
    global _aliases
    if not os.path.isfile(path):
        log.warning("Aliases file not found: %s", path)
        _aliases = {}
        return 0
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        _aliases = {k.lower(): v.lower() for k, v in data.items()}
        log.info("Loaded %d team aliases from %s", len(_aliases), os.path.basename(path))
        return len(_aliases)
    except Exception:
        log.exception("Failed to load aliases from %s", path)
        _aliases = {}
        return 0


def get_aliases() -> dict[str, str]:
    """Return current aliases dict (read-only copy)."""
    return dict(_aliases)


def _apply_aliases(name: str) -> str:
    """Apply team name aliases to a lowercased name.

    Checks full name first, then individual words.
    """
    if not _aliases:
        return name
    # Full name match
    if name in _aliases:
        return _aliases[name]
    # Word-level replacement (for partial aliases like "миссан" → "майсан")
    words = name.split()
    changed = False
    for i, w in enumerate(words):
        if w in _aliases:
            words[i] = _aliases[w]
            changed = True
    return " ".join(words) if changed else name


def normalize(name: str) -> str:
    """Normalize a team/league name for fuzzy comparison.

    Steps:
    1. Lowercase
    2. Apply aliases (sl_teams_zamen.json)
    3. Transliterate Cyrillic → Latin
    4. Remove punctuation
    5. Remove common prefixes (FC, FK, etc.)
    6. Collapse whitespace
    7. Strip
    """
    s = name.lower()
    s = _apply_aliases(s)
    s = _transliterate(s)
    s = _PUNCT_RE.sub(" ", s)
    s = _SPACE_RE.sub(" ", s).strip()
    # Remove common abbreviations
    words = s.split()
    words = [w for w in words if w not in _ABBREVIATIONS]
    return " ".join(words).strip()


def _transliterate(text: str) -> str:
    """Transliterate Cyrillic characters to Latin."""
    result = []
    for ch in text:
        if ch in _TRANSLIT:
            result.append(_TRANSLIT[ch])
        elif ch.lower() in _TRANSLIT:
            result.append(_TRANSLIT[ch.lower()])
        else:
            result.append(ch)
    return "".join(result)
