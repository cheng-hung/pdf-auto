# Architecture

The installable code uses a `src` layout under `src/pdf_auto`. Beamline services
are initialized only after the command-line arguments have been parsed, allowing
the package, documentation, and offline tests to load without Kafka, Tiled,
pyFAI, PDFstream, or the local PDFgetX wheel.

## Processing layers

1. `cli.py` parses the beamline acronym and optional INI path.
2. `consumer.py` receives Bluesky documents and owns run-level orchestration.
3. `routing.py` contains service-independent start-document decisions.
4. `image_processing.py` reads image streams, subtracts dark images, stitches
   multi-position images, and writes TIFF files.
5. `integration.py` applies masks and PONI calibration through pyFAI.
6. `reduction.py` converts integrated PDF data through PDFstream/PDFgetX.
7. `plotting.py` and `plot_widgets.py` manage interactive visualization.

`plugin_00.py` remains a compatibility wrapper because the deployed Pixi task
invokes that absolute workstation path. It delegates to `pdf_auto.cli`.

## Compatibility policy

Canonical APIs use standard Python names such as `ImageData2D`,
`ImageIntegrator`, `PDFReducer`, and `ProcessingFactory`. The earlier names are
retained as aliases during the transition so existing beamline scripts do not
break. New code and documentation should use the canonical names.

## Test boundary

The default suite tests pure routing, configuration, output naming, dark
subtraction, TIFF writing, and synthetic image stitching. Tests requiring live
NSLS-II services or the PDFgetX wheel must use the `beamline` pytest marker.
