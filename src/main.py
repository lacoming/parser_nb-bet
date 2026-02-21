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
        logger.info("--test-telegram: will send test message (TODO step 07)")
        return

    # Run mode
    if args.once:
        logger.info("Running single cycle... (TODO step 09)")
    elif args.daemon:
        logger.info("Starting daemon mode... (TODO step 09)")
    else:
        logger.info("Starting GUI mode... (TODO step 10)")

    logger.info("boot ok")


if __name__ == "__main__":
    main()
