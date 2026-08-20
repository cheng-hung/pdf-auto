# AGENTS.md

`pdf-auto` is the NSLS-II PDF beamline area-detector reduction workflow. It
consumes Bluesky/Kafka run documents, loads runs from Tiled, integrates images
with pyFAI, and runs PDFgetX reduction. `README.md` is thorough — read it for
domain, config, and output details. This file only covers agent-specific gotchas.

## Environment reality vs. deployment target

- The project targets **`linux-64` only** (`pixi.toml`). Even on a linux
  checkout, `pixi install` / `pixi run pdf_auto` will not fully work off the
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

## Import boundary (critical for local work)

Beamline-only deps (`bluesky`, `bluesky_kafka`, `event_model`, `tiled`,
`diffpy.pdfgetx`, `pdfstream`, `pyFAI`) are in the `beamline` extra and are NOT
installed by default. These modules import them at top level and will fail to
import off-beamline:

- `consumer.py`, `reduction.py`, `integration.py`, `plot_widgets.py`

Off-beamline-safe modules (imported by the offline tests): `cli.py`,
`routing.py`, `utilities.py`, `image_processing.py`, `config.py`. Keep new
importable-anywhere logic in these; keep beamline imports isolated to the
modules above so the offline suite stays green.

## Layout conventions

- Package is `src/` layout (`src/pdf_auto/`); Ruff line length 88, target py312.
- `legacy/` is fully excluded from Ruff/tooling and is dead reference code
  (`zmq_server.py` is noted as non-working). Do not treat it as an entrypoint.
- Active entrypoint: `python -m pdf_auto pdf` → `pdf_auto.cli:main`. The CLI arg
  (`pdf`) is BOTH the Kafka topic prefix and the Tiled profile name.
- Default INI path is hardcoded in `config.py` to a beamline path; override with
  `--config` for local testing rather than editing the default.

## Do not touch without cause

- Beamline-absolute paths in `pixi.toml`, `config.py`, and `pdf_auto_config.ini`
  are deployment values, not placeholders. `test_deployment_config.py` asserts
  the Pixi task shape and dependency set — update it if you change those.
