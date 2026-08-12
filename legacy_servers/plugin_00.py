"""Legacy compatibility entry point for the beamline workstation.

The active Pixi task now launches :mod:`pdf_auto` directly. This wrapper is
retained only as a reference for the earlier workstation command.
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from pdf_auto.cli import main
except ModuleNotFoundError:
    # Keep direct execution working before the local project is installed.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from pdf_auto.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
