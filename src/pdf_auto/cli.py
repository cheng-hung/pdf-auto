"""Command-line interface for the beamline reduction workflows."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from .config import CONFIG_ENV_VAR, resolve_config_path

_CONFIG_HELP = (
    "INI configuration path. When omitted, resolution order is: "
    f"${CONFIG_ENV_VAR} env var, the beamline deployment path if present, "
    "then the packaged default template."
)


def build_parser() -> argparse.ArgumentParser:
    """Build the ``pdf-analysis`` parser without initializing beamline services."""
    parser = argparse.ArgumentParser(
        prog="pdf-analysis",
        description=(
            "Run the ZMQ-driven PDFAnalysisDispatcher that reduces runs and "
            "publishes a Bluesky 'reduced' analysis stream."
        ),
    )
    parser.add_argument(
        "beamline",
        help="Beamline acronym used as the Tiled profile name.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help=_CONFIG_HELP,
    )
    parser.add_argument(
        "--zmq-address",
        default=None,
        help=(
            "ZMQ document-proxy output socket to listen on. Overrides the "
            "[LISTEN TO] zmq_address in the INI when given."
        ),
    )
    parser.add_argument(
        "--prefix",
        default=None,
        help=(
            "RemoteDispatcher prefix filter for the listen stream. Overrides "
            "the [LISTEN TO] prefix in the INI when given."
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Start the ZMQ analysis-stream dispatcher (``pdf-analysis``)."""
    args = build_parser().parse_args(argv)

    # Import lazily so package inspection, tests, and ``--help`` stay free of
    # the beamline-only deps and the local PDFgetX wheel.
    from .callbacks.live_dispatcher import run_analysis_stream_zmq

    run_analysis_stream_zmq(
        args.beamline,
        ini_config=str(resolve_config_path(args.config)),
        zmq_address=args.zmq_address,
        prefix=args.prefix,
    )
    return 0


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
        default=None,
        help=_CONFIG_HELP,
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
    from .callbacks.save_data import run_save_data_zmq

    run_save_data_zmq(
        ini_config=str(resolve_config_path(args.config)),
        host=args.host,
        prefix=args.prefix,
    )
    return 0


def build_plot_parser() -> argparse.ArgumentParser:
    """Build the ``pdf-plot`` parser without initializing beamline services.

    Like ``pdf-save``, PlotData only subscribes to the published ``reduced``
    ZMQ stream defined by ``[PUBLISH TO]`` in the INI; no beamline acronym.
    """
    parser = argparse.ArgumentParser(
        prog="pdf-plot",
        description=(
            "Run the PlotData callback against the published 'reduced' "
            "ZMQ stream, drawing image/I(Q)/S(Q)/F(Q)/G(r) figures."
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help=_CONFIG_HELP,
    )
    parser.add_argument(
        "--host",
        default=None,
        help=(
            "ZMQ proxy output socket to subscribe to. Overrides the "
            "[PUBLISH TO] subscribe_host in the INI when given."
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


def plot_main(argv: Sequence[str] | None = None) -> int:
    """Console-script entry point for the ``pdf-plot`` PlotData subscriber."""
    args = build_plot_parser().parse_args(argv)

    # Import lazily so package inspection and ``--help`` stay free of the
    # beamline-only deps (bluesky/pyFAI/matplotlib GUI).
    from .callbacks.plot_callback import run_plot_zmq

    run_plot_zmq(
        ini_config=str(resolve_config_path(args.config)),
        host=args.host,
        prefix=args.prefix,
    )
    return 0
