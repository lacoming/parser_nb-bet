"""Tests for src.ui.main_window — QueueLogHandler + MainWindow."""
from __future__ import annotations

import logging
import queue
import threading

import pytest

# Skip all tests if tkinter is unavailable (headless CI, etc.)
tk = pytest.importorskip("tkinter")

from src.ui.main_window import MainWindow, QueueLogHandler


# ================================================================ QueueLogHandler


class TestQueueLogHandler:
    """Tests for QueueLogHandler (no Tk window needed)."""

    def _make_record(self, msg: str, level: int = logging.INFO) -> logging.LogRecord:
        return logging.LogRecord(
            name="test", level=level, pathname="", lineno=0,
            msg=msg, args=(), exc_info=None,
        )

    def test_emit_puts_message(self):
        h = QueueLogHandler()
        h.setFormatter(logging.Formatter("%(message)s"))
        h.emit(self._make_record("hello"))
        assert h.log_queue.get_nowait() == "hello"

    def test_emit_formatted(self):
        h = QueueLogHandler()
        h.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        h.emit(self._make_record("warn!", logging.WARNING))
        assert h.log_queue.get_nowait() == "[WARNING] warn!"

    def test_empty_queue_initially(self):
        h = QueueLogHandler()
        assert h.log_queue.empty()

    def test_multiple_messages(self):
        h = QueueLogHandler()
        h.setFormatter(logging.Formatter("%(message)s"))
        for i in range(5):
            h.emit(self._make_record(f"msg{i}"))
        msgs = []
        while not h.log_queue.empty():
            msgs.append(h.log_queue.get_nowait())
        assert msgs == ["msg0", "msg1", "msg2", "msg3", "msg4"]

    def test_queue_full_does_not_raise(self):
        h = QueueLogHandler(maxsize=3)
        h.setFormatter(logging.Formatter("%(message)s"))
        for i in range(10):
            h.emit(self._make_record(f"m{i}"))
        # Only first 3 messages kept
        count = 0
        while not h.log_queue.empty():
            h.log_queue.get_nowait()
            count += 1
        assert count == 3

    def test_integration_with_logger(self):
        h = QueueLogHandler()
        h.setFormatter(logging.Formatter("%(message)s"))
        logger = logging.getLogger("test_ui_integration")
        logger.addHandler(h)
        logger.setLevel(logging.DEBUG)
        try:
            logger.info("integration test")
            assert h.log_queue.get_nowait() == "integration test"
        finally:
            logger.removeHandler(h)


# ================================================================ MainWindow


