"""Compatibility entry point for the beamline workstation.

The implementation now lives in :mod:`pdf_auto`. This wrapper preserves the
existing command configured in ``pixi.toml``.
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from pdf_auto.cli import main
except ModuleNotFoundError:
    # Keep direct execution working before the local project is installed.
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
    from pdf_auto.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
