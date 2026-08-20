"""SaveData callback: persist reduced PDF products from the ``reduced`` stream.

This is a Bluesky callback (following the ``bluesky.callbacks`` format) that
consumes the ``reduced`` analysis stream published by
:class:`pdf_auto.live_dispatcher.PDFAnalysisDispatcher` and writes every product
to disk:

- the processed detector image as ``.tiff``;
- the integrated ``I(Q)`` as ``.iq`` and two-theta as ``.xy`` (with headers); and
- the ``S(Q)``/``F(Q)``/``G(r)`` PDFgetX products.

The dispatcher is now *compute-only*: it runs the pipeline, publishes the reduced
arrays + target paths + header metadata inline, and performs no file I/O.
SaveData is the sole writer. It can be used two ways:

- as a direct in-process subscriber to the dispatcher
  (``dispatcher.subscribe(SaveData())``); or
- driven later from the published ``reduced`` ZMQ stream via
  :func:`run_save_data_zmq`.

Beamline-only: ``write_pdfgetter`` (pdfstream) and ``tifffile`` are imported at
top level, so this module belongs to the ``beamline`` extra. The pure payload
shape lives in :mod:`pdf_auto.analysis_stream`.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from configparser import ConfigParser

import pandas as pd
import tifffile
from bluesky.callbacks.core import CallbackBase
from bluesky.callbacks.zmq import RemoteDispatcher
from pdfstream.transformation.io import write_pdfgetter

from .config import DEFAULT_CONFIG_PATH

ini_config = str(DEFAULT_CONFIG_PATH)

# Final fallbacks mirroring the ``[PUBLISH TO]`` INI section.
DEFAULT_PUBLISH_HOST = "ipc:///var/lib/bluesky-zmq-proxy/pdf-tcp-in-ipc-out/out.sock"
DEFAULT_PUBLISH_PREFIX = "reduced"


def read_publish_config(ini_config: str) -> tuple[str, bytes]:
    """Read the ZMQ ``host`` and ``prefix`` from the ``[PUBLISH TO]`` section.

    The ``prefix`` is returned as ``bytes`` because the ZMQ
    :class:`~bluesky.callbacks.zmq.Publisher`/:class:`RemoteDispatcher` expect a
    bytes prefix. Missing keys or a missing section fall back to the defaults.
    """
    parser = ConfigParser()
    parser.read(ini_config)
    host = parser.get("PUBLISH TO", "host", fallback=DEFAULT_PUBLISH_HOST)
    prefix = parser.get("PUBLISH TO", "prefix", fallback=DEFAULT_PUBLISH_PREFIX)
    return host, prefix.encode()


def write_iq_file(fn, df, md, header=("#q_A^-1", "I(q)")):
    """Write a 1D integration file (``.iq``/``.xy``) with a metadata header.

    Mirrors the historical ``pdf_auto.integration.iq_saver`` output so files are
    byte-for-byte compatible with the previous file-writing workflow. Returns
    the number of header rows written.
    """
    os.makedirs(os.path.dirname(fn), exist_ok=True)

    with open(fn, mode="w", encoding="utf-8") as f:
        f.write("# pyFai_poni_information_28ID1_NSLS2_BNL\n")
        num_row = 1
        for key, value in md.items():
            f.write(f"# {key} {value}\n")
            num_row += 1

    df.to_csv(
        fn,
        encoding="utf-8",
        mode="a",
        header=header,
        index=False,
        float_format="{:.8e}".format,
        sep=" ",
    )
    return num_row


class SaveData(CallbackBase):
    """Write reduced PDF products carried on the ``reduced`` event stream.

    The event ``data`` produced by
    :func:`pdf_auto.analysis_stream.analysis_event_data` carries inline arrays
    (``image``, 1D dataframes) plus target paths and header metadata. This
    callback writes each product that is present; PDF-only products
    (``sq``/``fq``/``gr``) are written only when the pdfgetter is included.
    """

    def event(self, doc):
        data = doc.get("data", {})
        print(
            "\n=== SaveData received a reduced event "
            f"(raw_uid={data.get('raw_uid')}, acq_mode={data.get('acq_mode')}, "
            f"sample={data.get('sample_name')}); writing files... ===\n",
            flush=True,
        )
        self._save_image(data)
        self._save_integration(data)
        self._save_pdf(data)
        print("\n=== SaveData finished writing this event. ===\n", flush=True)
        return doc

    def save(self, data: dict) -> dict:
        """Write all products in ``data`` and return the S(Q)/F(Q)/G(r) paths.

        Convenience for in-process callers (e.g. the Kafka file-writing
        consumer) that want the written pdfgetter paths back for plotting. The
        returned dict is whatever ``write_pdfgetter`` produced (``{}`` when no
        pdfgetter was present).
        """
        self._save_image(data)
        self._save_integration(data)
        return self._save_pdf(data)

    @staticmethod
    def _save_image(data: dict) -> None:
        image = data.get("image")
        tiff_fn = data.get("img_file")
        if image is None or not tiff_fn:
            print("\n*** No processed image to save. ***\n", flush=True)
            return
        os.makedirs(os.path.dirname(tiff_fn), exist_ok=True)
        tifffile.imwrite(tiff_fn, image)
        print(f"\n*** {os.path.basename(tiff_fn)} saved!! ***\n", flush=True)

    @staticmethod
    def _save_integration(data: dict) -> None:
        md = data.get("integration_md", {})

        iq_fn = data.get("iq_file")
        q = data.get("q")
        iq = data.get("iq")
        if iq_fn and q is not None and iq is not None:
            iq_df = pd.DataFrame({"q": q, "I": iq})
            write_iq_file(iq_fn, iq_df, md)
            print(f"\n*** {os.path.basename(iq_fn)} saved!! ***\n", flush=True)

        tth_fn = data.get("tth_file")
        tth = data.get("tth")
        if tth_fn and tth is not None and iq is not None:
            tth_df = pd.DataFrame({"tth": tth, "I": iq})
            write_iq_file(tth_fn, tth_df, md, header=("#tth", "I(q)"))
            print(f"\n*** {os.path.basename(tth_fn)} saved!! ***\n", flush=True)

    @staticmethod
    def _save_pdf(data: dict) -> dict:
        pdfgetter = data.get("pdfgetter")
        target_dir = data.get("pdfgetter_dir")
        prefix = data.get("pdfgetter_prefix")
        if pdfgetter is None or not target_dir or not prefix:
            print("\n*** No PDF (S/F/G) products to save. ***\n", flush=True)
            return {}
        os.makedirs(target_dir, exist_ok=True)
        sqfqgr_path = write_pdfgetter(target_dir, prefix, pdfgetter)
        print(f"\n*** {os.path.basename(sqfqgr_path['gr'])} saved!! ***\n", flush=True)
        return sqfqgr_path


def run_save_data_zmq(
    ini_config: str = ini_config,
    host: str | None = None,
    prefix: bytes | str | None = None,
    extra_subscribers: Iterable[Callable[[str, dict], None]] | None = None,
):
    """Run :class:`SaveData` against the published ``reduced`` ZMQ stream.

    Subscribes a :class:`SaveData` (and any ``extra_subscribers``) to a
    :class:`bluesky.callbacks.zmq.RemoteDispatcher` connected to the
    ``[PUBLISH TO]`` proxy, then starts polling. ``host``/``prefix`` override the
    INI values when given.
    """
    ini_host, ini_prefix = read_publish_config(ini_config)
    if host is None:
        host = ini_host
    if prefix is None:
        prefix = ini_prefix
    elif isinstance(prefix, str):
        prefix = prefix.encode()

    rd = RemoteDispatcher(host, prefix=prefix)
    rd.subscribe(SaveData())
    for subscriber in extra_subscribers or ():
        rd.subscribe(subscriber)

    print(
        f"\n\n*** SaveData subscribed to {host} (prefix={prefix!r}); ***\n"
        "waiting for reduced documents \n\n",
        flush=True,
    )

    try:
        rd.start()
    except KeyboardInterrupt:
        print("\nExiting SaveData ZMQ dispatcher", flush=True)
        return ()
