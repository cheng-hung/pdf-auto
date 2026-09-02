import tomllib
from configparser import ConfigParser
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).parents[1]


def test_pixi_analysis_task_launches_package_directly() -> None:
    with (REPOSITORY_ROOT / "pixi.toml").open("rb") as stream:
        pixi_config = tomllib.load(stream)

    task = pixi_config["tasks"]["pdf-analysis"]

    assert task["cmd"] == "python -m pdf_auto pdf"
    assert task["env"]["MPLBACKEND"] == "qtagg"
    # pdf-auto is installed as a dependency, so no PYTHONPATH is needed.
    assert "PYTHONPATH" not in task["env"]


def test_pixi_has_no_kafka_task() -> None:
    with (REPOSITORY_ROOT / "pixi.toml").open("rb") as stream:
        pixi_config = tomllib.load(stream)

    # The Kafka file-writing consumer was removed from this branch.
    assert "pdf_auto" not in pixi_config["tasks"]
    assert set(pixi_config["tasks"]) == {"pdf-analysis", "pdf-save", "pdf-plot"}


def test_pixi_save_task_launches_save_subcommand() -> None:
    with (REPOSITORY_ROOT / "pixi.toml").open("rb") as stream:
        pixi_config = tomllib.load(stream)

    task = pixi_config["tasks"]["pdf-save"]

    assert task["cmd"] == "python -m pdf_auto save"
    assert task["env"]["MPLBACKEND"] == "qtagg"
    assert "PYTHONPATH" not in task["env"]


def test_pixi_plot_task_launches_plot_subcommand() -> None:
    with (REPOSITORY_ROOT / "pixi.toml").open("rb") as stream:
        pixi_config = tomllib.load(stream)

    task = pixi_config["tasks"]["pdf-plot"]

    assert task["cmd"] == "python -m pdf_auto plot"
    assert task["env"]["MPLBACKEND"] == "qtagg"
    assert "PYTHONPATH" not in task["env"]


def test_pixi_installs_pdf_auto_from_git_branch() -> None:
    with (REPOSITORY_ROOT / "pixi.toml").open("rb") as stream:
        pixi_config = tomllib.load(stream)

    dep = pixi_config["pypi-dependencies"]["pdf-auto"]

    assert dep["git"].endswith("pdf-auto.git")
    assert dep["branch"] == "Live_dispatcher"


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
        # databroker provides Tiled's BlueskyRun structure clients (the
        # reducer needs run.start/.stop); do not drop it with nslsii.
        "databroker",
        "event-model",
        "matplotlib-base",
        "numpy",
        "pandas",
        "pyside6",
        "pyfai",
        "python",
        "scipy",
        "tifffile",
        "tiled-client",
    } <= dependencies

    # Kafka was removed from this branch.
    assert "bluesky-kafka" not in dependencies
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
    # Publisher (IN) and subscriber (OUT) must be distinct proxy sockets.
    publish_host = parser.get("PUBLISH TO", "publish_host")
    subscribe_host = parser.get("PUBLISH TO", "subscribe_host")
    assert publish_host
    assert subscribe_host
    assert publish_host != subscribe_host
    assert parser.get("PUBLISH TO", "prefix") == "reduced"
