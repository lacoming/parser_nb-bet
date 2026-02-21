"""Team name normalizer for fuzzy matching between NB-Bet and Kush.

Pipeline: lowercase → transliterate (ru→en) → remove punctuation → collapse whitespace.
"""
from __future__ import annotations

import re
import unicodedata

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


def normalize(name: str) -> str:
    """Normalize a team/league name for fuzzy comparison.

    Steps:
    1. Lowercase
    2. Transliterate Cyrillic → Latin
    3. Remove punctuation
    4. Remove common prefixes (FC, FK, etc.)
    5. Collapse whitespace
    6. Strip
    """
    s = name.lower()
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
