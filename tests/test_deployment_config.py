import tomllib
from configparser import ConfigParser
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).parents[1]


def test_pixi_task_launches_package_directly() -> None:
    with (REPOSITORY_ROOT / "pixi.toml").open("rb") as stream:
        pixi_config = tomllib.load(stream)

    task = pixi_config["tasks"]["pdf_auto"]

    assert task["cmd"] == "python -m pdf_auto pdf"
    assert task["env"]["PYTHONPATH"].endswith("/pdf-auto/src")
    assert task["env"]["MPLBACKEND"] == "qtagg"


def test_pixi_analysis_task_launches_analysis_mode() -> None:
    with (REPOSITORY_ROOT / "pixi.toml").open("rb") as stream:
        pixi_config = tomllib.load(stream)

    task = pixi_config["tasks"]["pdf-analysis"]

    assert task["cmd"] == "python -m pdf_auto pdf --mode analysis"
    assert task["env"]["PYTHONPATH"].endswith("/pdf-auto/src")
    assert task["env"]["MPLBACKEND"] == "qtagg"


def test_pixi_save_task_launches_save_subcommand() -> None:
    with (REPOSITORY_ROOT / "pixi.toml").open("rb") as stream:
        pixi_config = tomllib.load(stream)

    task = pixi_config["tasks"]["pdf-save"]

    assert task["cmd"] == "python -m pdf_auto save"
    assert task["env"]["PYTHONPATH"].endswith("/pdf-auto/src")
    assert task["env"]["MPLBACKEND"] == "qtagg"


def test_pixi_uses_one_default_environment() -> None:
    with (REPOSITORY_ROOT / "pixi.toml").open("rb") as stream:
        pixi_config = tomllib.load(stream)

    assert "feature" not in pixi_config
    assert "environments" not in pixi_config


def test_pixi_declares_active_runtime_dependencies() -> None:
    with (REPOSITORY_ROOT / "pixi.toml").open("rb") as stream:
        pixi_config = tomllib.load(stream)

    dependencies = set(pixi_config["dependencies"])
    assert {
        "bluesky-base",
        "bluesky-kafka",
        "event-model",
        "matplotlib-base",
        "nslsii",
        "numpy",
        "pandas",
        "pyside6",
        "pyfai",
        "python",
        "scipy",
        "tifffile",
        "tiled-client",
    } <= dependencies

    assert "bluesky-queueserver" not in dependencies
    assert "ophyd" not in dependencies
    assert "pymatgen" not in dependencies


def test_default_ini_file_exists() -> None:
    assert (REPOSITORY_ROOT / "pdf_auto_config.ini").is_file()


def test_default_ini_declares_listen_to_section() -> None:
    parser = ConfigParser()
    parser.read(REPOSITORY_ROOT / "pdf_auto_config.ini")

    assert parser.has_section("LISTEN TO")
    assert parser.get("LISTEN TO", "zmq_address")
    assert parser.get("LISTEN TO", "prefix") == "raw"


def test_default_ini_declares_publish_to_section() -> None:
    parser = ConfigParser()
    parser.read(REPOSITORY_ROOT / "pdf_auto_config.ini")

    assert parser.has_section("PUBLISH TO")
    assert parser.get("PUBLISH TO", "host")
    assert parser.get("PUBLISH TO", "prefix") == "reduced"
