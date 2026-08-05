# pdf-auto

`pdf-auto` is the automatic area-detector data-reduction workflow used at the
NSLS-II PDF beamline. It listens for completed Bluesky runs, retrieves the run
from Tiled, processes the detector image, integrates the image to one-dimensional
data, and—when appropriate—performs PDF reduction.

This repository is intended primarily for colleagues who operate, maintain, or
debug the workflow on the beamline workstation.

## What the workflow produces

For a supported data run, the workflow can produce:

- a processed detector image (`.tiff`);
- integrated intensity as a function of momentum transfer (`.iq`);
- integrated intensity as a function of two-theta (`.xy`);
- `S(Q)`, `F(Q)`, and `G(r)` files for PDF acquisitions; and
- interactive Matplotlib views of the detector image, integration result, and
  PDF-reduction products.

Dark scans and runs that already contain `original_run_uid` are not processed.

## Processing flow

```mermaid
flowchart TD
    A["Bluesky run documents"] --> B["Kafka consumer in plugin_00.py"]
    B --> C{"Start document is eligible?"}
    C -->|"Dark or previously processed run"| D["Skip run"]
    C -->|"Data run"| E["Load run from Tiled"]
    E --> F["Wait for stop document"]
    F --> G{"Number and type of image streams"}
    G -->|"Configured multi-position run"| H["Stitch detector images"]
    G -->|"Single-position PE run"| I["Subtract dark image when available"]
    G -->|"Other supported run"| J["Read detector image"]
    H --> K["Save processed TIFF"]
    I --> K
    J --> K
    K --> L["Load mask and PONI calibration"]
    L --> M["pyFAI 2D integration and percentile filtering"]
    M --> N["Save I(Q) and two-theta data"]
    N --> O{"PDF acquisition and reduction enabled?"}
    O -->|"Yes"| P["PDFgetX reduction"]
    P --> Q["Save S(Q), F(Q), and G(r)"]
    O -->|"No"| R["Finish after integration"]
    K --> S["Update interactive plots"]
    N --> S
    Q --> S
```

Processing is triggered by Bluesky documents, but the data reduction itself is
performed after the run's `stop` document is received. The active server uses a
unique Kafka consumer group on each launch, so it receives new documents without
sharing work with another consumer instance.

## Beamline environment

The environment is defined in [`pixi.toml`](pixi.toml) and locked by
[`pixi.lock`](pixi.lock). It currently targets:

- Linux x86-64 (`linux-64`);
- Python 3.12;
- the NSLS-II Bluesky, Kafka, and Tiled infrastructure;
- pyFAI for azimuthal integration; and
- PDFstream/PDFgetX for PDF reduction.

The absolute repository path and local PDFgetX wheel path in `pixi.toml` are
intentional. They correspond to the beamline workstation deployment and should
not be changed there unless that deployment or wheel location changes.

The workflow also expects:

- a working Tiled profile matching the beamline acronym, normally `pdf`;
- `/etc/bluesky/kafka.yml` with Kafka connection information;
- access to the configured NSLS-II data directories;
- detector masks and PONI calibration files; and
- a graphical session for the Qt/Matplotlib displays.

## Starting the active server

On the beamline workstation, from this repository:

```bash
pixi install -e terminal
pixi run -e terminal pdf_auto
```

The `pdf_auto` Pixi task runs the equivalent of:

```bash
python /home/xf28id1/src/pdf-auto/plugin_00.py pdf
```

Here, `pdf` is both the beamline acronym used to construct the Kafka topic and
the Tiled profile name used by the processing factory. The server subscribes to:

```text
pdf.bluesky.runengine.documents
```

Stop the consumer with `Ctrl+C`.

The hard-coded INI path in [`plugin_00.py`](plugin_00.py) is also intentional for
the beamline workstation. If the repository is deployed elsewhere, the repository,
wheel, and INI paths must be updated together and validated in that environment.

## Configuration

Runtime behavior is controlled by
[`pilatus_zmq_config.ini`](pilatus_zmq_config.ini). Its existing filesystem paths
are beamline deployment paths and should not be replaced with generic examples.

### `[topics]`

Defines the raw and analysis catalog names. These values are retained for the
beamline data model even though the current entry point obtains its Tiled client
from the beamline profile.

### `[PATH]`

Defines:

- the processed-data and configuration roots;
- detector-specific PDF, XRD, and SAXS calibration directories;
- masks for individual detector positions and stitched images;
- PONI geometry files; and
- optional flat-field images.

The mask and PONI filenames are resolved beneath `config_base`. The selected
calibration directory depends on the detector and acquisition mode.

### `[SUM]`

Controls image preprocessing and acquisition classification:

- `num_positions` is the number of streams expected for a stitched acquisition;
- `detector_Xmotor` and `detector_Ymotor` name the position fields used during
  stitching;
- `pixel_size` converts motor displacement to detector-pixel offsets;
- `use_flat_field_*` enables detector-specific flat-field correction;
- `PDF_limit` is the upper detector-distance boundary for PDF mode; and
- `SAXS_limit` separates XRD and SAXS modes.

With the current configuration, distance is interpreted as follows:

| Detector distance | Acquisition mode |
|---|---|
| Less than `PDF_limit` | PDF |
| Between `PDF_limit` and `SAXS_limit` | XRD |
| Greater than `SAXS_limit` | SAXS |

### `[INTEGRATION]`

Controls pyFAI integration:

