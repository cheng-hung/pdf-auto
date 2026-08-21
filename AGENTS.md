# AGENTS.md

`pdf-auto` is the NSLS-II PDF beamline area-detector reduction workflow. It
consumes Bluesky run documents over **ZMQ**, loads runs from Tiled, integrates
images with pyFAI, runs PDFgetX reduction, and re-publishes a `reduced` analysis
stream that separate SaveData and PlotData processes consume. `README.md` is
thorough — read it for domain, config, and output details. This file only covers
agent-specific gotchas.

> **This branch has no Kafka.** The old Kafka file-writing consumer
> (`consumer.py`) was removed; that version lives on another branch. Do not
> re-add `bluesky-kafka`/`nslsii` or a `consumer.py` here.

## Environment reality vs. deployment target

- The project targets **`linux-64` only** (`pixi.toml`). Even on a linux
  checkout, `pixi install` / `pixi run pdf-analysis` will not fully work off the
  beamline workstation: they pull the beamline-local PDFgetX wheel at
  `/home/xf28id1/...` and expect beamline paths/services. Do not "fix" those
  absolute paths; they are the beamline deployment and are intentional (see
  README).
- For local dev, use plain Python 3.12 + `pip install -e '.[dev]'`, not Pixi.

## Commands (local dev)

```bash
pytest                 # offline suite only; runs without beamline services
ruff check .           # legacy/ is excluded via pyproject
ruff format --check .
mypy                   # files = src, tests (config in pyproject)
```

- `pytest` runs under `filterwarnings = error` and `--strict-markers`: any
  unexpected warning or unregistered marker fails the run.
- Tests requiring beamline services must use the registered `beamline` marker.
  The default suite is offline. CI (`.github/workflows/test.yml`) runs `pytest`
  on ubuntu with `MPLBACKEND=Agg`, installing only the base package + pytest —
  so the offline suite must never import beamline-extra deps at collection time.

## Package layout (subpackages)

`src/pdf_auto/` is grouped by responsibility:

- `reduction/` — `image_processing.py`, `integration.py`, `reduction.py` (the
  compute pipeline; `PDFReducer` = `pdf_auto.reduction.reduction.PDFReducer`).
- `callbacks/` — `live_dispatcher.py`, `save_data.py`, `plot_callback.py`,
  `analysis_stream.py` (Bluesky stream callbacks + the pure payload helpers).
- `plotting/` — `plotting.py`, `plot_widgets.py` (Matplotlib figures + tuners).
- `core/` — `utilities.py`, `routing.py`, `qt_kicker.py` (shared helpers).
- top level — `cli.py`, `config.py`, `__main__.py`, `__init__.py`.

Intra-package imports are relative and cross subpackages, e.g.
`from ..core.utilities import ...`, `from ..reduction import reduction`. Ruff
line length 88, target py312. `legacy/` is excluded from tooling (dead reference
code); do not treat it as an entrypoint.

## Import boundary (critical for local work)

Beamline-only deps (`bluesky`, `event_model`, `tiled`, `diffpy.pdfgetx`,
`pdfstream`, `pyFAI`) are in the `beamline` extra and are NOT installed by
default. These modules import them at top level and will fail to import
off-beamline:

- `reduction/image_processing.py`, `reduction/integration.py`,
  `reduction/reduction.py`, `plotting/plot_widgets.py`, `plotting/plotting.py`
  (via `plot_widgets`), `callbacks/live_dispatcher.py`, `callbacks/save_data.py`,
  `callbacks/plot_callback.py`

Off-beamline-safe modules (imported by the offline tests): `cli.py`,
`config.py`, `core/routing.py`, `core/utilities.py`, `core/qt_kicker.py`
(Matplotlib/Qt imported lazily inside the function), `callbacks/analysis_stream.py`.
Keep new importable-anywhere logic in these; keep beamline imports isolated to
the modules above so the offline suite stays green.

- `cli.py` must stay import-safe: `main`/`save_main`/`plot_main` import their
  beamline runners **lazily inside the function** (from `.callbacks.*`), never
  at module top. Tests import `cli` and its parsers directly.

## Entrypoints (three ZMQ processes)

