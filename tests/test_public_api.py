from pdf_auto.core.utilities import (
    AutoBackground,
    ServerState,
    auto_bkg,
    get_header_rows,
    get_HeaderRows,
    server_log,
)


def test_legacy_utility_names_are_compatible() -> None:
    assert server_log is ServerState
    assert auto_bkg is AutoBackground
    assert get_HeaderRows is get_header_rows
