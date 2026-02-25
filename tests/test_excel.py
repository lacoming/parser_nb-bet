"""Tests for Excel writer (step 08)."""
from __future__ import annotations

import os
import tempfile

import pytest

from src.excel.default_mapper import (
    DEFAULT_COLUMNS,
    ColumnDef,
    get_headers,
    get_widths,
)
from src.excel.models import ExcelRow, MissingRow, PendingRow, RejectedRow
from src.excel.writer import ExcelWriter


# ── ExcelRow ─────────────────────────────────────────────────────────


class TestExcelRow:
    def test_defaults_empty(self):
        row = ExcelRow()
        assert row.date == ""
        assert row.team_home == ""

    def test_as_list_length(self):
        row = ExcelRow()
        values = row.as_list()
        assert len(values) == 29  # 29 columns

    def test_as_list_order(self):
        row = ExcelRow(
            date="21.02.2026",
            time="15:00",
            league="EPL",
            team_home="Arsenal",
            team_away="Chelsea",
            bet_type="П1",
        )
        vals = row.as_list()
        assert vals[0] == "21.02.2026"
        assert vals[1] == "15:00"
        assert vals[2] == "EPL"
        assert vals[3] == "Arsenal"
        assert vals[4] == "Chelsea"
        assert vals[26] == "П1"

    def test_as_list_all_fields(self):
        row = ExcelRow(
            date="d",
            time="t",
            league="l",
            team_home="h",
            team_away="a",
            score_home="1",
            score_away="2",
            score_total="3",
            score_diff="-1",
            odds_1_start="1.50",
            odds_1_end="1.40",
            odds_x_start="3.00",
            odds_x_end="3.10",
            odds_2_start="5.00",
            odds_2_end="5.50",
            exact_score_home="1",
            exact_score_away="0",
            exact_score_kf_start="6.00",
            exact_score_kf_end="5.80",
            mp_name="ТБ 2.5",
            mp_kf_start="1.80",
            mp_kf_end="1.90",
            pp_name="ТМ 2.5",
            pp_kf_start="2.00",
            pp_kf_end="1.95",
            link="/match/123",
            bet_type="1X",
            kf_kush="2.10",
            ratio="1.15",
        )
        vals = row.as_list()
        assert len(vals) == 29
        assert vals[19] == "ТБ 2.5"
        assert vals[25] == "/match/123"
        assert vals[28] == "1.15"


# ── DefaultMapper ────────────────────────────────────────────────────


class TestDefaultMapper:
    def test_column_count(self):
        assert len(DEFAULT_COLUMNS) == 29

    def test_headers_count(self):
        assert len(get_headers()) == 29

    def test_widths_count(self):
        assert len(get_widths()) == 29

    def test_headers_match_columns(self):
        headers = get_headers()
        for i, col in enumerate(DEFAULT_COLUMNS):
            assert headers[i] == col.header

    def test_first_columns(self):
        h = get_headers()
        assert h[0] == "Дата"
        assert h[1] == "Время"
        assert h[2] == "Лига"
        assert h[3] == "Команда 1"
        assert h[4] == "Команда 2"

    def test_last_columns(self):
        h = get_headers()
        assert h[26] == "Ставка"
        assert h[27] == "Кф Куш"
        assert h[28] == "Ratio"

    def test_column_def_defaults(self):
        c = ColumnDef("Test")
        assert c.width == 12


# ── ExcelWriter ──────────────────────────────────────────────────────