- `npt_rad`: number of radial bins;
- `npt_azim`: number of azimuthal bins;
- `polarization`: polarization correction factor;
- `UNIT`: radial-axis unit; and
- `low_limit_pcfilter` / `up_limit_pcfilter`: percentile limits used to reject
  low and high outliers in each radial bin of the unrolled image.

### `[pdfgetx3]`

Controls conversion from `I(Q)` to PDF products:

- `do_reduction` enables or disables PDFgetX processing;
- `backgroundfile` and `bgscale` control background subtraction;
- `use_auto_bkg` optimizes the background scale when the background exists;
- `qmin`, `qmax`, and `qmaxinst` define the Q range;
- `rmin`, `rmax`, and `rstep` define the real-space output range; and
- `rpoly`, `dataformat`, and `outputtype` are passed to PDFgetX.

PDFgetX reduction is performed only when `do_reduction = True` and the run is
classified as PDF. If `backgroundfile` is empty or missing, the workflow reports
that no background exists and continues with the PDF transformation configuration.

### `[TEMPERATURE]`

`temp_controller` names the start-document field containing sample temperature.
If that field is available and numeric, the temperature and inferred unit are
included in output metadata and filenames. Missing temperature metadata does not
stop processing.

## Required run metadata

The workflow expects the following Bluesky start-document fields:

| Field | Use |
|---|---|
| `uid` | Locates the run in Tiled and identifies output files |
| `sample_name` | Selects the sample output directory and filename prefix |
| `detectors` | Selects detector-specific preprocessing and calibration |
| `sp_plan_name` | Identifies dark scans that should be skipped |
| `calibration_md.Distance` | Classifies the run as PDF, XRD, or SAXS |
| `calibration_md.Wavelength` | Converts Q to two-theta |
| `composition_string` | Supplies composition for PDFgetX reduction; currently required for reliable operation |
| `sc_dk_field_uid` | Optional UID of the dark run used for subtraction |
| configured temperature field | Optional temperature metadata |

The stop document must provide `num_events`; its stream names are used to locate
the image data and decide whether the acquisition should be stitched.

The code contains an intended `Ni1.0` fallback for a missing
`composition_string`, but the PDF configuration may be evaluated before that
fallback is reached. For reliable operation, provide a valid composition in the
run metadata and confirm it is scientifically correct for the sample.

## Output layout and filenames

Outputs are written below:

```text
<user_data>/<tiff_base>/<sample_name>/<detector>/
├── img/
├── iq/
└── tth/
```

PDFgetX products are written in the detector directory. The base filename includes
the sample name, acquisition date/time, first six UID characters, and—when
available—temperature. A suffix records the image treatment:

- `_sum`: multi-position images were stitched;
- `_sub`: a single-position image was dark-subtracted, or exported directly when
  no dark UID was available; and
- `_flat`: flat-field correction was enabled.

The integration files include pyFAI configuration and run metadata in their
headers.

## Code map

| File | Responsibility |
|---|---|
| [`plugin_00.py`](plugin_00.py) | Active Kafka entry point, run filtering, and processing orchestration |
| [`imgData_2D.py`](imgData_2D.py) | Configuration, Tiled access, acquisition classification, dark subtraction, stitching, and output paths |
| [`img_integrate.py`](img_integrate.py) | Mask/calibration selection and pyFAI 2D-to-1D integration |
| [`img_getpdf.py`](img_getpdf.py) | PDFgetX configuration, automatic background scaling, and PDF reduction |
| [`img_plotter.py`](img_plotter.py) | High-level interactive plots |
| [`subplot_tuner.py`](subplot_tuner.py) | Matplotlib sliders, buttons, and plot controls |
| [`utility.py`](utility.py) | Shared parsing, array, plotting, logging, and background helpers |
| [`callbacks.py`](callbacks.py) | Experimental/unused callback code retained for development reference |
| [`zmq_server.py`](zmq_server.py) | Alternative server implementation; currently not working |

The `legacy_replay_tools/` directory contains replay utilities and calibration
assets from older server-testing workflows. It is retained for reference and
manual event replay; it is not the active server and is not an automated test
suite.

## Troubleshooting

### The server cannot connect to Kafka

Confirm that `/etc/bluesky/kafka.yml` exists, is readable, and contains the
beamline Kafka configuration. Also confirm that the requested beamline acronym
matches the published topic.

### A run UID cannot be loaded

Verify that the Tiled profile exists and that the run is visible through that
profile. The command-line acronym is also used as the profile name by the active
factory.

### A mask or PONI file cannot be found

Check the detector name, acquisition mode, `config_base`, and the corresponding
mask/PONI entries in the INI file. Stitched acquisitions use the stitched mask and
merged PONI file; other acquisitions use detector- and mode-specific files.

### No dark image was subtracted

Dark subtraction requires `sc_dk_field_uid` in the run metadata. Without it, the
raw image is exported and the server prints a warning.

### PDF files were not generated

Confirm all of the following:

- the run was classified as PDF using `calibration_md.Distance`;
- `do_reduction = True`;
- the run has a valid `composition_string`, or the printed fallback is acceptable;
- the PDFgetX environment is available; and
- the background and Q/r settings are appropriate for the measurement.

### Plot windows do not appear

The Pixi task selects the Qt Matplotlib backend. Run the workflow in a graphical
beamline workstation session with a functioning display and PySide6 installation.

## Legacy and alternative servers

[`plugin_00.py`](plugin_00.py) is the active implementation.
[`zmq_server.py`](zmq_server.py) is an alternative implementation but is currently
not working and should not be used for routine operation. Files under
`legacy_replay_tools/` belong to older testing/replay workflows and should not be
mistaken for the production entry point.
