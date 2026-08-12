import tomllib
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).parents[1]


def test_pixi_task_launches_package_directly() -> None:
    with (REPOSITORY_ROOT / "pixi.toml").open("rb") as stream:
        pixi_config = tomllib.load(stream)

    task = pixi_config["feature"]["terminal"]["tasks"]["pdf_auto"]

    assert task["cmd"] == "python -m pdf_auto pdf"
    assert task["env"]["PYTHONPATH"].endswith("/pdf-auto/src")


def test_default_ini_file_exists() -> None:
    assert (REPOSITORY_ROOT / "pdf_auto_config.ini").is_file()
