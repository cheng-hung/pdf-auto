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
from configparser import ConfigParser

from bluesky.callbacks.stream import LiveDispatcher
from bluesky.callbacks.zmq import Publisher, RemoteDispatcher
from tiled.client import from_profile

from . import reduction
from .analysis_stream import (
    ANALYSIS_STREAM_NAME,
    analysis_data_keys,
    analysis_event_data,
)
from .config import DEFAULT_CONFIG_PATH
from .routing import is_dark_start, should_process_start
from .save_data import read_publish_config
from .utilities import ServerState

ini_config = str(DEFAULT_CONFIG_PATH)

# Final fallbacks used when the INI has no ``[LISTEN TO]`` section and no
# explicit override is passed. ``DEFAULT_ZMQ_ADDRESS`` is shared with the CLI.
DEFAULT_ZMQ_ADDRESS = "ipc:///var/lib/bluesky-zmq-proxy/pdf-ipc-in-ipc-out/out.sock"
DEFAULT_PREFIX = "raw"


def read_listen_config(ini_config: str) -> tuple[str, bytes]:
    """Read the ZMQ ``zmq_address`` and ``prefix`` from ``[LISTEN TO]``.

    The ``prefix`` is returned as ``bytes`` because
    :class:`bluesky.callbacks.zmq.RemoteDispatcher` expects a bytes prefix
    filter. Missing keys or a missing section fall back to the module defaults.
    """
    parser = ConfigParser()
    parser.read(ini_config)
    zmq_address = parser.get(
        "LISTEN TO", "zmq_address", fallback=DEFAULT_ZMQ_ADDRESS
    )
    prefix = parser.get("LISTEN TO", "prefix", fallback=DEFAULT_PREFIX)
    return zmq_address, prefix.encode()


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
    - This dispatcher is *compute-only*: it publishes the reduced arrays, target
      paths, and header metadata inline (see :mod:`pdf_auto.analysis_stream`) and
      performs no file I/O. Writing is done by :class:`pdf_auto.save_data.SaveData`.
    """

    def __init__(self, beamline_acronym: str, ini_config: str):
        super().__init__()
        self.tiled_client = from_profile(beamline_acronym)
        self.ini_config = ini_config
        self.factory_log = ServerState()
        self.img_analyzer: reduction.PDFReducer | None = None

    def emit(self, name, doc):
        """Emit a document to subscribers, skipping strict schema validation.

        The base :class:`~bluesky.callbacks.stream.LiveDispatcher.emit` calls
        ``schema_validators[name].validate(doc)`` *before* dispatching. Our
        reduced events carry inline numpy arrays and dict metadata
        (``image``, ``cake``, ``pdf_arrays``, ``integration_md``, ...) that do
        not satisfy the strict event-model ``event``/``descriptor`` schemas, so
        validation raises and the document is never dispatched to the Publisher
        or any subscriber. We bypass validation and dispatch directly, with a
        loud print so emission is observable and any dispatch error surfaces.
        """
        name_str = getattr(name, "name", str(name))
        try:
            self.dispatcher.process(name, doc)
            print(f"[EMIT] dispatched {name_str} document.\n", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(
                f"[EMIT][ERROR] failed to dispatch {name_str} document: "
                f"{exc!r}\n",
                flush=True,
            )
            raise

    def start(self, doc, _md=None):
        # Reuse the same routing decision as the file-writing factory.
        self.factory_log.do_process = should_process_start(doc)

        print(
            "\n==================== [START] new run received "
            f"(uid={doc.get('uid')}) ====================\n",
            flush=True,
        )

        if is_dark_start(doc):
            print("\n***** This is a DARK scan; skip processing. *****\n", flush=True)
            self.factory_log.do_process = False

        elif "original_run_uid" in doc:
            print(
                "\n***** This is an analysis scan already processed by "
                "PDFstream; skip. *****\n",
                flush=True,
            )
            self.factory_log.do_process = False

        if self.factory_log.do_process:
            uid = doc["uid"]
            print(
                f"\n[START] Data scan accepted. Loading run {uid} from Tiled "
                "and building the reducer...\n",
                flush=True,
            )
            self.img_analyzer = reduction.PDFReducer(
                uid, self.tiled_client, self.ini_config
            )
            print(
                f"\n[START] Reducer ready. acq_mode = {self.img_analyzer.acq_mode}. "
                "Waiting for the stop document to reduce.\n",
                flush=True,
            )
        else:
            print("\n[START] Run will be skipped (not eligible).\n", flush=True)

        # Re-emit the raw start as an analysis-stream start document
        # (LiveDispatcher injects a new uid + original_run_uid).
        super().start(doc, _md=_md)

    def event(self, doc, **kwargs):
        # Reduction is stop-driven and Tiled-backed; nothing to do per event.
        return doc

    def stop(self, doc, _md=None):
        if not self.factory_log.do_process or self.img_analyzer is None:
            print(
                "\n[STOP] Nothing to process for this run; emitting stop only.\n",
                flush=True,
            )
            super().stop(doc, _md=_md)
            self.factory_log.do_process = False
            self.img_analyzer = None
            return

        analyzer = self.img_analyzer

        stream_name = list(doc["num_events"].keys())
        analyzer.stream_name = stream_name

        print(
            "\n-------------------- [STOP] starting reduction for "
            f"uid={analyzer.full_uid} (sample={analyzer.sample_name}, "
            f"detector={analyzer.detector}, acq_mode={analyzer.acq_mode}) "
            "--------------------\n",
            flush=True,
        )
        print(f"[STOP] stream(s): {stream_name}\n", flush=True)

        # Wait for data to be written to the databroker, then run the
        # compute-only pipeline. This dispatcher performs no file I/O; all
        # writing is done by pdf_auto.save_data.SaveData from the published
        # ``reduced`` event below.
        print("[STEP 1/4] Waiting 1 s for data to land in the databroker...\n",
              flush=True)
        time.sleep(1)

        print("[STEP 2/4] Processing detector image (stitch / dark-subtract)...\n",
              flush=True)
        process_img, tiff_fn = analyzer.compute_processed_image()
        poni_name, mask_name = analyzer.poni_mask_fn
        print(
            f"[STEP 2/4] Image ready -> {os.path.basename(tiff_fn)} "
            f"(poni={os.path.basename(poni_name)}, "
            f"mask={os.path.basename(mask_name)}).\n",
            flush=True,
        )

        print("[STEP 3/4] pyFAI 2D->1D integration...\n", flush=True)
        iq_df, tth_df, integration_md, iq_fn, tth_fn, cake = analyzer.pct_integration()
        print(
            f"[STEP 3/4] Integration ready -> {os.path.basename(iq_fn)}, "
            f"{os.path.basename(tth_fn)}.\n",
            flush=True,
        )

        output_paths: dict[str, str] = {
            "img": tiff_fn,
            "iq": iq_fn,
            "tth": tth_fn,
        }
        scalars: dict[str, object] = {
            "poni_file": os.path.basename(poni_name),
            "mask_file": os.path.basename(mask_name),
            # Full paths for the plotting callback (basenames above are kept for
            # SaveData's file headers/metadata).
            "poni_path": poni_name,
            "stitched": analyzer.stream_length == analyzer.num_positions,
        }
        # Reduced arrays carried inline for SaveData and the plotting callback
        # (so plotting needs no filesystem access to the raw products).
        arrays: dict[str, object] = {
            "image": process_img,
            "cake": cake,
            "mask": analyzer.mask_array,
            "q": iq_df["q"].to_numpy(),
            "iq": iq_df["I"].to_numpy(),
            "tth": tth_df["tth"].to_numpy(),
            "integration_md": integration_md,
        }

        temperature = analyzer.temperature
        if isinstance(temperature, float):
            scalars["temperature"] = temperature
            scalars["temperature_unit"] = analyzer.T_unit

        if analyzer.do_reduction and analyzer.acq_mode == "PDF":
            print("[STEP 4/4] PDF acquisition: PDFgetX reduction (S/F/G)...\n",
                  flush=True)
            # Publish the pdfgetter *output arrays* (picklable), not the live
            # PDFGetter object, so the reduced event survives ZMQ pickling.
            pdf_arrays, pdf_dir, pdf_prefix = analyzer.get_gr(iq_df)
            arrays["pdf_arrays"] = pdf_arrays
            arrays["pdfgetter_dir"] = pdf_dir
            arrays["pdfgetter_prefix"] = pdf_prefix
            scalars["bgscale"] = float(analyzer.pdfconfig().bgscale[0])
            scalars["backgroundfile"] = analyzer.pdfconfig_dict["backgroundfile"]
            print(
                f"[STEP 4/4] PDF reduction ready (prefix={pdf_prefix}, "
                f"types={sorted(pdf_arrays)}, "
                f"bgscale={scalars['bgscale']:.4f}).\n",
                flush=True,
            )
        else:
            print(
                "[STEP 4/4] Not a PDF acquisition; skipping G(r) transformation.\n",
                flush=True,
            )

        data = analysis_event_data(
            raw_uid=analyzer.full_uid,
            acq_mode=analyzer.acq_mode,
            sample_name=analyzer.sample_name,
            detector=analyzer.detector,
            output_paths=output_paths,
            scalars=scalars,
            arrays=arrays,
        )

        # Emit the synthesized analysis event, then the analysis stop document.
        print(
            "[PUBLISH] Emitting the reduced event to the analysis stream "
            "(subscribers/publisher will now receive it)...\n",
            flush=True,
        )
        self.process_event(
            {"data": data, "descriptor": None, "filled": {}},
            stream_name=ANALYSIS_STREAM_NAME,
            config={"data_keys": analysis_data_keys(data)},
        )
        super().stop(doc, _md=_md)

        print(
            "-------------------- [DONE] reduction published for "
            f"uid={analyzer.full_uid} --------------------\n",
            flush=True,
        )

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
    zmq_address: str | None = None,
    prefix: bytes | str | None = None,
    publish: bool = True,
    subscribers: Iterable[Callable[[str, dict], None]] | None = None,
):
    """Run the reduction as a re-emitted analysis stream over ZMQ.

    Builds a :class:`PDFAnalysisDispatcher`, publishes its reduced documents to
    the ``[PUBLISH TO]`` proxy via a :class:`bluesky.callbacks.zmq.Publisher`,
    attaches any provided ``subscribers``, subscribes the dispatcher to the
    ``[LISTEN TO]`` :class:`bluesky.callbacks.zmq.RemoteDispatcher`, and starts
    polling.

    The listen ``zmq_address``/``prefix`` come from ``[LISTEN TO]``; the publish
    ``host``/``prefix`` come from ``[PUBLISH TO]``. Explicit ``zmq_address``/
    ``prefix`` arguments override the listen INI values when not ``None``.

    Parameters
    ----------
    zmq_address:
        ZMQ address of the beamline document proxy's output socket (listen).
        When ``None``, the ``[LISTEN TO]`` INI value is used.
    prefix:
        ``RemoteDispatcher`` prefix filter for the listen stream (e.g.
        ``b"raw"``). A ``str`` is encoded to ``bytes``. When ``None``, the
        ``[LISTEN TO]`` INI value is used.
    publish:
        When ``True`` (default), a :class:`Publisher` for the ``[PUBLISH TO]``
        ``reduced`` stream is subscribed to the dispatcher so downstream
        SaveData/plotting callbacks receive the reduced documents.
    subscribers:
        Optional extra ``cb(name, doc)`` callbacks subscribed to the analysis
        stream (e.g. an in-process SaveData for testing).
    """
    ini_zmq_address, ini_prefix = read_listen_config(ini_config)
    if zmq_address is None:
        zmq_address = ini_zmq_address
    if prefix is None:
        prefix = ini_prefix
    elif isinstance(prefix, str):
        prefix = prefix.encode()

    dispatcher = PDFAnalysisDispatcher(beamline_acronym, ini_config)

    if publish:
        # Publisher connects to the proxy IN socket (publish_host).
        publish_host, _subscribe_host, publish_prefix = read_publish_config(
            ini_config
        )
        publisher = Publisher(publish_host, prefix=publish_prefix)
        dispatcher.subscribe(publisher)
        print(
            f"\n*** Publish reduced documents to {publish_host} ***\n"
            f"(prefix={publish_prefix!r}) \n",
            flush=True,
        )

    for subscriber in subscribers or ():
        dispatcher.subscribe(subscriber)

    rd = RemoteDispatcher(zmq_address, prefix=prefix)
    rd.subscribe(dispatcher)

    print(
        f"\n\n*** Subscribe to RemoteDispatcher at {zmq_address} ***\n"
        f"(prefix={prefix!r}) and start the analysis stream \n\n"
    )

    try:
        rd.start()
    except KeyboardInterrupt:
        print("\nExiting ZMQ analysis-stream dispatcher")
        return ()
