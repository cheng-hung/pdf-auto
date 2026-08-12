# Development

Use Python 3.12. The single beamline runtime environment is defined by
`pixi.toml`; standard package and developer-tool configuration is in
`pyproject.toml`.

Run the offline checks with:

```bash
pytest
ruff check .
ruff format --check .
```

Automatic formatting is available with:

```bash
ruff format .
ruff check . --fix
```

Do not enable the `beamline` tests in generic CI. Those tests may depend on the
Tiled profile, Kafka configuration, calibration files, a graphical session, and
the workstation-only PDFgetX wheel.
