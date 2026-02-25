"""Excel writer using xlsxwriter.

Buffers rows and writes to .xlsx file on save().
"""
from __future__ import annotations

import logging
import os
from datetime import datetime

import xlsxwriter

from src.excel.default_mapper import DEFAULT_COLUMNS, get_headers, get_widths
from src.excel.models import ExcelRow, MissingRow, PendingRow, RejectedRow

log = logging.getLogger("parser_nb_bet.excel.writer")


class ExcelWriter:
    """Buffered Excel writer.

    Args:
        output_dir: Directory where .xlsx files are saved.
        sheet_name: Worksheet name (default "Проставленные").
    """

    def __init__(self, output_dir: str = "output", sheet_name: str = "Проставленные") -> None:
        self.output_dir = output_dir
        self.sheet_name = sheet_name
        self._rows: list[ExcelRow] = []
        self._missing_rows: list[MissingRow] = []
        self._rejected_rows: list[RejectedRow] = []
        self._pending_rows: list[PendingRow] = []

    @property
    def row_count(self) -> int:
        return len(self._rows)

    @property
    def missing_count(self) -> int:
        return len(self._missing_rows)

    @property
    def rejected_count(self) -> int:
        return len(self._rejected_rows)

    @property
    def pending_count(self) -> int:
        return len(self._pending_rows)

    def add_row(self, row: ExcelRow) -> None:
        """Add a row to the buffer."""
        self._rows.append(row)

    def add_missing_row(self, row: MissingRow) -> None:
        """Add a missing-match row to the buffer."""
        self._missing_rows.append(row)

    def add_rejected_row(self, row: RejectedRow) -> None:
        """Add a ratio-rejected row to the buffer."""
        self._rejected_rows.append(row)

    def add_pending_row(self, row: PendingRow) -> None:
        """Add a far-future pending row to the buffer."""
        self._pending_rows.append(row)

    def clear(self) -> None:
        """Clear all buffers."""
        self._rows.clear()
        self._missing_rows.clear()
        self._rejected_rows.clear()
        self._pending_rows.clear()

    def _make_filename(self, suffix: str = "") -> str:
        """Generate output filename with date."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        name = f"{date_str}_results{suffix}.xlsx"
        return os.path.join(self.output_dir, name)

    def save(self, filepath: str | None = None) -> str:
        """Write buffered rows to xlsx and return file path.

        Args:
            filepath: Optional explicit path. If None, auto-generates
                      based on date in output_dir.

        Returns:
            Absolute path to the saved file.
        """
        if filepath is None:
            filepath = self._make_filename()

        # Ensure output directory exists
        dirpath = os.path.dirname(filepath)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)

        wb = xlsxwriter.Workbook(filepath, {"strings_to_urls": False})
        ws = wb.add_worksheet(self.sheet_name)

        # Formats
        header_fmt = wb.add_format(
            {
                "bold": True,
                "font_name": "Times New Roman",
                "font_size": 11,
                "align": "center",
                "valign": "vcenter",
                "text_wrap": True,
                "border": 2,
            }
        )

        # Column widths
        widths = get_widths()
        for i, w in enumerate(widths):
            ws.set_column(i, i, w)

        # Header row
        headers = get_headers()
        for col, h in enumerate(headers):
            ws.write(0, col, h, header_fmt)

        # Data rows
        for row_idx, row in enumerate(self._rows, start=1):
            values = row.as_list()
            for col, val in enumerate(values):
                ws.write(row_idx, col, val)

        # Table formatting (if there are rows)
        if self._rows:
            last_row = len(self._rows)
            last_col = len(headers) - 1
            columns = [{"header": h} for h in headers]
            ws.add_table(
                0, 0, last_row, last_col,
                {
                    "name": "ResultsData",
                    "style": "Table Style Medium 3",
                    "columns": columns,
                },
            )

        # --- Second sheet: Ненайденные (missing matches) ---
        if self._missing_rows:
            ws2 = wb.add_worksheet("Ненайденные")
            m_headers = MissingRow.headers()
            m_widths = MissingRow.widths()
            for i, w in enumerate(m_widths):
                ws2.set_column(i, i, w)
            for col, h in enumerate(m_headers):
                ws2.write(0, col, h, header_fmt)
            for row_idx, mrow in enumerate(self._missing_rows, start=1):
                for col, val in enumerate(mrow.as_list()):
                    ws2.write(row_idx, col, val)
            last_m = len(self._missing_rows)
            last_mc = len(m_headers) - 1
            m_columns = [{"header": h} for h in m_headers]
            ws2.add_table(
                0, 0, last_m, last_mc,
                {
                    "name": "MissingData",
                    "style": "Table Style Medium 4",
                    "columns": m_columns,
                },
            )

        # --- Third sheet: ОТКЛОНЕНО (ratio-rejected matches) ---
        if self._rejected_rows:
            ws3 = wb.add_worksheet("Отклонено")
            r_headers = RejectedRow.headers()
            r_widths = RejectedRow.widths()
            for i, w in enumerate(r_widths):
                ws3.set_column(i, i, w)
            for col, h in enumerate(r_headers):
                ws3.write(0, col, h, header_fmt)
            for row_idx, rrow in enumerate(self._rejected_rows, start=1):
                for col, val in enumerate(rrow.as_list()):
                    ws3.write(row_idx, col, val)
            last_r = len(self._rejected_rows)
            last_rc = len(r_headers) - 1
            r_columns = [{"header": h} for h in r_headers]
            ws3.add_table(
                0, 0, last_r, last_rc,
                {
                    "name": "RejectedData",
                    "style": "Table Style Medium 5",
                    "columns": r_columns,
                },
            )

        # --- Fourth sheet: Ожидающие (far-future pending matches) ---
        if self._pending_rows:
            ws4 = wb.add_worksheet("Ожидающие")
            p_headers = PendingRow.headers()
            p_widths = PendingRow.widths()
            for i, w in enumerate(p_widths):
                ws4.set_column(i, i, w)
            for col, h in enumerate(p_headers):
                ws4.write(0, col, h, header_fmt)
            for row_idx, prow in enumerate(self._pending_rows, start=1):
                for col, val in enumerate(prow.as_list()):
                    ws4.write(row_idx, col, val)
            last_p = len(self._pending_rows)
            last_pc = len(p_headers) - 1
            p_columns = [{"header": h} for h in p_headers]
            ws4.add_table(
                0, 0, last_p, last_pc,
                {
                    "name": "PendingData",
                    "style": "Table Style Medium 6",
                    "columns": p_columns,
                },
            )

        wb.close()
        log.info(
            "Excel saved: %s (%d rows, %d missing, %d rejected, %d pending)",
            filepath, len(self._rows), len(self._missing_rows),
            len(self._rejected_rows), len(self._pending_rows),
        )
        return filepath
