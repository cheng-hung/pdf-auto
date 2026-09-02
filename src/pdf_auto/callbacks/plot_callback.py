"""PlotData callback: live plots from the ``reduced`` analysis stream.

A Bluesky callback (following the ``bluesky.callbacks`` format) that consumes the
``reduced`` stream published by
:class:`pdf_auto.callbacks.live_dispatcher.PDFAnalysisDispatcher` and draws the beamline's
interactive figures (processed image + histogram, masked image + I(Q), and
S(Q)/F(Q)/G(r)) by reusing the existing :class:`pdf_auto.plotting.plotting.ImagePlotter`
and its slider/ring tuners.

Design notes:

- It subclasses :class:`bluesky.callbacks.mpl_plotting.QtAwareCallback`, NOT
  ``LivePlot``. ``LivePlot``/``LiveGrid`` accumulate one point/pixel per event;
  our ``reduced`` event instead carries whole arrays (image, cake, 1D curves,
  S/F/G) for one completed run and replaces the plot contents each run.
  ``QtAwareCallback`` gives us the important piece: it *teleports* the document
  to the main GUI thread via a Qt signal, so Matplotlib/Qt drawing is safe even
  though this callback runs in the ``RemoteDispatcher`` asyncio/background
  thread.
- Plots are drawn from the **inline arrays** in ``doc['data']`` (``image``,
  ``cake``, ``mask``, ``q``/``iq``, ``pdf_arrays``, ``poni_path``), so there is
  no file re-reading and no race with :class:`pdf_auto.callbacks.save_data.SaveData`.
- Tuner objects returned by ``ImagePlotter`` hold widget callbacks and must be
  retained for the lifetime of the run, so they are stored on ``self``.

Beamline-only: imports ``bluesky``/``pyFAI`` (via ``plotting`` → ``plot_widgets``)
at top level, so this module belongs to the ``beamline`` extra.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable

import pandas as pd
from bluesky.callbacks.mpl_plotting import QtAwareCallback
from bluesky.callbacks.zmq import RemoteDispatcher

from ..config import resolve_config_path
from ..plotting import plotting
from .save_data import read_publish_config

logger = logging.getLogger(__name__)


class PlotData(QtAwareCallback):
    """Draw the beamline figures for each ``reduced`` event.

    One :class:`pdf_auto.plotting.plotting.ImagePlotter` is (re)created per run so figures
    reset between samples. Nothing is written to disk.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plotter: plotting.ImagePlotter | None = None
        self.color_str = ""
        # Retain tuners so their Matplotlib widget callbacks stay alive.
        self._tuners: list = []

    def start(self, doc):
        sample_name = doc.get("sample_name", "")
        print(
            f"\n=== PlotData: new run (uid={doc.get('original_run_uid')}, "
            f"sample={sample_name}) ===\n",
            flush=True,
        )
        # Fresh figures per run; carry the color forward for visual continuity.
        self.plotter = plotting.ImagePlotter(sample_name, color_str=self.color_str)
        self.color_str = self.plotter.color_str
        self._tuners = []
        super().start(doc)

    def event(self, doc):
        data = doc.get("data", {})
        if self.plotter is None:
            # No start was seen (e.g. subscribed mid-run); build a plotter.
            self.plotter = plotting.ImagePlotter(
                data.get("sample_name", ""), color_str=self.color_str
            )
            self.color_str = self.plotter.color_str

        self._plot_image(data)
        self._plot_maskimg_iq(data)
        self._plot_pdf(data)
        print("=== PlotData: figures updated. ===\n", flush=True)
        super().event(doc)

    def _plot_image(self, data: dict) -> None:
        image = data.get("image")
        mask = data.get("mask")
        if image is None or mask is None:
            return
        # Unmasked 2D image + intensity histogram.
        tuner = self.plotter.plot_tiff3(
            image, mask, use_mask=False, histogram=True
        )
        tuner()
        self._tuners.append(tuner)

    def _plot_maskimg_iq(self, data: dict) -> None:
        image = data.get("image")
        mask = data.get("mask")
        cake = data.get("cake")
        q = data.get("q")
        iq = data.get("iq")
        poni_path = data.get("poni_path", "")
        if image is None or mask is None or cake is None or q is None or iq is None:
            return
        iq_df = pd.DataFrame({"q": q, "I(q)": iq})
        tuner = self.plotter.plot_maskImg_iq(
            image,
            mask,
            cake,
            data.get("iq_file", ""),
            poni_path,
            binning=2,
            iq_df=iq_df,
        )
        tuner()
        self._tuners.append(tuner)

    def _plot_pdf(self, data: dict) -> None:
        pdf_arrays = data.get("pdf_arrays")
        if pdf_arrays:
            self.plotter.plot_sqfqgr_arrays(pdf_arrays)
        else:
            # XRD/SAXS run: clear any stale S/F/G curves.
            self.plotter.clear_sqfqgr()

    def stop(self, doc):
        self.color_str = self.plotter.color_str if self.plotter else self.color_str
        print("=== PlotData: run complete. ===\n", flush=True)
        super().stop(doc)


