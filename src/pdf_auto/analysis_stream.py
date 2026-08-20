"""Pure helpers for building the PDF analysis secondary stream.

This module is import-safe off-beamline (no ``bluesky``/``event_model``/Tiled/
``pyFAI`` imports). It only assembles plain dictionaries describing the
processed-data event that a :class:`~bluesky.callbacks.stream.LiveDispatcher`
subclass re-emits after a run's ``stop`` document.

Keeping this logic here lets the offline test suite verify the exact shape and
contents of the analysis events without any beamline services. The beamline-only
glue (subscribing to the raw stream, running :class:`pdf_auto.reduction.PDFReducer`,
and emitting the documents) lives in :mod:`pdf_auto.consumer`.

Payload convention (per the beamline decision): analysis events carry output
*file paths* and *scalar metadata* only -- never raw images or full I(Q)/G(r)
arrays. Downstream subscribers that need the arrays read them from the emitted
paths (or from Tiled via the referenced uids).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

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
) -> dict[str, Any]:
    """Build the ``data`` dict for one analysis event document.

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
        skipped so absent products (e.g. ``gr`` on an XRD run) are simply not
        present.
    scalars:
        Optional extra scalar metadata (temperature, ``bgscale``, mask/poni
        names, etc.). Values must be JSON/schema friendly scalars or strings.

    Returns
    -------
    dict
        A flat ``data`` mapping suitable for a Bluesky event document. All array
        payloads are intentionally excluded; only paths and scalars are present.
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

    return data


def analysis_data_keys(data: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Return an event-model ``data_keys`` description for ``data``.

    ``LiveDispatcher.process_event`` can synthesize descriptors on its own, but
    building the description here keeps it deterministic and unit-testable.
    Every value in the analysis event is a string or a plain scalar, so the
    dtype mapping is simple and stable.
    """
    keys: dict[str, dict[str, Any]] = {}
    for key, value in data.items():
        if isinstance(value, str):
            dtype = "string"
        elif isinstance(value, bool):
            dtype = "boolean"
        elif isinstance(value, (int, float)):
            dtype = "number"
        else:
            # Fall back to string; the dispatcher stringifies unknowns.
            dtype = "string"
        keys[key] = {"dtype": dtype, "shape": [], "source": "pdf_auto.analysis"}
    return keys
