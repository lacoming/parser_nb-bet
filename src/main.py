"""parser_nb-bet — entry point.

Usage:
    python src/main.py --once --dry-run
    python src/main.py --daemon
    python src/main.py --test-telegram
    python src/main.py          # GUI mode (default)
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

from src.config.loader import ConfigValidationError, load_config
from src.log_setup import setup_logging
from src.state import AppState

log = logging.getLogger("parser_nb_bet")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="parser_nb-bet",
        description="NB-bet results parser and Kush bet placer",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="Run one cycle and exit")
    mode.add_argument("--daemon", action="store_true", help="Run on schedule (daemon mode)")
    parser.add_argument("--dry-run", action="store_true", help="No real bets placed")
    parser.add_argument("--test-telegram", action="store_true", help="Send test Telegram message and exit")
    parser.add_argument("--config", default="config.json", help="Path to config file")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Load config
    try:
        config = load_config(args.config)
    except ConfigValidationError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # Override dry_run from CLI
    if args.dry_run:
        config.kush.dry_run = True

    # Determine mode
    is_gui = not args.once and not args.daemon and not args.test_telegram

    # For GUI mode, create window early so its log handler captures all messages
    window = None
    ui_handler = None
    if is_gui:
        from src.ui.main_window import MainWindow

        window = MainWindow()
        ui_handler = window.log_handler

    # Setup logging
    logger = setup_logging(config.logging, config.files.logs_dir, ui_handler=ui_handler)
    logger.info("parser_nb-bet starting...")
    logger.info(
        "  mode:    %s",
        "gui" if is_gui else "once" if args.once else "daemon" if args.daemon else "test-telegram",
    )
    logger.info("  dry-run: %s", config.kush.dry_run)

    # Init state
    state = AppState()

    # Test telegram mode
    if args.test_telegram:
        from src.telegram.notifier import TelegramNotifier

        tg = TelegramNotifier(
            token=config.telegram.token,
            chat_ids=config.telegram.chat_ids,
            rate_limit=config.telegram.rate_limit_seconds,
        )
        if not tg.enabled:
            logger.error("Telegram not configured (token or chat_ids missing)")
            sys.exit(1)
        results = tg.send_test()
        for r in results:
            if r.ok:
                logger.info("Test message sent to chat %s", r.chat_id)
            else:
                logger.error("Failed to send to chat %s: %s", r.chat_id, r.error)
        return

    # Build shared components for cycle
    from src.config.loader import load_proxies
    from src.decision.engine import DecisionEngine
    from src.decision.league_filter import LeagueFilter
    from src.decision.league_loader import find_leagues_xlsx, load_league_settings
    from src.excel.writer import ExcelWriter
    from src.nb.client import NbClient
    from src.scheduler.cycle_runner import CycleStats, run_cycle
    from src.scheduler.msk_scheduler import MskScheduler
    from src.telegram.notifier import TelegramNotifier

    proxies = load_proxies(config.proxies.file) if config.proxies.enabled else []
    nb_client = NbClient(config=config.nb, proxy_list=proxies)

    # Auto-discover leagues xlsx
    leagues_path = config.files.leagues_xlsx_path
    if not leagues_path or not os.path.isfile(leagues_path):
        app_dir = (
            os.path.dirname(sys.executable)
            if getattr(sys, "frozen", False)
            else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        discovered = find_leagues_xlsx(app_dir)
        if discovered:
            leagues_path = discovered
            logger.info("Using auto-discovered leagues: %s", os.path.basename(discovered))
        else:
            if is_gui and window is not None:
                from tkinter import messagebox as _mb

                _mb.showwarning(
                    "Лиги не найдены",
                    "Не найден файл .xlsx с лигами.\n"
                    "Поместите файл с лигами рядом с программой и перезапустите.",
                )
            logger.warning("No leagues xlsx found — running with empty league settings")
            leagues_path = ""

    league_settings = load_league_settings(leagues_path) if leagues_path else []
    league_filter = LeagueFilter(settings=league_settings)
    decision_engine = DecisionEngine()
    excel_writer = ExcelWriter(output_dir=config.files.output_dir)
    telegram = TelegramNotifier(
        token=config.telegram.token,
        chat_ids=config.telegram.chat_ids,
        rate_limit=config.telegram.rate_limit_seconds,
    )

    def do_cycle() -> CycleStats:
        return run_cycle(
            config=config,
            state=state,
            nb_client=nb_client,
            league_filter=league_filter,
            decision_engine=decision_engine,
            excel_writer=excel_writer,
            telegram=telegram,
            proxies=proxies,
        )

    # Run mode
    if args.once:
        logger.info("Running single cycle...")
        do_cycle()
    elif args.daemon:
        logger.info("Starting daemon mode...")
        scheduler = MskScheduler(
            start_time_msk=config.schedule.start_time_msk,
            interval_hours=config.schedule.interval_hours,
        )
        scheduler.run_daemon(do_cycle)
    else:
        # GUI mode — daemon loop in a worker thread, controlled via UI
        import threading as _threading
        import time as _time

        shutdown_event = _threading.Event()
        pause_event = _threading.Event()

        scheduler = MskScheduler(
            start_time_msk=config.schedule.start_time_msk,
            interval_hours=config.schedule.interval_hours,
            shutdown_event=shutdown_event,
        )

        cycle_count = 0

        def _format_cycle_stats(stats: CycleStats) -> str:
            return (
                f"Матчей найдено: {stats.total_matches}\n"
                f"После фильтра лиг: {stats.filtered}\n"
                f"Прошли решение: {stats.decided}\n"
                f"Найдено на Куше: {stats.matched}\n"
                f"Ставок размещено: {stats.placed}\n"
                f"Не найдено: {stats.missing}\n"
                f"Ошибок: {stats.errors}"
            )

        def on_start() -> None:
            nonlocal cycle_count
            # Run first cycle immediately
            logger.info("Running first cycle...")
            stats: Optional[CycleStats] = None
            try:
                stats = do_cycle()
            except Exception:
                logger.exception("First cycle failed")
            cycle_count += 1
            window.update_stats(
                cycles=cycle_count,
                placed=state.placed_count,
                pending=state.pending_count,
            )
            if stats is not None:
                window.show_cycle_result(_format_cycle_stats(stats))

            # Then enter scheduled daemon loop
            logger.info("Entering scheduled daemon loop...")
            while not shutdown_event.is_set():
                # Pause check
                while pause_event.is_set() and not shutdown_event.is_set():
                    _time.sleep(1)
                if shutdown_event.is_set():
                    break
                if not scheduler.wait_until_next():
                    break
                if shutdown_event.is_set() or pause_event.is_set():
                    continue
                logger.info("Scheduled cycle starting...")
                try:
                    do_cycle()
                except Exception:
                    logger.exception("Cycle failed")
                cycle_count += 1
                window.update_stats(
                    cycles=cycle_count,
                    placed=state.placed_count,
                    pending=state.pending_count,
                )
                _time.sleep(2)
            logger.info("Daemon stopped")

        def on_pause() -> None:
            if pause_event.is_set():
                pause_event.clear()
                logger.info("Resumed")
            else:
                pause_event.set()
                logger.info("Paused")

        def on_exit() -> None:
            shutdown_event.set()

        window._on_start = on_start
        window._on_pause = on_pause
        window._on_exit = on_exit

        logger.info("GUI ready")
        window.run()

    logger.info("Done")


if __name__ == "__main__":
    main()