class TestMainWindow:
    """Tests for MainWindow Tkinter UI.

    Each test creates and destroys a Tk window.
    """

    @pytest.fixture()
    def window(self):
        w = MainWindow(title="test-window")
        yield w
        try:
            if not w._destroyed:
                w.root.destroy()
        except tk.TclError:
            pass

    # --- creation ---

    def test_window_title(self, window):
        assert window.root.title() == "test-window"

    def test_initial_status(self, window):
        assert "\u0413\u043e\u0442\u043e\u0432" in window.status_var.get()

    def test_initial_stats(self, window):
        val = window.stats_var.get()
        assert "\u0426\u0438\u043a\u043b\u043e\u0432: 0" in val
        assert "\u0421\u0442\u0430\u0432\u043e\u043a: 0" in val

    def test_initial_button_states(self, window):
        assert str(window.btn_start["state"]) == "normal"
        assert str(window.btn_pause["state"]) == "disabled"
        assert str(window.btn_hide["state"]) == "normal"
        assert str(window.btn_exit["state"]) == "normal"

    def test_log_handler_is_attached(self, window):
        assert isinstance(window.log_handler, QueueLogHandler)

    # --- set_status ---

    def test_set_status(self, window):
        window.set_status("Test Status")
        assert window.status_var.get() == "Test Status"

    # --- update_stats ---

    def test_update_stats(self, window):
        window.update_stats(cycles=3, placed=5, pending=2)
        val = window.stats_var.get()
        assert "3" in val
        assert "5" in val
        assert "2" in val

    def test_update_stats_default(self, window):
        window.update_stats()
        assert "\u0426\u0438\u043a\u043b\u043e\u0432: 0" in window.stats_var.get()

    # --- log text ---

    def test_append_log_line(self, window):
        window._append_log_line("line one")
        window.log_text.configure(state=tk.NORMAL)
        content = window.log_text.get("1.0", tk.END)
        window.log_text.configure(state=tk.DISABLED)
        assert "line one" in content

    def test_append_multiple_lines(self, window):
        for i in range(10):
            window._append_log_line(f"line-{i}")
        window.log_text.configure(state=tk.NORMAL)
        content = window.log_text.get("1.0", tk.END)
        window.log_text.configure(state=tk.DISABLED)
        assert "line-0" in content
        assert "line-9" in content

    def test_poll_processes_queue(self, window):
        window.log_handler.log_queue.put("poll msg")
        window._poll_log_queue()
        window.log_text.configure(state=tk.NORMAL)
        content = window.log_text.get("1.0", tk.END)
        window.log_text.configure(state=tk.DISABLED)
        assert "poll msg" in content

    # --- start ---

    def test_start_triggers_callback(self, window):
        called = threading.Event()

        def on_start():
            called.set()

        window._on_start = on_start
        window._handle_start()
        assert called.wait(timeout=2)
        if window._worker_thread:
            window._worker_thread.join(timeout=2)

    def test_start_changes_button_states(self, window):
        window._on_start = lambda: None
        window._handle_start()
        assert str(window.btn_start["state"]) == "disabled"
        assert str(window.btn_pause["state"]) == "normal"
        if window._worker_thread:
            window._worker_thread.join(timeout=2)

    def test_start_sets_running_flag(self, window):
        window._on_start = lambda: None
        window._handle_start()
        assert window._running is True
        assert window.is_running is True
        if window._worker_thread:
            window._worker_thread.join(timeout=2)

    def test_double_start_ignored(self, window):
        call_count = []
        hold = threading.Event()

        def on_start():
            call_count.append(1)
            hold.wait(timeout=2)

        window._on_start = on_start
        window._handle_start()
        window._handle_start()  # should be ignored
        hold.set()
        if window._worker_thread:
            window._worker_thread.join(timeout=2)
        assert len(call_count) == 1

    def test_start_without_callback(self, window):
        # No _on_start set — should not crash
        window._handle_start()
        assert window._running is True

    # --- pause ---

    def test_pause_toggle(self, window):
        window._running = True
        window.btn_pause.configure(state=tk.NORMAL)

        pause_calls = []
        window._on_pause = lambda: pause_calls.append(True)

        window._handle_pause()
        assert window._paused is True
        assert window.is_paused is True
        assert "\u041f\u0440\u043e\u0434\u043e\u043b\u0436\u0438\u0442\u044c" in window.btn_pause["text"]

        window._handle_pause()
        assert window._paused is False
        assert "\u041f\u0430\u0443\u0437\u0430" in window.btn_pause["text"]

        assert len(pause_calls) == 2

    def test_pause_when_not_running_ignored(self, window):
        calls = []
        window._on_pause = lambda: calls.append(1)
        window._handle_pause()
        assert len(calls) == 0
        assert window._paused is False

    # --- hide / show ---

    def test_hide_iconifies(self, window):
        window._handle_hide()
        assert window.root.state() == "iconic"

    def test_show_restores(self, window):
        window._handle_hide()
        window.show()
        assert window.root.state() == "normal"

    # --- exit ---

    def test_exit_sets_destroyed(self, window):
        exit_calls = []
        window._on_exit = lambda: exit_calls.append(True)
        window._do_exit()
        assert window._destroyed is True
        assert len(exit_calls) == 1

    def test_exit_handles_callback_error(self, window):
        def bad_exit():
            raise RuntimeError("exit error")

        window._on_exit = bad_exit
        window._do_exit()  # should not raise
        assert window._destroyed is True

    # --- properties ---

    def test_is_paused_default(self, window):
        assert window.is_paused is False

    def test_is_running_default(self, window):
        assert window.is_running is False

    # --- worker done ---

    def test_on_worker_done_resets_state(self, window):
        window._running = True
        window._paused = True
        window.btn_start.configure(state=tk.DISABLED)
        window.btn_pause.configure(state=tk.NORMAL)

        window._on_worker_done()

        assert window._running is False
        assert window._paused is False
        assert str(window.btn_start["state"]) == "normal"
        assert str(window.btn_pause["state"]) == "disabled"
        assert "\u0413\u043e\u0442\u043e\u0432" in window.status_var.get()

    # --- log trimming ---

    def test_log_trim_on_overflow(self, window):
        # Use smaller limits for fast test
        window.MAX_LINES = 100
        window.TRIM_TO = 50
        for i in range(150):
            window._append_log_line(f"L{i}")
        window.log_text.configure(state=tk.NORMAL)
        line_count = int(window.log_text.index("end-1c").split(".")[0])
        window.log_text.configure(state=tk.DISABLED)
        assert line_count <= 105  # some slack for Tk line counting

    # --- set_status when destroyed ---

    def test_set_status_after_destroy_noop(self, window):
        window._destroyed = True
        window.set_status("should not set")
        # status_var may still have old value, but no crash
