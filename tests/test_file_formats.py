from pdf_auto.core.file_formats import (
    PDF_COLUMN_LABELS,
    format_value,
    render_pdfgetx_header,
)


def _sample_md() -> dict:
    # Ordered like PDFReducer.pdfgetter_header_md(); outputtype here is the
    # configured list and must be overridden per file by the renderer.
    return {
        "version": "diffpy.pdfgetx-2.4.0",
        "dataformat": "QA",
        "backgroundfile": "",
        "outputtype": "sq, fq, gr",
        "mode": "xray",
        "composition": "Ni1.0",
        "bgscales": 0.98,
        "rpoly": 0.95,
        "qmaxinst": 29.0,
        "qmin": 0.6,
        "qmax": 22.0,
        "rmin": 0.0,
        "rmax": 100.0,
        "rstep": 0.01,
        "temperature_K": 300.0,
    }


def test_format_value_uses_g_for_numbers() -> None:
    assert format_value(29.0) == "29"
    assert format_value(0.01) == "0.01"
    assert format_value(0.0) == "0"
    assert format_value(100.0) == "100"
    assert format_value(None) == ""
    assert format_value("QA") == "QA"
    # booleans are rendered as strings, not 1/0
    assert format_value(True) == "True"


def test_gr_header_matches_expected_template() -> None:
    expected = (
        "[DEFAULT]\n"
        "\n"
        "version = diffpy.pdfgetx-2.4.0\n"
        "\n"
        "# input and output specifications\n"
        "dataformat = QA\n"
        "backgroundfile = \n"
        "outputtype = gr\n"
        "\n"
        "# PDF calculation setup\n"
        "mode = xray\n"
        "composition = Ni1.0\n"
        "bgscales = 0.98\n"
        "rpoly = 0.95\n"
        "qmaxinst = 29\n"
        "qmin = 0.6\n"
        "qmax = 22\n"
        "rmin = 0\n"
        "rmax = 100\n"
        "rstep = 0.01\n"
        "temperature_K = 300\n"
        "\n"
        "# End of config "
        "--------------------------------------------------------------\n"
        "\n"
        "#### start data\n"
        "#S 1\n"
        "#L r(\u00c5)  G(\u00c5$^{-2}$)\n"
    )
    assert render_pdfgetx_header("gr", _sample_md()) == expected


def test_separator_is_78_columns() -> None:
    header = render_pdfgetx_header("gr", _sample_md())
    sep = next(
        line for line in header.splitlines() if line.startswith("# End of config")
    )
    assert len(sep) == 78
    assert sep.startswith("# End of config ")


def test_outputtype_is_per_file() -> None:
    # md carries the configured list, but each file records its own type.
    for out_type in ("sq", "fq", "gr"):
        header = render_pdfgetx_header(out_type, _sample_md())
        assert f"outputtype = {out_type}\n" in header
        assert f"#L {PDF_COLUMN_LABELS[out_type]}\n" in header


def test_header_ends_ready_for_data_rows() -> None:
    header = render_pdfgetx_header("sq", _sample_md())
    # Ends with the #L line + newline so data rows follow directly.
    assert header.endswith("#L " + PDF_COLUMN_LABELS["sq"] + "\n")


def test_missing_version_is_omitted() -> None:
    md = _sample_md()
    del md["version"]
    header = render_pdfgetx_header("gr", md)
    assert "version =" not in header
    # Still starts with the [DEFAULT] block and the I/O section.
    assert header.startswith("[DEFAULT]\n\n# input and output specifications\n")
