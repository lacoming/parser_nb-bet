"""In-memory state management: pending queue, placed bets, known keys."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PendingEntry:
    match_key: str
    bet_types: list[str]
    enqueued_at: float = field(default_factory=time.time)
    next_check_at: float = field(default_factory=time.time)
    check_count: int = 0


class AppState:
    """In-memory state for pending matches, placed bets, and deduplication."""

    def __init__(self, recheck_interval: float = 300.0, max_checks: int = 48):
        self._pending: dict[str, PendingEntry] = {}
        self._placed: set[str] = set()
        self._known: set[str] = set()
        self._processed: set[str] = set()  # all fully processed (placed/rejected/missing)
        self._ratio_rejected: set[str] = set()  # ratio-rejected (NOT processed → recheck)
        self._recheck_interval = recheck_interval  # seconds between rechecks
        self._max_checks = max_checks  # max rechecks before expiry

    def enqueue_pending(self, match_key: str, bet_types: list[str]) -> bool:
        """Add to pending queue. Returns False if already pending or placed."""
        if match_key in self._pending or match_key in self._placed:
            return False
        self._pending[match_key] = PendingEntry(match_key=match_key, bet_types=bet_types)
        self._known.add(match_key)
        return True

    def get_due_pending(self) -> list[PendingEntry]:
        """Get pending entries that are due for recheck."""
        now = time.time()
        return [e for e in self._pending.values() if e.next_check_at <= now]

    def update_next_check(self, match_key: str) -> None:
        """Bump next_check_at and increment counter."""
        entry = self._pending.get(match_key)
        if entry:
            entry.check_count += 1
            entry.next_check_at = time.time() + self._recheck_interval

    def remove_pending(self, match_key: str) -> Optional[PendingEntry]:
        """Remove from pending queue."""
        return self._pending.pop(match_key, None)

    def record_placed(self, match_key: str) -> None:
        """Record a bet as placed."""
        self._placed.add(match_key)
        self._known.add(match_key)
        self._processed.add(match_key)
        self._pending.pop(match_key, None)

    def record_processed(self, match_key: str) -> None:
        """Record a match as fully processed (placed, rejected, or missing)."""
        self._processed.add(match_key)
        self._known.add(match_key)

    def is_processed(self, match_key: str) -> bool:
        """Check if match has been fully processed in a previous cycle."""
        return match_key in self._processed

    def is_known(self, match_key: str) -> bool:
        """Check if match_key has been seen (pending or placed)."""
        return match_key in self._known

    def is_expired(self, entry: PendingEntry) -> bool:
        """Check if a pending entry has exceeded max rechecks."""
        return entry.check_count >= self._max_checks

    def record_ratio_rejected(self, match_key: str) -> None:
        """Record a match as ratio-rejected. NOT added to processed → will be rechecked."""
        self._ratio_rejected.add(match_key)
        self._known.add(match_key)

    def is_ratio_rejected(self, match_key: str) -> bool:
        """Check if match was previously rejected by ratio."""
        return match_key in self._ratio_rejected

    def promote_to_placed(self, match_key: str) -> None:
        """Promote a ratio-rejected match to placed (ratio now passes)."""
        self._ratio_rejected.discard(match_key)
        self.record_placed(match_key)

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    @property
    def placed_count(self) -> int:
        return len(self._placed)

    @property
    def ratio_rejected_count(self) -> int:
        return len(self._ratio_rejected)
