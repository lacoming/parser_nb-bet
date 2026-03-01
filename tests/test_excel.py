"""Tests for Excel writer (unified 18-column format)."""
from __future__ import annotations

import os
import tempfile

import pytest

from src.excel.default_mapper import (
    UNIFIED_COLUMNS,
    ColumnDef,
    get_headers,
    get_widths,
)
from src.excel.models import UnifiedRow
from src.excel.writer import ExcelWriter


# -- UnifiedRow ---------------------------------------------------------------


class TestUnifiedRow:
    def test_defaults_empty(self):
        row = UnifiedRow()
        assert row.date == ""
        assert row.team_home == ""

    def test_as_list_length(self):
        row = UnifiedRow()
        values = row.as_list()
        assert len(values) == 18

    def test_as_list_order(self):
        row = UnifiedRow(
            date="21.02.2026",
            time="15:00",
            league="EPL",
            team_home="Arsenal",
            team_away="Chelsea",
            bet_type="1",
            kf1_start="2.00",
            kfx_start="3.10",
            kf2_start="3.40",
            kf_nb="2.00",
            min_kf_kush="2.20",
            nb_placed="+",
            kush_placed="+",
            kush_reason="",
            kf_kush="2.40",
            kush_date="21.02.2026",
            kush_time="16:00",
            link="https://nb-bet.com/soccer/arsenal-chelsea-123",
        )
        vals = row.as_list()
        assert vals[0] == "21.02.2026"
        assert vals[1] == "15:00"
        assert vals[2] == "EPL"
        assert vals[3] == "Arsenal"
        assert vals[4] == "Chelsea"
        assert vals[5] == "1"
        assert vals[6] == "2.00"
        assert vals[9] == "2.00"      # KfNB
        assert vals[11] == "+"        # nb_placed
        assert vals[12] == "+"        # kush_placed
        assert vals[14] == "2.40"     # kf_kush
        assert vals[17] == "https://nb-bet.com/soccer/arsenal-chelsea-123"

    def test_missing_scenario(self):
        row = UnifiedRow(
            date="01.03.2026",
            league="La Liga",
            team_home="Barcelona",
            team_away="Sevilla",
            bet_type="1X",
            nb_placed="-",
            kush_placed="-",
            kush_reason="отсутствие",
        )
        vals = row.as_list()
        assert vals[12] == "-"
        assert vals[13] == "отсутствие"
        assert vals[14] == ""  # no kf_kush
        assert vals[15] == ""  # no kush_date

    def test_ratio_rejected_scenario(self):
        row = UnifiedRow(
            kush_placed="-",
            kush_reason="ratio",
            kf_kush="2.10",
        )
        vals = row.as_list()
        assert vals[12] == "-"
        assert vals[13] == "ratio"
        assert vals[14] == "2.10"

    def test_pending_scenario(self):
        row = UnifiedRow(
            kush_placed="-",
            kush_reason="ожидание",
        )
        vals = row.as_list()
        assert vals[12] == "-"
        assert vals[13] == "ожидание"


# -- DefaultMapper ------------------------------------------------------------


class TestDefaultMapper:
    def test_column_count(self):
        assert len(UNIFIED_COLUMNS) == 18

    def test_headers_count(self):
        assert len(get_headers()) == 18

    def test_widths_count(self):
        assert len(get_widths()) == 18

    def test_headers_match_columns(self):
        headers = get_headers()
        for i, col in enumerate(UNIFIED_COLUMNS):
            assert headers[i] == col.header

    def test_first_columns(self):
        h = get_headers()
        assert h[0] == "Дата"
        assert h[1] == "Время"
        assert h[2] == "Лига"
        assert h[3] == "Дома"
        assert h[4] == "Гости"
        assert h[5] == "Ставка"

    def test_last_columns(self):
        h = get_headers()
        assert h[16] == "Время ставки Куш"
        assert h[17] == "Ссылка"

    def test_column_def_defaults(self):
        c = ColumnDef("Test")
        assert c.width == 12


# -- ExcelWriter --------------------------------------------------------------


