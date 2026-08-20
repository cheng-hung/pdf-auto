"""ZMQ-driven Bluesky secondary (analysis) stream for PDF reduction.

This module re-emits the results of the existing stop-driven, Tiled-backed
reduction pipeline (:class:`pdf_auto.reduction.PDFReducer`) as a Bluesky
secondary document stream, using
:class:`bluesky.callbacks.stream.LiveDispatcher`.

It is intentionally kept separate from :mod:`pdf_auto.consumer`: the analysis
stream is document-oriented and meant to be driven over **ZMQ** (a
:class:`bluesky.callbacks.zmq.RemoteDispatcher`), whereas ``consumer.py`` holds
the Kafka file-writing workflow. Subscribing this dispatcher to a live ZMQ
source is left for later; :func:`run_analysis_stream_zmq` provides the wiring.

Like the rest of the beamline modules, this imports ``bluesky``/Tiled/PDFgetX at
top level and is only importable on the beamline (the ``beamline`` extra). The
pure, off-beamline-safe payload logic lives in :mod:`pdf_auto.analysis_stream`.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Iterable

from bluesky.callbacks.stream import LiveDispatcher
from bluesky.callbacks.zmq import RemoteDispatcher
from tiled.client import from_profile

from . import reduction
from .analysis_stream import (
    ANALYSIS_STREAM_NAME,
    analysis_data_keys,
    analysis_event_data,
)
from .config import DEFAULT_CONFIG_PATH
from .routing import is_dark_start, should_process_start
from .utilities import ServerState

ini_config = str(DEFAULT_CONFIG_PATH)


class PDFAnalysisDispatcher(LiveDispatcher):
    """Re-emit PDF reduction results as a Bluesky secondary (analysis) stream.

    This wraps the existing stop-driven, Tiled-backed reduction pipeline
    (:class:`pdf_auto.reduction.PDFReducer`) inside a
    :class:`bluesky.callbacks.stream.LiveDispatcher`. The reduction itself is
    unchanged: images are read from Tiled after the raw ``stop`` document, then
    integrated and PDF-reduced. Instead of only writing files and plotting, this
    dispatcher additionally emits a synthesized analysis stream so downstream
    subscribers (a Tiled writer, live plots, adaptive agents, or another ZMQ/
    Kafka analysis topic) can consume the results.

    ``LiveDispatcher`` re-emits ``start``/``stop`` itself (injecting
    ``original_run_uid`` and new uids). This subclass overrides ``start`` to run
    eligibility checks and build the reducer, and ``stop`` to run the pipeline
    and emit one analysis event carrying output file paths + scalar metadata.

    Notes
    -----
    - The base ``LiveDispatcher.event`` is a no-op here because reduction is
      stop-driven and reads full image stacks from Tiled; there is nothing
      useful to transform per raw event.
    - Payloads are paths + scalars only (see :mod:`pdf_auto.analysis_stream`);
      raw arrays are never embedded in the emitted documents.
    """

    def __init__(self, beamline_acronym: str, ini_config: str):
        super().__init__()
        self.tiled_client = from_profile(beamline_acronym)
        self.ini_config = ini_config
        self.factory_log = ServerState()
        self.img_analyzer: reduction.PDFReducer | None = None

    def start(self, doc, _md=None):
        # Reuse the same routing decision as the file-writing factory.
        self.factory_log.do_process = should_process_start(doc)

        if is_dark_start(doc):
            print("\n***** This is a DARK scan skip process data. *****\n")
        elif "original_run_uid" in doc:
            print(
                "\n***** This is a analysis scan already processed by PDFstream. *****\n"
            )
            self.factory_log.do_process = False

        if self.factory_log.do_process:
            uid = doc["uid"]
            self.img_analyzer = reduction.PDFReducer(
                uid, self.tiled_client, self.ini_config
            )
            print(f"\n{self.img_analyzer.acq_mode = }\n")

        # Re-emit the raw start as an analysis-stream start document
        # (LiveDispatcher injects a new uid + original_run_uid).
        super().start(doc, _md=_md)

    def event(self, doc, **kwargs):
        # Reduction is stop-driven and Tiled-backed; nothing to do per event.
        return doc

    def stop(self, doc, _md=None):
        if not self.factory_log.do_process or self.img_analyzer is None:
            super().stop(doc, _md=_md)
            self.factory_log.do_process = False
            self.img_analyzer = None
            return

        analyzer = self.img_analyzer

        stream_name = list(doc["num_events"].keys())
        analyzer.stream_name = stream_name

        # Wait for data to be written to the databroker, then run the pipeline.
        time.sleep(1)
        analyzer.save_processed_image()
        poni_name, mask_name = analyzer.poni_mask_fn

        iq_df, iq_fn, _unrolled = analyzer.pct_integration()
        tth_fn = analyzer.output_data_path(sub_name="tth", file_type="xy")

        output_paths: dict[str, str] = {"iq": iq_fn, "tth": tth_fn}
        scalars: dict[str, object] = {
            "poni_file": os.path.basename(poni_name),
            "mask_file": os.path.basename(mask_name),
            "stitched": analyzer.stream_length == analyzer.num_positions,
        }

        temperature = analyzer.temperature
        if isinstance(temperature, float):
            scalars["temperature"] = temperature
            scalars["temperature_unit"] = analyzer.T_unit

        if analyzer.do_reduction and analyzer.acq_mode == "PDF":
            sqfqgr_path = analyzer.get_gr(iq_df)
            output_paths.update(
                {
                    "sq": sqfqgr_path.get("sq", ""),
                    "fq": sqfqgr_path.get("fq", ""),
                    "gr": sqfqgr_path.get("gr", ""),
                }
            )
            scalars["bgscale"] = float(analyzer.pdfconfig().bgscale[0])
            scalars["backgroundfile"] = analyzer.pdfconfig_dict["backgroundfile"]

        data = analysis_event_data(
            raw_uid=analyzer.full_uid,
            acq_mode=analyzer.acq_mode,
            sample_name=analyzer.sample_name,
            detector=analyzer.detector,
            output_paths=output_paths,
            scalars=scalars,
        )

        # Emit the synthesized analysis event, then the analysis stop document.
        self.process_event(
            {"data": data, "descriptor": None, "filled": {}},
            stream_name=ANALYSIS_STREAM_NAME,
            config={"data_keys": analysis_data_keys(data)},
        )
        super().stop(doc, _md=_md)

        self.factory_log.do_process = False
        self.img_analyzer = None

    def process_event(self, doc, stream_name=ANALYSIS_STREAM_NAME, **kwargs):
        # Our synthesized event has no raw descriptor to inherit from, so seed
        # an empty one keyed by the sentinel descriptor id used below.
        self.raw_descriptors.setdefault(None, {"data_keys": {}})
        return super().process_event(doc, stream_name=stream_name, **kwargs)


def run_analysis_stream_zmq(
    beamline_acronym: str,
    ini_config: str = ini_config,
    zmq_address: str = "ipc:///var/lib/bluesky-zmq-proxy/pdf-ipc-in-ipc-out/out.sock",
    subscribers: Iterable[Callable[[str, dict], None]] | None = None,
):
    """Run the reduction as a re-emitted analysis stream over ZMQ.

    Builds a :class:`PDFAnalysisDispatcher`, attaches any provided
    ``subscribers`` (document-style callbacks ``cb(name, doc)`` such as a Tiled
    writer, a live plotter, or another publisher), subscribes the dispatcher to
    a :class:`bluesky.callbacks.zmq.RemoteDispatcher`, and starts polling.

    Parameters
    ----------
    zmq_address:
        ZMQ address of the beamline document proxy's output socket. Defaults to
        the PDF beamline proxy path used elsewhere in this package.
    subscribers:
        Optional iterable of ``cb(name, doc)`` callbacks subscribed to the
        analysis stream. If ``None``, the analysis documents are still emitted
        and schema-validated but go nowhere (useful for a smoke test).

    Notes
    -----
    Wiring the live ZMQ subscription is intentionally the last step; adjust
    ``zmq_address`` and add subscribers as downstream consumers come online.
    """
    dispatcher = PDFAnalysisDispatcher(beamline_acronym, ini_config)
    for subscriber in subscribers or ():
        dispatcher.subscribe(subscriber)

    rd = RemoteDispatcher(zmq_address)
    rd.subscribe(dispatcher)

    print("\n\n Subscribe to RemoteDispatcher and start the analysis stream \n\n")

    try:
        rd.start()
    except KeyboardInterrupt:
        print("\nExiting ZMQ analysis-stream dispatcher")
        return ()
