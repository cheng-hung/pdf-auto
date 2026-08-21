"""Support ``python -m pdf_auto``.

The first argument selects the entry point:

- ``python -m pdf_auto save [--config ... --host ... --prefix ...]`` runs the
  SaveData ZMQ subscriber (:func:`pdf_auto.cli.save_main`);
- ``python -m pdf_auto plot [--config ... --host ... --prefix ...]`` runs the
  PlotData ZMQ subscriber (:func:`pdf_auto.cli.plot_main`);
- anything else (e.g. ``python -m pdf_auto pdf``) runs the ZMQ analysis-stream
  dispatcher (:func:`pdf_auto.cli.main`).
"""

import sys

from .cli import main, plot_main, save_main

if len(sys.argv) > 1 and sys.argv[1] == "save":
    raise SystemExit(save_main(sys.argv[2:]))

if len(sys.argv) > 1 and sys.argv[1] == "plot":
    raise SystemExit(plot_main(sys.argv[2:]))

raise SystemExit(main())