class TestExcelWriter:
    def test_init_defaults(self):
        w = ExcelWriter()
        assert w.output_dir == "output"
        assert w.row_count == 0

    def test_add_row(self):
        w = ExcelWriter()
        w.add_row(UnifiedRow(date="21.02.2026"))
        assert w.row_count == 1

    def test_clear(self):
        w = ExcelWriter()
        w.add_row(UnifiedRow())
        w.add_row(UnifiedRow())
        assert w.row_count == 2
        w.clear()
        assert w.row_count == 0

    def test_save_empty(self):
        """Save with no rows should create file with headers only."""
        with tempfile.TemporaryDirectory() as tmpdir:
            w = ExcelWriter(output_dir=tmpdir)
            path = w.save()
            assert os.path.exists(path)
            assert path.endswith(".xlsx")
            assert os.path.getsize(path) > 0

    def test_save_with_rows(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            w = ExcelWriter(output_dir=tmpdir)
            w.add_row(UnifiedRow(
                date="21.02.2026", time="15:00", league="EPL",
                team_home="Arsenal", team_away="Chelsea", bet_type="1",
                kush_placed="+", kf_kush="2.40",
            ))
            w.add_row(UnifiedRow(
                date="21.02.2026", time="17:30", league="La Liga",
                team_home="Barcelona", team_away="Real Madrid", bet_type="1X",
                kush_placed="-", kush_reason="ratio",
            ))
            path = w.save()
            assert os.path.exists(path)
            assert os.path.getsize(path) > 1000

    def test_save_explicit_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            w = ExcelWriter()
            path = os.path.join(tmpdir, "custom_output.xlsx")
            result = w.save(filepath=path)
            assert result == path
            assert os.path.exists(path)

    def test_save_creates_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            nested = os.path.join(tmpdir, "sub", "dir")
            w = ExcelWriter(output_dir=nested)
            path = w.save()
            assert os.path.exists(path)

    def test_filename_monthly_format(self):
        w = ExcelWriter()
        name = w._make_filename()
        # Should contain YYYY-MM pattern
        assert "_results.xlsx" in name
        assert ".xlsx" in name

    def test_multiple_saves(self):
        """Can save multiple times with same data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            w = ExcelWriter(output_dir=tmpdir)
            w.add_row(UnifiedRow(team_home="Test"))
            p1 = os.path.join(tmpdir, "out1.xlsx")
            p2 = os.path.join(tmpdir, "out2.xlsx")
            w.save(filepath=p1)
            w.save(filepath=p2)
            assert os.path.exists(p1)
            assert os.path.exists(p2)

    def test_single_sheet(self):
        """All row types go to a single 'Результаты' sheet."""
        with tempfile.TemporaryDirectory() as tmpdir:
            w = ExcelWriter(output_dir=tmpdir)
            w.add_row(UnifiedRow(team_home="Arsenal", kush_placed="+"))
            w.add_row(UnifiedRow(team_home="Liverpool", kush_placed="-", kush_reason="отсутствие"))
            w.add_row(UnifiedRow(team_home="Bayern", kush_placed="-", kush_reason="ratio"))
            w.add_row(UnifiedRow(team_home="Barcelona", kush_placed="-", kush_reason="ожидание"))
            path = w.save()
            import openpyxl
            wb = openpyxl.load_workbook(path)
            assert wb.sheetnames == ["Результаты"]
            ws = wb.active
            # header + 4 data rows
            assert ws.max_row == 5
            wb.close()

    def test_append_mode(self):
        """Second save appends rows to existing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test_append.xlsx")

            # First write: 2 rows
            w1 = ExcelWriter(output_dir=tmpdir)
            w1.add_row(UnifiedRow(team_home="Arsenal"))
            w1.add_row(UnifiedRow(team_home="Chelsea"))
            w1.save(filepath=path)

            # Second write: 1 row
            w2 = ExcelWriter(output_dir=tmpdir)
            w2.add_row(UnifiedRow(team_home="Liverpool"))
            w2.save(filepath=path)

            # Verify: header + 3 data rows
            import openpyxl
            wb = openpyxl.load_workbook(path)
            ws = wb.active
            assert ws.max_row == 4  # 1 header + 3 data
            assert ws.cell(2, 4).value == "Arsenal"
            assert ws.cell(3, 4).value == "Chelsea"
            assert ws.cell(4, 4).value == "Liverpool"
            wb.close()

    def test_18_columns_in_file(self):
        """Verify the file has exactly 18 columns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            w = ExcelWriter(output_dir=tmpdir)
            w.add_row(UnifiedRow(
                date="01.03.2026", time="15:00", league="EPL",
                team_home="Arsenal", team_away="Chelsea", bet_type="1",
                kf1_start="2.00", kfx_start="3.10", kf2_start="3.40",
                kf_nb="2.00", min_kf_kush="2.20",
                nb_placed="+", kush_placed="+", kush_reason="",
                kf_kush="2.40", kush_date="01.03.2026", kush_time="16:00",
                link="https://nb-bet.com/soccer/arsenal-chelsea-123",
            ))
            path = w.save()
            import openpyxl
            wb = openpyxl.load_workbook(path)
            ws = wb.active
            # Header row should have 18 columns
            headers = [ws.cell(1, c).value for c in range(1, 19)]
            assert len(headers) == 18
            assert headers[0] == "Дата"
            assert headers[17] == "Ссылка"
            # Data row
            assert ws.cell(2, 4).value == "Arsenal"
            assert ws.cell(2, 12).value == "+"  # nb_placed
            assert ws.cell(2, 13).value == "+"  # kush_placed
            wb.close()
