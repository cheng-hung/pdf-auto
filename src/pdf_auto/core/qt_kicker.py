"""Self-contained Qt/asyncio event-loop kicker (no pdfstream dependency).

``install_qt_kicker`` schedules a periodic callback on an asyncio event loop that
pumps the Qt event queue and redraws stale Matplotlib figures. This keeps
Matplotlib/Qt widgets (sliders, buttons) interactive while a blocking asyncio
loop -- e.g. ``bluesky.callbacks.zmq.RemoteDispatcher.start()`` -- owns the main
thread.

This vendors the small helper pdf-auto previously imported from
``pdfstream.vend.qt_kicker`` so the beamline callbacks do not depend on
pdfstream. Two robustness fixes over that copy:

- The Qt-binding check also recognizes the modern bindings ``PySide6`` /
  ``PySide2`` / ``PyQt6`` (the beamline uses **PySide6**; the original only
  checked ``PyQt4`` / ``pyside`` / ``PyQt5`` and would silently no-op).
- ``_create_qApp`` is imported from ``matplotlib.backends.backend_qt`` (current)
  with a fallback to ``backend_qt5`` (older Matplotlib).

Only ``asyncio``/``sys`` are imported at module top, so this module stays
import-safe off-beamline (Matplotlib/Qt are imported lazily inside the function).
"""

import asyncio
import sys

# Guard against installing the kicker more than once per loop.
_QT_KICKER_INSTALLED: dict = {}

# Qt bindings that, if already imported, mean a Qt event loop is in play.
_QT_BINDINGS = ("PyQt4", "pyside", "PyQt5", "PySide2", "PySide6", "PyQt6")


def _create_qapp():
    """Return the singleton Matplotlib QApplication across Matplotlib versions."""
    try:
        from matplotlib.backends.backend_qt import _create_qApp
    except ImportError:  # older Matplotlib
        from matplotlib.backends.backend_qt5 import _create_qApp
    return _create_qApp()


def install_qt_kicker(loop=None, update_rate=0.03):
    """Install a periodic callback to integrate Qt and asyncio event loops.

    If no Qt binding is already imported, this does nothing. It is safe to call
    multiple times (idempotent per loop).

    Parameters
    ----------
    loop : asyncio event loop, optional
        Defaults to the current event loop.
    update_rate : float
        Seconds between periodic Qt kicks. Default 0.03.
    """
    if loop is None:
        loop = asyncio.get_event_loop()
    if loop in _QT_KICKER_INSTALLED:
        return
    if not any(binding in sys.modules for binding in _QT_BINDINGS):
        return

    from matplotlib._pylab_helpers import Gcf

    qapp = _create_qapp()

    try:
        _draw_all = Gcf.draw_all  # Matplotlib >= 1.5
    except AttributeError:  # slower, backward-compatible fallback
        def _draw_all():
            for f_mgr in Gcf.get_all_fig_managers():
                f_mgr.canvas.draw_idle()

    def _qt_kicker():
        # The asyncio loop starves the Qt loop; kick it to keep GUI events and
        # figure redraws flowing.
        _draw_all()
        qapp.processEvents()
        loop.call_later(update_rate, _qt_kicker)

    _QT_KICKER_INSTALLED[loop] = loop.call_soon(_qt_kicker)
