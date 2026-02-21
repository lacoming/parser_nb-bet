"""
parser_nb-bet — entry point.
Usage:
    python src/main.py --once
    python src/main.py --daemon
    python src/main.py --dry-run
"""

import argparse
import sys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="parser_nb-bet",
        description="NB-bet results parser and Kush bet placer",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="Run one cycle and exit")
    mode.add_argument("--daemon", action="store_true", help="Run on schedule (daemon mode)")
    parser.add_argument("--dry-run", action="store_true", help="No real bets placed")
    parser.add_argument("--config", default="config.json", help="Path to config file")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Stub: will be replaced in step 04 (config) and step 12 (scheduler)
    print("parser_nb-bet starting...")
    print(f"  mode:    {'once' if args.once else 'daemon' if args.daemon else 'interactive'}")
    print(f"  dry-run: {args.dry_run}")
    print(f"  config:  {args.config}")
    print("boot ok")


if __name__ == "__main__":
    main()
