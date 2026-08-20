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

Payloads are fully picklable (numpy arrays + paths + scalars); the live diffpy
``PDFGetter`` object is never sent over ZMQ (it may not survive ``pickle`` and
would cause :class:`~bluesky.callbacks.zmq.RemoteDispatcher` to silently drop the
event). The dispatcher extracts the pdfgetter output arrays; SaveData writes them.

Beamline-only: ``tifffile`` is imported at top level, so this module belongs to
the ``beamline`` extra. The pure payload shape lives in
:mod:`pdf_auto.analysis_stream`.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from configparser import ConfigParser

import numpy as np
import pandas as pd
import tifffile
from bluesky.callbacks.core import CallbackBase
from bluesky.callbacks.zmq import RemoteDispatcher

from .config import DEFAULT_CONFIG_PATH

ini_config = str(DEFAULT_CONFIG_PATH)

# Final fallbacks mirroring the ``[PUBLISH TO]`` INI section.
#
# The reduced stream is published into one proxy and read out of another (see
# the [PUBLISH TO] comments in pdf_auto_config.ini): the Publisher connects to
# the pdf-tcp-in-ipc-out proxy's out.sock, while the SaveData/plotting
# RemoteDispatcher connects to the pdf-ipc-in-ipc-out proxy's out.sock. These
# are DIFFERENT proxies; do not collapse them into one address.
DEFAULT_PUBLISH_IN = "ipc:///var/lib/bluesky-zmq-proxy/pdf-tcp-in-ipc-out/out.sock"
DEFAULT_PUBLISH_OUT = "ipc:///var/lib/bluesky-zmq-proxy/pdf-ipc-in-ipc-out/out.sock"
DEFAULT_PUBLISH_PREFIX = "reduced"


def read_publish_config(ini_config: str) -> tuple[str, str, bytes]:
    """Read the publish/subscribe hosts and ``prefix`` from ``[PUBLISH TO]``.

    Returns ``(publish_host, subscribe_host, prefix_bytes)`` where:

    - ``publish_host`` is the proxy **IN** socket the :class:`Publisher`
      connects to (INI key ``publish_host``, falling back to ``host`` then the
      default IN socket);
    - ``subscribe_host`` is the proxy **OUT** socket the SaveData
      :class:`RemoteDispatcher` connects to (INI key ``subscribe_host``, falling
      back to ``host`` then the default OUT socket).

    ``prefix`` is returned as ``bytes`` because the ZMQ callbacks require it.
    """
    parser = ConfigParser()
    parser.read(ini_config)
    # ``host`` (legacy single key) is used as a fallback for either side.
    legacy_host = parser.get("PUBLISH TO", "host", fallback=None)
    publish_host = parser.get(
        "PUBLISH TO",
        "publish_host",
        fallback=legacy_host if legacy_host else DEFAULT_PUBLISH_IN,
    )
    subscribe_host = parser.get(
        "PUBLISH TO",
        "subscribe_host",
        fallback=legacy_host if legacy_host else DEFAULT_PUBLISH_OUT,
    )
    prefix = parser.get("PUBLISH TO", "prefix", fallback=DEFAULT_PUBLISH_PREFIX)
    return publish_host, subscribe_host, prefix.encode()


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


def write_pdf_arrays(saving_dir: str, prefix: str, pdf_arrays: dict) -> dict:
    """Write S(Q)/F(Q)/G(r) (and I(Q)) files from plain (2, N) arrays.

    Reproduces the on-disk layout of ``pdfstream.transformation.io``'s
    ``write_pdfgetter`` -- one subdirectory per output type, files named
    ``<prefix>.<out_type>`` -- but from picklable numpy arrays instead of a live
    ``PDFGetter`` object. ``pdf_arrays`` maps each ``out_type`` (``iq``/``sq``/
    ``fq``/``gr``) to a ``(2, N)`` array of ``[x, y]``. Returns ``{out_type:
    path}`` like ``write_pdfgetter``.
    """
    paths: dict = {}
    for out_type, xy in pdf_arrays.items():
        out_dir = os.path.join(saving_dir, out_type)
        os.makedirs(out_dir, exist_ok=True)
        out_file = os.path.join(out_dir, f"{prefix}.{out_type}")
        xy = np.asarray(xy)
        np.savetxt(out_file, xy.T)
        paths[out_type] = out_file
    return paths


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
        print(f"\n*** Saved to {os.path.dirname(tiff_fn)} ***\n", flush=True)
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
        pdf_arrays = data.get("pdf_arrays")
        target_dir = data.get("pdfgetter_dir")
        prefix = data.get("pdfgetter_prefix")
        if not pdf_arrays or not target_dir or not prefix:
            print("\n*** No PDF (S/F/G) products to save. ***\n", flush=True)
            return {}
        os.makedirs(target_dir, exist_ok=True)
        sqfqgr_path = write_pdf_arrays(target_dir, prefix, pdf_arrays)
        for out_type, path in sqfqgr_path.items():
            print(
                f"\n*** {out_type}: {os.path.basename(path)} saved!! ***\n",
                flush=True,
            )
        return sqfqgr_path


def run_save_data_zmq(
    ini_config: str = ini_config,
    host: str | None = None,
    prefix: bytes | str | None = None,
    extra_subscribers: Iterable[Callable[[str, dict], None]] | None = None,
):
    """Run :class:`SaveData` against the published ``reduced`` ZMQ stream.

    Subscribes a :class:`SaveData` (and any ``extra_subscribers``) to a
    :class:`bluesky.callbacks.zmq.RemoteDispatcher` connected to the proxy
    **OUT** socket (``subscribe_host`` in ``[PUBLISH TO]``), then starts polling.
    ``host`` overrides the subscribe address; ``prefix`` overrides the prefix.
    """
    _publish_host, subscribe_host, ini_prefix = read_publish_config(ini_config)
    if host is None:
        host = subscribe_host
    if prefix is None:
        prefix = ini_prefix
    elif isinstance(prefix, str):
        prefix = prefix.encode()

    # strict=True so any deserialization failure raises loudly instead of the
    # message being silently dropped on the floor (the failure mode that hid an
    # unpicklable payload before). The reduced stream is now plain arrays/paths.
    rd = RemoteDispatcher(host, prefix=prefix, strict=True)
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
