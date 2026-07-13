"""Command-line interface."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from autoairac import __version__
from autoairac.config import load_config
from autoairac.orchestrator import AutoAIRACOrchestrator


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="autoairac",
        description="Check AIRAC expiry, download updates via qBittorrent, and install.",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=Path("config.yaml"),
        help="Path to config.yaml (default: ./config.yaml)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check expiry only; do not search, download, or install.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Treat all enabled simulators as expired and fetch the current cycle.",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Run continuously at the interval from config.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config = load_config(args.config)
    orchestrator = AutoAIRACOrchestrator(config)

    if args.watch:
        interval = max(config.watch_interval_minutes, 1) * 60
        logging.info("Watch mode — interval %s minute(s).", config.watch_interval_minutes)
        while True:
            result = orchestrator.run(dry_run=args.dry_run, force=args.force)
            logging.info(result.message)
            time.sleep(interval)
        return 0

    result = orchestrator.run(dry_run=args.dry_run, force=args.force)
    print(result.message)
    for status in result.checked:
        print(f"  [{status.simulator_id}] {status.message}")
    return 0 if result.skipped or all(r.success for r in result.install_results) else 1


if __name__ == "__main__":
    sys.exit(main())