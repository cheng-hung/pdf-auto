from pathlib import Path

from pdf_auto.cli import build_parser
from pdf_auto.config import DEFAULT_CONFIG_PATH


def test_cli_uses_beamline_deployment_config_by_default() -> None:
    args = build_parser().parse_args(["pdf"])

    assert args.beamline == "pdf"
    assert args.config == DEFAULT_CONFIG_PATH
    assert args.config.name == "pdf_auto_config.ini"


def test_cli_accepts_config_override() -> None:
    args = build_parser().parse_args(["pdf", "--config", "/tmp/pdf-auto.ini"])

    assert args.config == Path("/tmp/pdf-auto.ini")
