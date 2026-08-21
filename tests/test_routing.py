import pytest

from pdf_auto.core.routing import is_dark_start, plan_names, should_process_start


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ({"sp_plan_name": "count"}, True),
        ({"sp_plan_name": ["count"]}, True),
        ({"sp_plan_name": ("count",)}, True),
        ({"sp_plan_name": "dark_plan"}, False),
        ({"sp_plan_name": ["dark_plan"]}, False),
        ({"sp_plan_name": ["count", "take_dark"]}, False),
        ({"sp_plan_name": "count", "original_run_uid": "abc"}, False),
        ({"sp_plan_name": ["count"], "original_run_uid": "abc"}, False),
        ({}, False),
        ({"sp_plan_name": None}, False),
        ({"sp_plan_name": []}, False),
    ],
)
def test_should_process_start(message, expected: bool) -> None:
    assert should_process_start(message) is expected


def test_plan_names_ignores_non_string_sequence_items() -> None:
    assert plan_names({"sp_plan_name": ["count", None, 3]}) == ("count",)


def test_is_dark_start_supports_beamline_list_metadata() -> None:
    assert is_dark_start({"sp_plan_name": ["take_dark"]}) is True
