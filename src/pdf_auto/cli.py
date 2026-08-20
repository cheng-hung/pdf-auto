"""Command-line interface for the beamline reduction workflows."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from .config import DEFAULT_CONFIG_PATH


def build_parser() -> argparse.ArgumentParser:
    """Build the parser without initializing beamline services."""
    parser = argparse.ArgumentParser(
        prog="pdf-auto",
        description="Run the automatic PDF beamline reduction workflow.",
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
    parser.add_argument(
        "--mode",
        choices=("consumer", "analysis"),
        default="consumer",
        help=(
            "Which workflow to run: 'consumer' (default) runs the Kafka "
            "file-writing reduction; 'analysis' runs the ZMQ-driven "
            "PDFAnalysisDispatcher that re-emits a Bluesky analysis stream."
        ),
    )
    parser.add_argument(
        "--zmq-address",
        default=None,
        help=(
            "ZMQ document-proxy output socket for --mode analysis. Overrides "
            "the [LISTEN TO] zmq_address in the INI when given."
        ),
    )
    parser.add_argument(
        "--prefix",
        default=None,
        help=(
            "RemoteDispatcher prefix filter for --mode analysis. Overrides the "
            "[LISTEN TO] prefix in the INI when given."
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Start the selected beamline workflow."""
    args = build_parser().parse_args(argv)

    # Keep package inspection, tests, and ``--help`` independent of beamline
    # services and the local PDFgetX wheel by importing lazily per mode.
    if args.mode == "analysis":
        from .live_dispatcher import run_analysis_stream_zmq

        run_analysis_stream_zmq(
            args.beamline,
            ini_config=str(args.config),
            zmq_address=args.zmq_address,
            prefix=args.prefix,
        )
        return 0

    from .consumer import run_kafka_consumer

    run_kafka_consumer(args.beamline, ini_config=str(args.config))
    return 0


def analysis_main(argv: Sequence[str] | None = None) -> int:
    """Console-script entry point that defaults to the analysis mode.

    Equivalent to ``pdf-auto <beamline> --mode analysis`` but exposed as its own
    ``pdf-analysis`` script and Pixi task. Any explicit ``--mode`` on the
    command line still wins.
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    if not any(arg == "--mode" or arg.startswith("--mode=") for arg in argv):
        argv = [*argv, "--mode", "analysis"]
    return main(argv)


def build_save_parser() -> argparse.ArgumentParser:
    """Build the ``pdf-save`` parser without initializing beamline services.

    Unlike the reduction workflows, SaveData needs no beamline acronym: it only
    subscribes to the published ``reduced`` ZMQ stream defined by ``[PUBLISH
    TO]`` in the INI.
    """
    parser = argparse.ArgumentParser(
        prog="pdf-save",
        description=(
            "Run the SaveData callback against the published 'reduced' "
            "ZMQ stream, writing tiff/iq/tth/sq/fq/gr files."
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help=f"INI configuration path (default: {DEFAULT_CONFIG_PATH}).",
    )
    parser.add_argument(
        "--host",
        default=None,
        help=(
            "ZMQ proxy output socket to subscribe to. Overrides the "
            "[PUBLISH TO] host in the INI when given."
        ),
    )
    parser.add_argument(
        "--prefix",
        default=None,
        help=(
            "RemoteDispatcher prefix filter. Overrides the [PUBLISH TO] "
            "prefix in the INI when given."
        ),
    )
    return parser


def save_main(argv: Sequence[str] | None = None) -> int:
    """Console-script entry point for the ``pdf-save`` SaveData subscriber."""
    args = build_save_parser().parse_args(argv)

    # Import lazily so package inspection and ``--help`` stay free of the
    # beamline-only deps (bluesky/pdfstream/tifffile).
    from .save_data import run_save_data_zmq

    run_save_data_zmq(
        ini_config=str(args.config),
        host=args.host,
        prefix=args.prefix,
    )
    return 0
