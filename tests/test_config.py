from configparser import ConfigParser
from pathlib import Path

from pdf_auto import config


def test_explicit_path_wins(monkeypatch) -> None:
    monkeypatch.setenv(config.CONFIG_ENV_VAR, "/tmp/env.ini")
    assert config.resolve_config_path("/tmp/explicit.ini") == Path("/tmp/explicit.ini")


def test_env_var_used_when_no_explicit(monkeypatch) -> None:
    monkeypatch.setenv(config.CONFIG_ENV_VAR, "/tmp/env.ini")
    assert config.resolve_config_path() == Path("/tmp/env.ini")


def test_falls_back_to_packaged_default(monkeypatch) -> None:
    monkeypatch.delenv(config.CONFIG_ENV_VAR, raising=False)
    # Force the beamline path to look absent so resolution reaches the package.
    monkeypatch.setattr(config, "DEFAULT_CONFIG_PATH", Path("/nonexistent/pdf.ini"))

    resolved = config.resolve_config_path()

    assert resolved == config.packaged_config_path()
    assert resolved.exists()
    assert resolved.name == "pdf_auto_config.ini"


def test_beamline_path_used_when_it_exists(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv(config.CONFIG_ENV_VAR, raising=False)
    fake_beamline = tmp_path / "pdf_auto_config.ini"
    fake_beamline.write_text("[topics]\nraw_db = pdf\n")
    monkeypatch.setattr(config, "DEFAULT_CONFIG_PATH", fake_beamline)

    assert config.resolve_config_path() == fake_beamline


def test_packaged_default_is_valid_ini() -> None:
    parser = ConfigParser()
    parser.read(config.packaged_config_path())

    # Structural sections and stable ZMQ wiring are present.
    for section in ("topics", "LISTEN TO", "PUBLISH TO", "PATH", "INTEGRATION"):
        assert parser.has_section(section)
    # Publisher/subscriber remain distinct proxy sockets.
    assert parser.get("PUBLISH TO", "publish_host") != parser.get(
        "PUBLISH TO", "subscribe_host"
    )
    # Site-specific path is a placeholder, not a real beamline root.
    assert parser.get("PATH", "user_data").startswith("/PATH/TO")
