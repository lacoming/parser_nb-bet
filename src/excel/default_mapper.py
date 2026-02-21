"""Default column mapping for Excel output.

Defines headers, widths, and column structure matching legacy format.
Customer templates can provide alternative mappers.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ColumnDef:
    """Single column definition."""
    header: str
    width: int = 12


# Default 29-column layout
DEFAULT_COLUMNS: list[ColumnDef] = [
    ColumnDef("Дата", 12),
    ColumnDef("Время", 10),
    ColumnDef("Лига", 22),
    ColumnDef("Команда 1", 25),
    ColumnDef("Команда 2", 25),
    ColumnDef("Голы 1", 8),
    ColumnDef("Голы 2", 8),
    ColumnDef("Тотал", 8),
    ColumnDef("Разница", 8),
    ColumnDef("Кф1 нач", 10),
    ColumnDef("Кф1 кон", 10),
    ColumnDef("КфX нач", 10),
    ColumnDef("КфX кон", 10),
    ColumnDef("Кф2 нач", 10),
    ColumnDef("Кф2 кон", 10),
    ColumnDef("ТС 1", 10),
    ColumnDef("ТС 2", 10),
    ColumnDef("ТС Кф нач", 10),
    ColumnDef("ТС Кф кон", 10),
    ColumnDef("МП вид", 12),
    ColumnDef("МП Кф нач", 10),
    ColumnDef("МП Кф кон", 10),
    ColumnDef("ПП вид", 12),
    ColumnDef("ПП Кф нач", 10),
    ColumnDef("ПП Кф кон", 10),
    ColumnDef("Ссылка", 50),
    ColumnDef("Ставка", 10),
    ColumnDef("Кф Куш", 10),
    ColumnDef("Ratio", 10),
]


def get_headers() -> list[str]:
    """Return list of header strings."""
    return [c.header for c in DEFAULT_COLUMNS]


def get_widths() -> list[int]:
    """Return list of column widths."""
    return [c.width for c in DEFAULT_COLUMNS]