class TestExcelWriter:
    def test_init_defaults(self):
        w = ExcelWriter()
        assert w.output_dir == "output"
        assert w.sheet_name == "Проставленные"
        assert w.row_count == 0
        assert w.rejected_count == 0

    def test_add_row(self):
        w = ExcelWriter()
        w.add_row(ExcelRow(date="21.02.2026"))
        assert w.row_count == 1

    def test_clear(self):
        w = ExcelWriter()
        w.add_row(ExcelRow())
        w.add_row(ExcelRow())
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
            w.add_row(
                ExcelRow(
                    date="21.02.2026",
                    time="15:00",
                    league="EPL",
                    team_home="Arsenal",
                    team_away="Chelsea",
                )
            )
            w.add_row(
                ExcelRow(
                    date="21.02.2026",
                    time="17:30",
                    league="La Liga",
                    team_home="Barcelona",
                    team_away="Real Madrid",
                )
            )
            path = w.save()
            assert os.path.exists(path)
            # File should be bigger with data
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

    def test_filename_contains_date(self):
        w = ExcelWriter()
        name = w._make_filename()
        # Should contain YYYY-MM-DD pattern
        assert "results" in name
        assert ".xlsx" in name

    def test_multiple_saves(self):
        """Can save multiple times with same data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            w = ExcelWriter(output_dir=tmpdir)
            w.add_row(ExcelRow(team_home="Test"))
            p1 = os.path.join(tmpdir, "out1.xlsx")
            p2 = os.path.join(tmpdir, "out2.xlsx")
            w.save(filepath=p1)
            w.save(filepath=p2)
            assert os.path.exists(p1)
            assert os.path.exists(p2)

    def test_add_rejected_row(self):
        w = ExcelWriter()
        w.add_rejected_row(RejectedRow(team_home="Arsenal"))
        assert w.rejected_count == 1

    def test_clear_clears_all_buffers(self):
        w = ExcelWriter()
        w.add_row(ExcelRow())
        w.add_missing_row(MissingRow())
        w.add_rejected_row(RejectedRow())
        w.add_pending_row(PendingRow())
        assert w.row_count == 1
        assert w.missing_count == 1
        assert w.rejected_count == 1
        assert w.pending_count == 1
        w.clear()
        assert w.row_count == 0
        assert w.missing_count == 0
        assert w.rejected_count == 0
        assert w.pending_count == 0

    def test_save_three_sheets(self):
        """Save with all three types creates 3-sheet xlsx."""
        with tempfile.TemporaryDirectory() as tmpdir:
            w = ExcelWriter(output_dir=tmpdir)
            w.add_row(ExcelRow(team_home="Arsenal", team_away="Chelsea"))
            w.add_missing_row(MissingRow(team_home="Liverpool", team_away="Everton"))
            w.add_rejected_row(RejectedRow(
                team_home="Bayern", team_away="Dortmund",
                kf_nb="2.10", kf_kush="2.20", ratio="1.08", threshold="1.10",
            ))
            path = w.save()
            assert os.path.exists(path)
            # Verify via openpyxl that all 3 sheets exist
            import openpyxl
            wb = openpyxl.load_workbook(path)
            sheet_names = wb.sheetnames
            assert "Проставленные" in sheet_names
            assert "Ненайденные" in sheet_names
            assert "Отклонено" in sheet_names
            # Verify rejected sheet has data (header + 1 row)
            ws3 = wb["Отклонено"]
            assert ws3.max_row == 2  # header + 1 data row
            wb.close()

    def test_save_four_sheets(self):
        """Save with all four types creates 4-sheet xlsx."""
        with tempfile.TemporaryDirectory() as tmpdir:
            w = ExcelWriter(output_dir=tmpdir)
            w.add_row(ExcelRow(team_home="Arsenal", team_away="Chelsea"))
            w.add_missing_row(MissingRow(team_home="Liverpool", team_away="Everton"))
            w.add_rejected_row(RejectedRow(
                team_home="Bayern", team_away="Dortmund",
                kf_nb="2.10", kf_kush="2.20", ratio="1.08", threshold="1.10",
            ))
            w.add_pending_row(PendingRow(
                date="10.03.2026", time="20:00", league="La Liga",
                team_home="Barcelona", team_away="Sevilla",
                bet_type="1", kf_nb="1.80", min_kf_kush="2.00",
                link="https://nb-bet.com/soccer/barca-sevilla-123",
            ))
            path = w.save()
            assert os.path.exists(path)
            import openpyxl
            wb = openpyxl.load_workbook(path)
            sheet_names = wb.sheetnames
            assert "Проставленные" in sheet_names
            assert "Ненайденные" in sheet_names
            assert "Отклонено" in sheet_names
            assert "Ожидающие" in sheet_names
            ws4 = wb["Ожидающие"]
            assert ws4.max_row == 2  # header + 1 data row
            # Verify some cell values
            assert ws4.cell(2, 4).value == "Barcelona"
            assert ws4.cell(2, 5).value == "Sevilla"
            wb.close()

    def test_add_pending_row(self):
        w = ExcelWriter()
        w.add_pending_row(PendingRow(team_home="Barcelona"))
        assert w.pending_count == 1

    def test_clear_clears_pending(self):
        w = ExcelWriter()
        w.add_pending_row(PendingRow())
        assert w.pending_count == 1
        w.clear()
        assert w.pending_count == 0


# ── RejectedRow ─────────────────────────────────────────────────────


class TestRejectedRow:
    def test_defaults_empty(self):
        row = RejectedRow()
        assert row.date == ""
        assert row.kf_kush == ""

    def test_as_list_length(self):
        row = RejectedRow()
        assert len(row.as_list()) == 14

    def test_headers_length(self):
        assert len(RejectedRow.headers()) == 14

    def test_widths_length(self):
        assert len(RejectedRow.widths()) == 14

    def test_as_list_order(self):
        row = RejectedRow(
            date="24.02.2026", time="18:00", league="EPL",
            team_home="Arsenal", team_away="Chelsea", bet_type="1",
            kf_nb="2.10", kf_kush="2.20", ratio="1.08", threshold="1.10",
        )
        vals = row.as_list()
        assert vals[0] == "24.02.2026"
        assert vals[3] == "Arsenal"
        assert vals[9] == "2.10"
        assert vals[10] == "2.20"
        assert vals[11] == "1.08"
        assert vals[12] == "1.10"


# ── PendingRow ─────────────────────────────────────────────────────


class TestPendingRow:
    def test_defaults_empty(self):
        row = PendingRow()
        assert row.date == ""
        assert row.min_kf_kush == ""

    def test_as_list_length(self):
        row = PendingRow()
        assert len(row.as_list()) == 12

    def test_headers_length(self):
        assert len(PendingRow.headers()) == 12

    def test_widths_length(self):
        assert len(PendingRow.widths()) == 12

    def test_as_list_order(self):
        row = PendingRow(
            date="10.03.2026", time="20:00", league="La Liga",
            team_home="Barcelona", team_away="Sevilla", bet_type="1",
            kf_nb="1.80", min_kf_kush="2.00",
            link="https://nb-bet.com/soccer/barca-sevilla-123",
        )
        vals = row.as_list()
        assert vals[0] == "10.03.2026"
        assert vals[3] == "Barcelona"
        assert vals[5] == "1"
        assert vals[9] == "1.80"
        assert vals[10] == "2.00"
        assert vals[11] == "https://nb-bet.com/soccer/barca-sevilla-123"
