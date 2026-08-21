from pathlib import Path

import pytest

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


def test_cli_defaults_to_consumer_mode() -> None:
    args = build_parser().parse_args(["pdf"])

    assert args.mode == "consumer"
    # Address/prefix default to None so the INI [LISTEN TO] section is the
    # source of truth unless explicitly overridden on the command line.
    assert args.zmq_address is None
    assert args.prefix is None


def test_cli_accepts_analysis_mode_and_zmq_override() -> None:
    args = build_parser().parse_args(
        [
            "pdf",
            "--mode",
            "analysis",
            "--zmq-address",
            "tcp://localhost:5578",
            "--prefix",
            "raw",
        ]
    )

    assert args.mode == "analysis"
    assert args.zmq_address == "tcp://localhost:5578"
    assert args.prefix == "raw"


def test_cli_rejects_unknown_mode() -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(["pdf", "--mode", "bogus"])


def test_analysis_main_injects_analysis_mode(monkeypatch) -> None:
    from pdf_auto import cli

    captured: dict[str, list[str]] = {}

    def fake_main(argv):
        captured["argv"] = list(argv)
        return 0

    monkeypatch.setattr(cli, "main", fake_main)

    assert cli.analysis_main(["pdf"]) == 0
    assert captured["argv"] == ["pdf", "--mode", "analysis"]


def test_analysis_main_preserves_explicit_mode(monkeypatch) -> None:
    from pdf_auto import cli

    captured: dict[str, list[str]] = {}
    monkeypatch.setattr(cli, "main", lambda argv: captured.update(argv=list(argv)))

    cli.analysis_main(["pdf", "--mode", "consumer"])
    assert captured["argv"] == ["pdf", "--mode", "consumer"]


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
