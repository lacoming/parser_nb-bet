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

    # Setup logging
    logger = setup_logging(config.logging, config.files.logs_dir)
    logger.info("parser_nb-bet starting...")
    logger.info("  mode:    %s", "once" if args.once else "daemon" if args.daemon else "interactive")
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
    from src.decision.league_loader import load_league_settings
    from src.excel.writer import ExcelWriter
    from src.nb.client import NbClient
    from src.scheduler.cycle_runner import run_cycle
    from src.scheduler.msk_scheduler import MskScheduler
    from src.telegram.notifier import TelegramNotifier

    proxies = load_proxies(config.proxies.file) if config.proxies.enabled else []
    nb_client = NbClient(config=config.nb, proxy_list=proxies)
    league_settings = load_league_settings(config.files.leagues_xlsx_path)
    league_filter = LeagueFilter(settings=league_settings)
    decision_engine = DecisionEngine()
    excel_writer = ExcelWriter(output_dir=config.files.output_dir)
    telegram = TelegramNotifier(
        token=config.telegram.token,
        chat_ids=config.telegram.chat_ids,
        rate_limit=config.telegram.rate_limit_seconds,
    )

    def do_cycle() -> None:
        run_cycle(
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
        logger.info("Starting GUI mode... (TODO step 10)")

    logger.info("Done")


if __name__ == "__main__":
    main()
