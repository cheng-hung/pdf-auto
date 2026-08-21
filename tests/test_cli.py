from pathlib import Path

from pdf_auto.cli import build_parser, build_plot_parser, build_save_parser
from pdf_auto.config import DEFAULT_CONFIG_PATH


def test_cli_uses_beamline_deployment_config_by_default() -> None:
    args = build_parser().parse_args(["pdf"])

    assert args.beamline == "pdf"
    assert args.config == DEFAULT_CONFIG_PATH
    assert args.config.name == "pdf_auto_config.ini"


def test_cli_accepts_config_override() -> None:
    args = build_parser().parse_args(["pdf", "--config", "/tmp/pdf-auto.ini"])

    assert args.config == Path("/tmp/pdf-auto.ini")


def test_cli_analysis_defaults_to_ini_source_of_truth() -> None:
    args = build_parser().parse_args(["pdf"])

    # No --mode flag anymore; analysis is the only reduction entrypoint.
    assert not hasattr(args, "mode")
    # Address/prefix default to None so the INI [LISTEN TO] section is the
    # source of truth unless explicitly overridden on the command line.
    assert args.zmq_address is None
    assert args.prefix is None


def test_cli_accepts_zmq_overrides() -> None:
    args = build_parser().parse_args(
        ["pdf", "--zmq-address", "tcp://localhost:5578", "--prefix", "raw"]
    )

    assert args.zmq_address == "tcp://localhost:5578"
    assert args.prefix == "raw"


def test_save_parser_defaults_to_ini_source_of_truth() -> None:
    args = build_save_parser().parse_args([])

    # No beamline acronym; host/prefix default to None so [PUBLISH TO] is used.
    assert args.config == DEFAULT_CONFIG_PATH
    assert args.host is None
    assert args.prefix is None


def test_save_parser_accepts_overrides() -> None:
    args = build_save_parser().parse_args(
        ["--config", "/tmp/x.ini", "--host", "tcp://h:1", "--prefix", "reduced"]
    )

    assert args.config == Path("/tmp/x.ini")
    assert args.host == "tcp://h:1"
    assert args.prefix == "reduced"


def test_plot_parser_defaults_to_ini_source_of_truth() -> None:
    args = build_plot_parser().parse_args([])

    assert args.config == DEFAULT_CONFIG_PATH
    assert args.host is None
    assert args.prefix is None


def test_plot_parser_accepts_overrides() -> None:
    args = build_plot_parser().parse_args(
        ["--config", "/tmp/x.ini", "--host", "tcp://h:1", "--prefix", "reduced"]
    )

    assert args.config == Path("/tmp/x.ini")
    assert args.host == "tcp://h:1"
    assert args.prefix == "reduced"
