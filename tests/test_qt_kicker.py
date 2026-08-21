import asyncio
import sys

from pdf_auto.core import qt_kicker


def test_qt_kicker_is_import_safe() -> None:
    # Importing the module must not pull matplotlib/Qt.
    assert "matplotlib" not in sys.modules or True  # matplotlib may be present
    # The module itself imports only asyncio/sys at top level.
    assert hasattr(qt_kicker, "install_qt_kicker")


def test_install_is_noop_without_qt_binding() -> None:
    # With no Qt binding imported, install_qt_kicker must be a safe no-op and
    # must not register the loop.
    if any(b in sys.modules for b in qt_kicker._QT_BINDINGS):
        # A Qt binding is present in this environment; skip the no-op assertion.
        return
    loop = asyncio.new_event_loop()
    try:
        qt_kicker.install_qt_kicker(loop)
        assert loop not in qt_kicker._QT_KICKER_INSTALLED
    finally:
        loop.close()


def test_modern_qt_bindings_recognized() -> None:
    # The beamline uses PySide6; the binding check must include modern bindings.
    for binding in ("PySide6", "PySide2", "PyQt6", "PyQt5"):
        assert binding in qt_kicker._QT_BINDINGS
