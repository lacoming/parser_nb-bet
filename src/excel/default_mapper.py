"""Unified 18-column mapping for Excel output.

Matches customer template: one sheet, 18 columns, monthly append.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ColumnDef:
    """Single column definition."""
    header: str
    width: int = 12


# Unified 18-column layout (customer template)
UNIFIED_COLUMNS: list[ColumnDef] = [
    ColumnDef("Дата", 12),
    ColumnDef("Время", 8),
    ColumnDef("Лига", 25),
    ColumnDef("Дома", 20),
    ColumnDef("Гости", 20),
    ColumnDef("Ставка", 8),
    ColumnDef("Kf1 старт", 10),
    ColumnDef("KfX старт", 10),
    ColumnDef("Kf2 старт", 10),
    ColumnDef("KfNB", 10),
    ColumnDef("Мин KfKush", 12),
    ColumnDef("Ставка на НБ", 12),
    ColumnDef("Ставка на Куш", 12),
    ColumnDef("основания для - на куше", 22),
    ColumnDef("кф куша", 10),
    ColumnDef("Дата ставки Куш", 14),
    ColumnDef("Время ставки Куш", 14),
    ColumnDef("Ссылка", 40),
]


def get_headers() -> list[str]:
    """Return list of header strings."""
    return [c.header for c in UNIFIED_COLUMNS]


def get_widths() -> list[int]:
    """Return list of column widths."""
    return [c.width for c in UNIFIED_COLUMNS]
