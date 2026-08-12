import pytest

from pdf_auto.routing import should_process_start


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ({"sp_plan_name": "count"}, True),
        ({"sp_plan_name": "dark_plan"}, False),
        ({"sp_plan_name": "count", "original_run_uid": "abc"}, False),
        ({}, False),
        ({"sp_plan_name": None}, False),
    ],
)
def test_should_process_start(message, expected: bool) -> None:
    assert should_process_start(message) is expected
