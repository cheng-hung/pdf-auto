"""Pure helpers for building the PDF analysis secondary stream.

This module is import-safe off-beamline (no ``bluesky``/``event_model``/Tiled/
``pyFAI`` imports; only ``numpy``, a base dependency). It assembles the plain
dictionaries describing the processed-data event that
:class:`pdf_auto.callbacks.live_dispatcher.PDFAnalysisDispatcher` re-emits after a run's
``stop`` document.

Keeping this logic here lets the offline test suite verify the exact shape and
contents of the analysis events without any beamline services. The beamline-only
glue (subscribing to the raw stream, running :class:`pdf_auto.reduction.reduction.PDFReducer`,
publishing over ZMQ) lives in :mod:`pdf_auto.callbacks.live_dispatcher`, and the file
writing lives in :mod:`pdf_auto.callbacks.save_data`.

Payload convention: the ``reduced`` event carries **the reduced arrays inline**
(2D image, integration cake, 1D q/I and tth/I columns, and the S(Q)/F(Q)/G(r)
pdfgetter) plus the target output paths and header metadata, so a downstream
:class:`pdf_auto.callbacks.save_data.SaveData` callback can persist every product without
touching Tiled or re-running the pipeline. Scalars/paths are still included for
lightweight subscribers (indexers, plotters) that do not need the raw arrays.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

# Stream name used for the synthesized analysis events. Kept as a module
# constant so the dispatcher, tests, and any downstream consumers agree.
ANALYSIS_STREAM_NAME = "pdf_analysis"


def analysis_event_data(
    *,
    raw_uid: str,
    acq_mode: str,
    sample_name: str,
    detector: str,
    output_paths: Mapping[str, str],
    scalars: Mapping[str, Any] | None = None,
    arrays: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the ``data`` dict for one analysis (``reduced``) event document.

    Parameters
    ----------
    raw_uid:
        The original (raw) run start uid this analysis was derived from.
    acq_mode:
        ``"PDF"``, ``"XRD"``, ``"SAXS"``, or a fallback classification.
    sample_name:
        Sample name copied from the raw start document.
    detector:
        Detector name copied from the raw start document.
    output_paths:
        Mapping of logical output name to filesystem path, e.g.
        ``{"iq": ..., "tth": ..., "img": ..., "sq": ..., "fq": ..., "gr": ...}``.
        Keys are emitted as ``<key>_file`` data keys. ``None``/empty values are
        skipped so absent products (e.g. ``gr`` on an XRD run) are omitted.
    scalars:
        Optional scalar/string metadata (temperature, ``bgscale``, mask/poni
        names, etc.).
    arrays:
        Optional mapping of ``<name> -> array-like`` reduced products carried
        inline for :class:`pdf_auto.callbacks.save_data.SaveData` (e.g. ``image``,
        ``cake``, ``q``, ``iq``, ``tth``). Values are kept as-is (numpy arrays);
        ``None`` values are skipped.

    Returns
    -------
    dict
        A ``data`` mapping suitable for a Bluesky event document, mixing string
        paths, scalars, and inline arrays.
    """
    data: dict[str, Any] = {
        "raw_uid": raw_uid,
        "acq_mode": acq_mode,
        "sample_name": sample_name,
        "detector": detector,
    }

    for name, path in output_paths.items():
        if path:
            data[f"{name}_file"] = str(path)

    if scalars:
        for key, value in scalars.items():
            if value is not None:
                data[key] = value

    if arrays:
        for key, value in arrays.items():
            if value is not None:
                data[key] = value

    return data


def _dtype_and_shape(value: Any) -> tuple[str, list[int]]:
    """Return the event-model ``(dtype, shape)`` for a single value."""
    if isinstance(value, str):
        return "string", []
    if isinstance(value, bool):
        return "boolean", []
    if isinstance(value, (int, float)):
        return "number", []
    # Array-like (numpy array, list, dataframe-with-shape): describe as array.
    shape = getattr(value, "shape", None)
    if shape is not None:
        return "array", [int(dim) for dim in shape]
    if isinstance(value, (list, tuple)):
        return "array", list(np.shape(value))
    # Fall back to string for anything unrecognized.
    return "string", []


def analysis_data_keys(data: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Return an event-model ``data_keys`` description for ``data``.

    Handles inline arrays (numpy arrays, lists, dataframes) in addition to
    strings and plain scalars, so the ``reduced`` event's descriptor is
    deterministic and unit-testable.
    """
    keys: dict[str, dict[str, Any]] = {}
    for key, value in data.items():
        dtype, shape = _dtype_and_shape(value)
        keys[key] = {"dtype": dtype, "shape": shape, "source": "pdf_auto.analysis"}
    return keys
