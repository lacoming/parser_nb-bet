"""Excel writer using openpyxl with monthly append.

One file per month (YYYY-MM_results.xlsx), one sheet "Результаты",
appends rows after each cycle.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, Side

from src.excel.default_mapper import get_headers, get_widths
from src.excel.models import UnifiedRow

log = logging.getLogger("parser_nb_bet.excel.writer")

_SHEET_NAME = "Результаты"


class ExcelWriter:
    """Buffered Excel writer with monthly file rotation and append.

    Args:
        output_dir: Directory where .xlsx files are saved.
    """

    def __init__(self, output_dir: str = "output") -> None:
        self.output_dir = output_dir
        self._rows: list[UnifiedRow] = []

    @property
    def row_count(self) -> int:
        return len(self._rows)

    def add_row(self, row: UnifiedRow) -> None:
        """Add a row to the buffer."""
        self._rows.append(row)

    def clear(self) -> None:
        """Clear the buffer."""
        self._rows.clear()

    def _make_filename(self) -> str:
        """Generate monthly output filename (YYYY-MM_results.xlsx)."""
        month_str = datetime.now().strftime("%Y-%m")
        name = f"{month_str}_results.xlsx"
        return os.path.join(self.output_dir, name)

    def save(self, filepath: str | None = None) -> str:
        """Write buffered rows to xlsx (append if file exists).

        Args:
            filepath: Optional explicit path. If None, auto-generates
                      monthly filename in output_dir.

        Returns:
            Absolute path to the saved file.
        """
        if filepath is None:
            filepath = self._make_filename()

        # Ensure output directory exists
        dirpath = os.path.dirname(filepath)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)

        headers = get_headers()
        widths = get_widths()

        if os.path.isfile(filepath):
            # Append mode: open existing file
            wb = load_workbook(filepath)
            if _SHEET_NAME in wb.sheetnames:
                ws = wb[_SHEET_NAME]
            else:
                ws = wb.create_sheet(_SHEET_NAME)
                _write_header(ws, headers, widths)
        else:
            # Create new file
            wb = Workbook()
            ws = wb.active
            ws.title = _SHEET_NAME
            _write_header(ws, headers, widths)

        # Append data rows
        for row in self._rows:
            ws.append(row.as_list())

        wb.save(filepath)
        wb.close()

        log.info("Excel saved: %s (%d new rows)", filepath, len(self._rows))
        return filepath


def _write_header(ws, headers: list[str], widths: list[int]) -> None:
    """Write header row with formatting."""
    header_font = Font(name="Times New Roman", size=11, bold=True)
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

    for col_idx, (header, width) in enumerate(zip(headers, widths), start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.alignment = header_align
        cell.border = thin_border
        # openpyxl uses 1-based column letter for width
        ws.column_dimensions[cell.column_letter].width = width
