"""Tests for MSK scheduler and cycle runner (step 09)."""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.scheduler.msk_scheduler import (
    MSK,
    MskScheduler,
    compute_next_run,
    now_msk,
    parse_start_time,
)


# ── parse_start_time ─────────────────────────────────────────────────


class TestParseStartTime:
    def test_valid(self):
        assert parse_start_time("08:00") == (8, 0)

    def test_valid_with_minutes(self):
        assert parse_start_time("14:30") == (14, 30)

    def test_invalid_format(self):
        with pytest.raises(ValueError):
            parse_start_time("8")

    def test_invalid_no_colon(self):
        with pytest.raises(ValueError):
            parse_start_time("0800")


# ── now_msk ──────────────────────────────────────────────────────────


class TestNowMsk:
    def test_returns_msk_tz(self):
        t = now_msk()
        assert t.tzinfo is not None
        assert t.utcoffset() == timedelta(hours=3)


# ── compute_next_run ─────────────────────────────────────────────────


class TestComputeNextRun:
    def test_next_slot_today(self):
        # Ref time: 10:00 MSK, start: 08:00, interval: 4h
        # Slots: 08:00, 12:00, 16:00, 20:00
        # Next should be 12:00
        ref = datetime(2026, 2, 21, 10, 0, tzinfo=MSK)
        result = compute_next_run(8, 0, 4, ref)
        assert result.hour == 12
        assert result.minute == 0
        assert result.date() == ref.date()

    def test_first_slot_today(self):
        # Ref time: 07:00 MSK, first slot is 08:00
        ref = datetime(2026, 2, 21, 7, 0, tzinfo=MSK)
        result = compute_next_run(8, 0, 4, ref)
        assert result.hour == 8
        assert result.minute == 0

    def test_all_passed_tomorrow(self):
        # Ref time: 21:00 MSK, all slots passed
        ref = datetime(2026, 2, 21, 21, 0, tzinfo=MSK)
        result = compute_next_run(8, 0, 4, ref)
        assert result.date() == ref.date() + timedelta(days=1)
        assert result.hour == 8

    def test_exact_slot_time_goes_next(self):
        # At exactly 12:00, should go to 16:00
        ref = datetime(2026, 2, 21, 12, 0, tzinfo=MSK)
        result = compute_next_run(8, 0, 4, ref)
        assert result.hour == 16

    def test_last_slot_today(self):
        # Ref time: 19:00, last slot is 20:00
        ref = datetime(2026, 2, 21, 19, 0, tzinfo=MSK)
        result = compute_next_run(8, 0, 4, ref)
        assert result.hour == 20
        assert result.date() == ref.date()

    def test_custom_interval(self):
        # 6h interval: 08:00, 14:00, 20:00
        ref = datetime(2026, 2, 21, 9, 0, tzinfo=MSK)
        result = compute_next_run(8, 0, 6, ref)
        assert result.hour == 14

    def test_utc_ref_time_converted(self):
        # Ref in UTC (07:00 UTC = 10:00 MSK)
        ref = datetime(2026, 2, 21, 7, 0, tzinfo=timezone.utc)
        result = compute_next_run(8, 0, 4, ref)
        # 10:00 MSK → next slot is 12:00 MSK
        assert result.hour == 12


# ── MskScheduler ─────────────────────────────────────────────────────


class TestMskScheduler:
    def test_init(self):
        s = MskScheduler("08:00", 4)
        assert s.start_hour == 8
        assert s.start_minute == 0
        assert s.interval_hours == 4

    def test_next_run(self):
        s = MskScheduler("08:00", 4)
        ref = datetime(2026, 2, 21, 10, 0, tzinfo=MSK)
        result = s.next_run(ref)
        assert result.hour == 12

    def test_request_shutdown(self):
        s = MskScheduler()
        assert not s.shutdown_event.is_set()
        s.request_shutdown()
        assert s.shutdown_event.is_set()

    def test_custom_shutdown_event(self):
        ev = threading.Event()
        s = MskScheduler(shutdown_event=ev)
        assert s.shutdown_event is ev

    def test_wait_returns_false_on_shutdown(self):
        """If shutdown is already set, wait should return False quickly."""
        s = MskScheduler()
        s.shutdown_event.set()
        # wait_until_next should return False (shutdown)
        result = s.wait_until_next()
        assert result is False

    def test_daemon_stops_on_shutdown(self):
        """Daemon should exit when shutdown is requested."""
        s = MskScheduler("08:00", 4)
        s.shutdown_event.set()  # Pre-set shutdown
        call_count = 0

        def cycle():
            nonlocal call_count
            call_count += 1

        s.run_daemon(cycle)
        assert call_count == 0  # Should not run any cycle


# ── CycleRunner (import test) ────────────────────────────────────────


class TestCycleRunnerImport:
    def test_import(self):
        from src.scheduler.cycle_runner import CycleStats, run_cycle
        stats = CycleStats()
        assert stats.total_matches == 0
        assert stats.placed == 0
        assert stats.errors == 0
