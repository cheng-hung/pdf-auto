"""Pure formatters for PDFgetX S(Q)/F(Q)/G(r) output files.

Off-beamline-safe (no ``bluesky``/``diffpy``/``pyFAI`` imports), so the header
format is unit-testable in the offline suite. :mod:`pdf_auto.callbacks.save_data`
uses these to write ``.sq``/``.fq``/``.gr`` files whose header mirrors the native
``diffpy.pdfgetx`` output::

    [DEFAULT]

    version = diffpy.pdfgetx-2.4.0

    # input and output specifications
    dataformat = QA
    backgroundfile =
    outputtype = gr

    # PDF calculation setup
    mode = xray
    composition = Ni1.0
    bgscales = 0.98
    ...
    rstep = 0.01
    temperature_K = 300

    # End of config --------------------------------------------------------------

    #### start data
    #S 1
    #L r(Å)  G(Å$^{-2}$)
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

# Column labels per output type (two spaces between the two column labels).
PDF_COLUMN_LABELS: dict[str, str] = {
    "sq": "Q(\u00c5$^{-1}$)  S(Q)",
    "fq": "Q(\u00c5$^{-1}$)  F(\u00c5$^{-1}$)",
    "gr": "r(\u00c5)  G(\u00c5$^{-2}$)",
    # Fallback for a configured ``iq`` product.
    "iq": "Q(\u00c5$^{-1}$)  I(Q)",
}

# Keys rendered under "# input and output specifications" (in this order); every
# other key falls under "# PDF calculation setup".
_IO_KEYS = ("dataformat", "backgroundfile", "outputtype")

# The "# End of config" separator is padded with dashes to 78 columns.
_SEPARATOR_WIDTH = 78
_END_OF_CONFIG = "# End of config "
_END_OF_CONFIG_LINE = _END_OF_CONFIG + "-" * (_SEPARATOR_WIDTH - len(_END_OF_CONFIG))


def format_value(value: Any) -> str:
    """Render a config value the way ``diffpy.pdfgetx`` does.

    Floats/ints use ``%g`` (so ``29.0`` -> ``29`` and ``0.01`` -> ``0.01``);
    ``None`` renders as an empty string; everything else is passed through as
    ``str``. Booleans are intentionally treated as strings (``True``/``False``).
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        return f"{value:g}"
    return str(value)


def render_pdfgetx_header(out_type: str, md: Mapping[str, Any]) -> str:
    """Return the full header block for a PDFgetX ``out_type`` output file.

    Parameters
    ----------
    out_type:
        The product type for this file (``sq``/``fq``/``gr``/``iq``); its own
        value overrides any ``outputtype`` in ``md`` so each file records its own
        type.
    md:
        Ordered mapping of config key -> value (see
        :meth:`pdf_auto.reduction.reduction.PDFReducer.pdfgetter_header_md`).

    Returns
    -------
    str
        The header text, ending with a trailing newline so data rows follow
        directly.
    """
    # Per-file outputtype overrides whatever the config list carried.
    items = dict(md)
    items["outputtype"] = out_type

    io_lines: list[str] = []
    calc_lines: list[str] = []
    version = items.pop("version", None)

    for key, value in items.items():
        line = f"{key} = {format_value(value)}"
        if key in _IO_KEYS:
            io_lines.append((key, line))
        else:
            calc_lines.append(line)

    # Keep the I/O section in the canonical order regardless of md ordering.
    io_ordered = [
        line for k in _IO_KEYS for (kk, line) in io_lines if kk == k
    ]

    label = PDF_COLUMN_LABELS.get(out_type, "x  y")

    parts: list[str] = ["[DEFAULT]", ""]
    if version is not None:
        parts += [f"version = {format_value(version)}", ""]
    parts += ["# input and output specifications", *io_ordered, ""]
    parts += ["# PDF calculation setup", *calc_lines, ""]
    parts += [_END_OF_CONFIG_LINE, ""]
    parts += ["#### start data", "#S 1", f"#L {label}"]

    return "\n".join(parts) + "\n"
