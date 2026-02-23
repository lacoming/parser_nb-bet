"""MSK timezone scheduler.

Computes next run times based on MSK (Europe/Moscow) start time + interval.
Supports --once and --daemon modes with graceful shutdown.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta, timezone

log = logging.getLogger("parser_nb_bet.scheduler.msk_scheduler")

# MSK = UTC+3 (fixed, no DST since 2014)
MSK = timezone(timedelta(hours=3))


def now_msk() -> datetime:
    """Current time in MSK."""
    return datetime.now(MSK)


def parse_start_time(time_str: str) -> tuple[int, int]:
    """Parse 'HH:MM' start time string. Returns (hour, minute)."""
    parts = time_str.split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid start_time format: {time_str!r}, expected HH:MM")
    return int(parts[0]), int(parts[1])


def compute_next_run(
    start_hour: int,
    start_minute: int,
    interval_hours: int,
    ref_time: datetime | None = None,
) -> datetime:
    """Compute the next scheduled run time in MSK.

    Generates all slots for today: start_time, start_time + interval, ...
    Returns the first slot that is in the future relative to ref_time.
    If all today's slots have passed, returns first slot tomorrow.
    """
    if ref_time is None:
        ref_time = now_msk()
    else:
        ref_time = ref_time.astimezone(MSK)

    today = ref_time.date()

    # Generate slots for today
    base = datetime(today.year, today.month, today.day, start_hour, start_minute, tzinfo=MSK)
    slots = []
    slot = base
    while slot.date() == today:
        slots.append(slot)
        slot = slot + timedelta(hours=interval_hours)

    # Find next future slot
    for s in slots:
        if s > ref_time:
            return s

    # All passed — first slot tomorrow
    tomorrow_base = base + timedelta(days=1)
    return tomorrow_base


class MskScheduler:
    """Scheduler that runs cycles at MSK-based time slots.

    Args:
        start_time_msk: Start time string 'HH:MM'.
        interval_hours: Hours between runs.
        shutdown_event: Threading event for graceful shutdown.
    """

    def __init__(
        self,
        start_time_msk: str = "08:00",
        interval_hours: int = 4,
        shutdown_event: threading.Event | None = None,
    ) -> None:
        self.start_hour, self.start_minute = parse_start_time(start_time_msk)
        self.interval_hours = interval_hours
        self.shutdown_event = shutdown_event or threading.Event()

    def next_run(self, ref_time: datetime | None = None) -> datetime:
        """Get next scheduled run time."""
        return compute_next_run(
            self.start_hour, self.start_minute, self.interval_hours, ref_time
        )

    def wait_until_next(self, ref_time: datetime | None = None) -> bool:
        """Wait until next scheduled run. Returns False if shutdown requested."""
        target = self.next_run(ref_time)
        now = now_msk()
        wait_secs = (target - now).total_seconds()

        if wait_secs <= 0:
            return True

        log.info(
            "Next run at %s MSK (in %.0f min)",
            target.strftime("%H:%M:%S"),
            wait_secs / 60,
        )

        # Wait with periodic checks for shutdown
        return not self.shutdown_event.wait(timeout=wait_secs)

    def run_daemon(self, cycle_fn: callable) -> None:
        """Run cycle_fn on schedule until shutdown.

        Args:
            cycle_fn: Callable that executes one cycle. Called with no args.
        """
        log.info(
            "Daemon started: MSK %02d:%02d every %dh",
            self.start_hour, self.start_minute, self.interval_hours,
        )

        while not self.shutdown_event.is_set():
            if not self.wait_until_next():
                log.info("Shutdown requested, exiting daemon")
                break

            if self.shutdown_event.is_set():
                break

            log.info("Cycle starting at %s MSK", now_msk().strftime("%H:%M:%S"))
            try:
                cycle_fn()
            except Exception:
                log.exception("Cycle failed")

            # Small delay to avoid re-triggering same slot
            time.sleep(2)

        log.info("Daemon stopped")

    def request_shutdown(self) -> None:
        """Request graceful shutdown."""
        self.shutdown_event.set()