def run_plot_zmq(
    ini_config: str | None = None,
    host: str | None = None,
    prefix: bytes | str | None = None,
    extra_subscribers: Iterable[Callable[[str, dict], None]] | None = None,
):
    """Run :class:`PlotData` against the published ``reduced`` ZMQ stream.

    Subscribes a :class:`PlotData` (and any ``extra_subscribers``) to a
    :class:`bluesky.callbacks.zmq.RemoteDispatcher` connected to the proxy
    **OUT** socket (``subscribe_host`` in ``[PUBLISH TO]``), then starts polling.
    ``host`` overrides the subscribe address; ``prefix`` overrides the prefix.

    Must run with a GUI Matplotlib backend (``MPLBACKEND=qtagg``) on a machine
    with a display; the Pixi ``pdf-plot`` task sets this.
    """
    import matplotlib.pyplot as plt
    from bluesky.callbacks.mpl_plotting import initialize_qt_teleporter

    from ..core.qt_kicker import install_qt_kicker

    # Initialize the Qt 'teleporter' on the main thread up front so PlotData
    # (a QtAwareCallback) can safely hand documents to the GUI thread even
    # though RemoteDispatcher processes them from its background asyncio thread.
    initialize_qt_teleporter()

    ini_config = str(resolve_config_path(ini_config))
    _publish_host, subscribe_host, ini_prefix = read_publish_config(ini_config)
    if host is None:
        host = subscribe_host
    if prefix is None:
        prefix = ini_prefix
    elif isinstance(prefix, str):
        prefix = prefix.encode()

    # Interactive, non-focus-stealing plots.
    plt.ion()
    plt.rcParams["figure.raise_window"] = False

    # strict=True so any deserialization failure raises loudly instead of being
    # silently dropped.
    rd = RemoteDispatcher(host, prefix=prefix, strict=True)

    # CRITICAL for interactivity: rd.start() blocks the main thread in the
    # asyncio loop, so the Qt event loop never runs on its own and Matplotlib
    # widgets (sliders/buttons) stay unresponsive. install_qt_kicker schedules a
    # periodic callback on the asyncio loop that pumps Qt GUI events, keeping the
    # tuners interactive.
    install_qt_kicker(rd.loop)

    rd.subscribe(PlotData())
    for subscriber in extra_subscribers or ():
        rd.subscribe(subscriber)

    print(
        f"\n\n*** PlotData subscribed to {host} (prefix={prefix!r}); ***\n"
        "waiting for reduced documents \n\n",
        flush=True,
    )

    try:
        rd.start()
    except KeyboardInterrupt:
        print("\nExiting PlotData ZMQ dispatcher", flush=True)
        return ()
