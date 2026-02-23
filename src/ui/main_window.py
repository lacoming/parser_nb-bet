"""Tkinter UI window for parser_nb-bet.

Provides:
- Status panel + stats bar
- Scrollable dark-themed log viewer
- Buttons: Запустить, Пауза, Скрыть, Выход
- Close (X) dialog: Выйти / Свернуть / Отмена
- Thread-safe log updates via QueueLogHandler + root.after()
"""
from __future__ import annotations

import logging
import queue
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext
from typing import Callable, Optional

log = logging.getLogger("parser_nb_bet.ui.main_window")


class QueueLogHandler(logging.Handler):
    """Logging handler that puts formatted records into a thread-safe queue.

    The MainWindow polls this queue via root.after() and appends messages
    to the Text widget on the main thread.
    """

    def __init__(self, maxsize: int = 10_000) -> None:
        super().__init__()
        self.log_queue: queue.Queue = queue.Queue(maxsize=maxsize)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self.log_queue.put_nowait(msg)
        except queue.Full:
            pass
        except Exception:
            self.handleError(record)


class MainWindow:
    """Tkinter main window.

    Args:
        title: Window title.
    """

    POLL_MS = 100
    MAX_LINES = 5000
    TRIM_TO = 4000

    def __init__(self, title: str = "parser_nb-bet") -> None:
        self._on_start: Optional[Callable[[], None]] = None
        self._on_pause: Optional[Callable[[], None]] = None
        self._on_exit: Optional[Callable[[], None]] = None

        self._running = False
        self._paused = False
        self._worker_thread: Optional[threading.Thread] = None
        self._destroyed = False

        # Log handler (created before Tk so it can be attached to logging early)
        self.log_handler = QueueLogHandler()

        # Build Tk window
        self.root = tk.Tk()
        self.root.title(title)
        self.root.geometry("800x500")
        self.root.minsize(600, 350)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_widgets()
        self._schedule_poll()

    # ------------------------------------------------------------------ build

    def _build_widgets(self) -> None:
        # --- Status bar ---
        status_frame = tk.Frame(self.root)
        status_frame.pack(fill=tk.X, padx=8, pady=(8, 2))

        self.status_var = tk.StringVar(value="\u0413\u043e\u0442\u043e\u0432 \u043a \u0437\u0430\u043f\u0443\u0441\u043a\u0443")
        tk.Label(
            status_frame,
            textvariable=self.status_var,
            font=("Segoe UI", 11, "bold"),
            anchor=tk.W,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # --- Stats bar ---
        stats_frame = tk.Frame(self.root)
        stats_frame.pack(fill=tk.X, padx=8, pady=(0, 4))

        self.stats_var = tk.StringVar(
            value="\u0426\u0438\u043a\u043b\u043e\u0432: 0 | \u0421\u0442\u0430\u0432\u043e\u043a: 0 | \u041e\u0436\u0438\u0434\u0430\u043d\u0438\u0435: 0"
        )
        tk.Label(
            stats_frame,
            textvariable=self.stats_var,
            font=("Segoe UI", 9),
            fg="gray",
            anchor=tk.W,
        ).pack(side=tk.LEFT)

        # --- Log viewer ---
        log_frame = tk.Frame(self.root)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            state=tk.DISABLED,
            font=("Consolas", 9),
            bg="#1e1e1e",
            fg="#d4d4d4",
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # --- Buttons ---
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(fill=tk.X, padx=8, pady=8)

        self.btn_start = tk.Button(
            btn_frame,
            text="\u0417\u0430\u043f\u0443\u0441\u0442\u0438\u0442\u044c",
            width=14,
            command=self._handle_start,
        )
        self.btn_start.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_pause = tk.Button(
            btn_frame,
            text="\u041f\u0430\u0443\u0437\u0430",
            width=14,
            command=self._handle_pause,
            state=tk.DISABLED,
        )
        self.btn_pause.pack(side=tk.LEFT, padx=4)

        self.btn_hide = tk.Button(
            btn_frame,
            text="\u0421\u043a\u0440\u044b\u0442\u044c",
            width=14,
            command=self._handle_hide,
        )
        self.btn_hide.pack(side=tk.LEFT, padx=4)

        self.btn_exit = tk.Button(
            btn_frame,
            text="\u0412\u044b\u0445\u043e\u0434",
            width=14,
            command=self._handle_exit,
        )
        self.btn_exit.pack(side=tk.RIGHT)

    # -------------------------------------------------------------- log poll

    def _schedule_poll(self) -> None:
        if not self._destroyed:
            self.root.after(self.POLL_MS, self._poll_log_queue)

    def _poll_log_queue(self) -> None:
        """Read queued log messages and append to Text widget."""
        count = 0
        try:
            while count < 200:
                msg = self.log_handler.log_queue.get_nowait()
                self._append_log_line(msg)
                count += 1
        except queue.Empty:
            pass
        self._schedule_poll()

    def _append_log_line(self, msg: str) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

        # Trim excess lines
        line_count = int(self.log_text.index("end-1c").split(".")[0])
        if line_count > self.MAX_LINES:
            self.log_text.configure(state=tk.NORMAL)
            self.log_text.delete("1.0", f"{line_count - self.TRIM_TO}.0")
            self.log_text.configure(state=tk.DISABLED)

    # -------------------------------------------------------- button handlers

    def _handle_start(self) -> None:
        if self._running:
            return
        self._running = True
        self._paused = False
        self.btn_start.configure(state=tk.DISABLED)
        self.btn_pause.configure(state=tk.NORMAL)
        self.set_status("\u0420\u0430\u0431\u043e\u0442\u0430\u0435\u0442...")

        if self._on_start:
            self._worker_thread = threading.Thread(
                target=self._run_worker, daemon=True, name="ui-worker",
            )
            self._worker_thread.start()

    def _run_worker(self) -> None:
        try:
            if self._on_start:
                self._on_start()
        except Exception:
            log.exception("Worker thread error")
        finally:
            if not self._destroyed:
                try:
                    self.root.after(0, self._on_worker_done)
                except (tk.TclError, RuntimeError):
                    pass

    def _on_worker_done(self) -> None:
        self._running = False
        self._paused = False
        self.btn_start.configure(state=tk.NORMAL)
        self.btn_pause.configure(
            state=tk.DISABLED,
            text="\u041f\u0430\u0443\u0437\u0430",
        )
        self.set_status("\u0413\u043e\u0442\u043e\u0432 \u043a \u0437\u0430\u043f\u0443\u0441\u043a\u0443")

    def _handle_pause(self) -> None:
        if not self._running:
            return
        self._paused = not self._paused
        if self._paused:
            self.btn_pause.configure(
                text="\u041f\u0440\u043e\u0434\u043e\u043b\u0436\u0438\u0442\u044c"
            )
            self.set_status("\u041d\u0430 \u043f\u0430\u0443\u0437\u0435")
        else:
            self.btn_pause.configure(text="\u041f\u0430\u0443\u0437\u0430")
            self.set_status("\u0420\u0430\u0431\u043e\u0442\u0430\u0435\u0442...")
        if self._on_pause:
            self._on_pause()

    def _handle_hide(self) -> None:
        self.root.iconify()

    def _handle_exit(self) -> None:
        self._do_exit()

    def _on_close(self) -> None:
        """Window X button — show exit/minimize dialog."""
        result = messagebox.askyesnocancel(
            "parser_nb-bet",
            "\u0425\u043e\u0442\u0438\u0442\u0435 \u0432\u044b\u0439\u0442\u0438 \u0438\u043b\u0438 \u0441\u0432\u0435\u0440\u043d\u0443\u0442\u044c?",
            detail="\u0414\u0430 \u2014 \u0432\u044b\u0439\u0442\u0438\n\u041d\u0435\u0442 \u2014 \u0441\u0432\u0435\u0440\u043d\u0443\u0442\u044c\n\u041e\u0442\u043c\u0435\u043d\u0430 \u2014 \u043e\u0441\u0442\u0430\u0442\u044c\u0441\u044f",
        )
        if result is True:
            self._do_exit()
        elif result is False:
            self._handle_hide()
        # None (Cancel) = do nothing

    def _do_exit(self) -> None:
        self._destroyed = True
        if self._on_exit:
            try:
                self._on_exit()
            except Exception:
                pass
        try:
            self.root.quit()
            self.root.destroy()
        except tk.TclError:
            pass

    # -------------------------------------------------------------- public API

    def set_status(self, text: str) -> None:
        """Update status label. Thread-safe."""
        if self._destroyed:
            return
        if threading.current_thread() is threading.main_thread():
            self.status_var.set(text)
        else:
            try:
                self.root.after(0, lambda t=text: self.status_var.set(t))
            except tk.TclError:
                pass

    def update_stats(
        self, cycles: int = 0, placed: int = 0, pending: int = 0
    ) -> None:
        """Update stats label. Thread-safe."""
        text = (
            f"\u0426\u0438\u043a\u043b\u043e\u0432: {cycles} | "
            f"\u0421\u0442\u0430\u0432\u043e\u043a: {placed} | "
            f"\u041e\u0436\u0438\u0434\u0430\u043d\u0438\u0435: {pending}"
        )
        if self._destroyed:
            return
        if threading.current_thread() is threading.main_thread():
            self.stats_var.set(text)
        else:
            try:
                self.root.after(0, lambda t=text: self.stats_var.set(t))
            except tk.TclError:
                pass

    def show_cycle_result(self, stats_text: str) -> None:
        """Show a popup with cycle results. Thread-safe."""
        if self._destroyed:
            return

        def _show() -> None:
            messagebox.showinfo("Результат", stats_text)

        if threading.current_thread() is threading.main_thread():
            _show()
        else:
            try:
                self.root.after(0, _show)
            except tk.TclError:
                pass

    def show(self) -> None:
        """Show/restore window after hide."""
        self.root.deiconify()
        self.root.lift()

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def is_running(self) -> bool:
        return self._running

    def run(self) -> None:
        """Start the Tkinter main loop. Blocks until exit."""
        self.root.mainloop()