All are `python -m pdf_auto ...` → `cli`; `__main__.py` routes first arg
`save`→`save_main`, `plot`→`plot_main`, else `main` (analysis):

- `pixi run pdf-analysis` = `python -m pdf_auto pdf` → `cli:main` →
  `callbacks.live_dispatcher.run_analysis_stream_zmq`: ZMQ-driven, compute-only
  `PDFAnalysisDispatcher` that publishes the `reduced` stream. The CLI arg
  (`pdf`) is the Tiled profile name.
- `pixi run pdf-save` = `python -m pdf_auto save` → `cli:save_main` →
  `callbacks.save_data.run_save_data_zmq`: subscribes and writes
  tiff/iq/tth/sq/fq/gr.
- `pixi run pdf-plot` = `python -m pdf_auto plot` → `cli:plot_main` →
  `callbacks.plot_callback.run_plot_zmq`: subscribes and draws figures.
  `PlotData` subclasses `QtAwareCallback` (teleports docs to the main GUI
  thread) and reuses `plotting.ImagePlotter`, plotting from the inline reduced
  arrays (no file re-read). `run_plot_zmq` installs `core.qt_kicker` so the Qt
  event loop stays live while `RemoteDispatcher` blocks the thread.

Default INI path is hardcoded in `config.py` to a beamline path; override with
`--config` for local testing rather than editing the default.

## ZMQ analysis stream (pdf-analysis → pdf-save)

The reduction was split into a Bluesky secondary stream: `PDFAnalysisDispatcher`
runs the pipeline (compute-only, no file I/O) and **publishes** a `reduced`
event; `SaveData` **subscribes** and writes tiff/iq/tth/sq/fq/gr. Hard-won
gotchas (all cost real beamline debugging):

- **`PDFAnalysisDispatcher.emit()` is overridden to skip schema validation.**
  The base `LiveDispatcher.emit` calls `schema_validators[name].validate(doc)`
  before dispatching; our `reduced` event `data` holds numpy arrays and dicts
  (`image`, `cake`, `pdf_arrays`, `integration_md`) that fail the strict
  event-model schema, so validation would silently block emission. Do not
  re-add validation to that path.
- **Never put the live diffpy `PDFGetter` object in the published event.** It
  does not reliably survive `pickle`, and `RemoteDispatcher` silently drops
  undeserializable messages. The reducer returns picklable output arrays
  (`reduction.reduction.PDFReducer.pdfgetter_arrays` → `{out_type: (2, N)
  array}`); `callbacks.save_data.write_pdf_arrays` writes them in the same
  layout as pdfstream's `write_pdfgetter`. `run_save_data_zmq` uses
  `strict=True` so future deserialization failures raise loudly instead of
  vanishing.
- **`[PUBLISH TO]` uses a two-proxy topology, not one proxy's in/out.** Publish
  and subscribe are DIFFERENT proxies bridged upstream:
  `publish_host = .../pdf-tcp-in-ipc-out/out.sock` (Publisher pushes here) and
  `subscribe_host = .../pdf-ipc-in-ipc-out/out.sock` (RemoteDispatcher reads
  here). Both are `out.sock`; `in.sock` / `tcp://localhost:5567` do NOT work for
  local publishers. `read_publish_config` returns
  `(publish_host, subscribe_host, prefix)`; a legacy single `host` key still
  falls back for both. Do not collapse these into one address.
- Reduction methods are **compute-only** (`compute_processed_image`,
  `pct_integration`, `compute_pdfgetter`/`get_gr` return data, not files);
  `callbacks.save_data.SaveData` is the sole writer.
- ZMQ callbacks run in an asyncio loop with no TTY — use `print(..., flush=True)`
  or output won't appear.

## Do not touch without cause

- Beamline-absolute paths in `pixi.toml`, `config.py`, and `pdf_auto_config.ini`
  (including the `[LISTEN TO]` / `[PUBLISH TO]` ZMQ sockets) are deployment
  values, not placeholders. `test_deployment_config.py` asserts the Pixi task
  set (`pdf-analysis`, `pdf-save`, `pdf-plot`), the dependency set, and the INI
  `[LISTEN TO]`/`[PUBLISH TO]` sections — update it if you change those.
