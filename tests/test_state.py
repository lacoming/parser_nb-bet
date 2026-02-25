"""Tests for in-memory state management."""
from __future__ import annotations

import time

from src.state import AppState, PendingEntry


class TestAppState:
    def test_enqueue_pending(self):
        state = AppState()
        assert state.enqueue_pending("key1", ["1X", "1"]) is True
        assert state.pending_count == 1

    def test_enqueue_duplicate_rejected(self):
        state = AppState()
        state.enqueue_pending("key1", ["1X"])
        assert state.enqueue_pending("key1", ["1X"]) is False
        assert state.pending_count == 1

    def test_enqueue_placed_rejected(self):
        state = AppState()
        state.record_placed("key1")
        assert state.enqueue_pending("key1", ["1X"]) is False

    def test_is_known(self):
        state = AppState()
        assert state.is_known("key1") is False
        state.enqueue_pending("key1", ["1X"])
        assert state.is_known("key1") is True

    def test_is_known_after_placed(self):
        state = AppState()
        state.record_placed("key1")
        assert state.is_known("key1") is True

    def test_remove_pending(self):
        state = AppState()
        state.enqueue_pending("key1", ["1X"])
        entry = state.remove_pending("key1")
        assert entry is not None
        assert entry.match_key == "key1"
        assert state.pending_count == 0

    def test_remove_nonexistent(self):
        state = AppState()
        assert state.remove_pending("key1") is None

    def test_record_placed_removes_pending(self):
        state = AppState()
        state.enqueue_pending("key1", ["1X"])
        state.record_placed("key1")
        assert state.pending_count == 0
        assert state.placed_count == 1

    def test_get_due_pending(self):
        state = AppState()
        state.enqueue_pending("key1", ["1X"])
        # Just enqueued → next_check_at is now → should be due
        due = state.get_due_pending()
        assert len(due) == 1
        assert due[0].match_key == "key1"

    def test_update_next_check(self):
        state = AppState(recheck_interval=600)
        state.enqueue_pending("key1", ["1X"])
        state.update_next_check("key1")
        # After update, should not be due (next_check_at is in future)
        due = state.get_due_pending()
        assert len(due) == 0

    def test_is_expired(self):
        state = AppState(max_checks=3)
        entry = PendingEntry(match_key="key1", bet_types=["1X"], check_count=3)
        assert state.is_expired(entry) is True
        entry.check_count = 2
        assert state.is_expired(entry) is False


class TestRatioRejected:
    def test_record_ratio_rejected(self):
        state = AppState()
        state.record_ratio_rejected("key1")
        assert state.is_ratio_rejected("key1") is True
        assert state.ratio_rejected_count == 1

    def test_ratio_rejected_not_processed(self):
        """Ratio-rejected matches are NOT marked as processed → recheck."""
        state = AppState()
        state.record_ratio_rejected("key1")
        assert state.is_processed("key1") is False
        assert state.is_known("key1") is True

    def test_promote_to_placed(self):
        state = AppState()
        state.record_ratio_rejected("key1")
        assert state.is_ratio_rejected("key1") is True
        state.promote_to_placed("key1")
        assert state.is_ratio_rejected("key1") is False
        assert state.placed_count == 1
        assert state.is_processed("key1") is True

    def test_ratio_rejected_allows_recheck(self):
        """A ratio-rejected match should not be blocked by is_processed."""
        state = AppState()
        state.record_ratio_rejected("key1")
        # is_processed returns False → cycle_runner will recheck this match
        assert state.is_processed("key1") is False

    def test_promote_nonexistent_harmless(self):
        state = AppState()
        state.promote_to_placed("key1")
        assert state.placed_count == 1
        assert state.is_ratio_rejected("key1") is False


class TestFarPending:
    def test_record_far_pending_new(self):
        state = AppState()
        assert state.record_far_pending("key1") is True

    def test_record_far_pending_duplicate(self):
        state = AppState()
        state.record_far_pending("key1")
        assert state.record_far_pending("key1") is False

    def test_far_pending_not_processed(self):
        """Far-pending matches must NOT be marked as processed."""
        state = AppState()
        state.record_far_pending("key1")
        assert state.is_processed("key1") is False

    def test_far_pending_not_known(self):
        """Far-pending matches are not in _known set (they have their own set)."""
        state = AppState()
        state.record_far_pending("key1")
        assert state.is_known("key1") is False
