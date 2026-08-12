"""Command-line interface for the beamline reduction consumer."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from .config import DEFAULT_CONFIG_PATH


def build_parser() -> argparse.ArgumentParser:
    """Build the parser without initializing beamline services."""
    parser = argparse.ArgumentParser(
        prog="pdf-auto",
        description="Run the automatic PDF beamline reduction consumer.",
    )
    parser.add_argument(
        "beamline",
        help="Beamline acronym used for both Kafka and the Tiled profile.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help=f"INI configuration path (default: {DEFAULT_CONFIG_PATH}).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Start the Kafka consumer for a beamline."""
    args = build_parser().parse_args(argv)

    # Keep package inspection, tests, and ``--help`` independent of beamline
    # services and the local PDFgetX wheel.
    from .consumer import run_kafka_consumer

    run_kafka_consumer(args.beamline, ini_config=str(args.config))
    return 0
