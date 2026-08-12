import numpy as np
import pytest
import tifffile

from pdf_auto.image_processing import (
    ImageData2D,
    ImageDataConfig,
    classify_acquisition_mode,
    imgData_2D,
    imgData_config,
)


class ArrayField:
    def __init__(self, value) -> None:
        self.value = np.asarray(value)

    def to_numpy(self):
        return self.value


class FakeStream:
    def __init__(self, image, *, x=0.0, y=0.0) -> None:
        self.data = {
            "pe1c_image": ArrayField([[image]]),
            "pilatus_image": ArrayField([[image]]),
            "Grid_X": ArrayField([x]),
            "Grid_Y": ArrayField([y]),
        }

    def read(self):
        return self.data


class FakeRun:
    def __init__(self, start, streams) -> None:
        self.start = start
        self.streams = streams

    def __getitem__(self, name):
        return self.streams[name]

    def __getattr__(self, name):
        try:
            return self.streams[name]
        except KeyError as error:
            raise AttributeError(name) from error


def write_config(tmp_path, *, flat_field_pe1c=False):
    tmp_path.mkdir(parents=True, exist_ok=True)
    config_base = tmp_path / "config"
    config_path = tmp_path / "pdf-auto.ini"
    config_path.write_text(
        "\n".join(
            [
                "[PATH]",
                f"user_data = {tmp_path}",
                "tiff_base = processed",
                "config_base = config",
                "pilatus_PDF = pilatus_PDF",
                "pilatus_XRD = pilatus_XRD",
                "mask_01 = mask_1.npy",
                "mask_02 = mask_2.npy",
                "mask_03 = mask_3.npy",
                "[SUM]",
                "num_positions = 3",
                "pixel_size = 1.0",
                "detector_Xmotor = Grid_X",
                "detector_Ymotor = Grid_Y",
                f"use_flat_field_pe1c = {flat_field_pe1c}",
                "PDF_limit = 0.6",
                "SAXS_limit = 2.56",
                "[TEMPERATURE]",
                "temp_controller = cryostat_A",
            ]
        ),
        encoding="utf-8",
    )
    return config_path, config_base


def make_processor(tmp_path, *, detector="pe1c", dark=True, flat_field=False):
    raw = np.array([[10.0, 12.0], [14.0, 16.0]], dtype=np.float32)
    start = {
        "uid": "abcdef12-3456",
        "sample_name": "sample",
        "detectors": [detector],
        "time": 0,
        "calibration_md": {"Distance": 0.2, "Wavelength": 1e-10},
    }
    streams = {"primary": FakeStream(raw)}
    client = {}
    run = FakeRun(start, streams)
    client[start["uid"]] = run

    if dark:
        dark_uid = "dark-uid"
        start["sc_dk_field_uid"] = dark_uid
        dark_run = FakeRun({}, {"primary": FakeStream(np.full((2, 2), 2.0))})
        client[dark_uid] = dark_run

    config_path, _ = write_config(tmp_path, flat_field_pe1c=flat_field)
    processor = ImageData2D(start["uid"], client, config_path)
    processor.stream_name = ["primary"]
    return processor, raw


@pytest.mark.parametrize(
    ("distance", "expected"),
    [
        (0.2, "PDF"),
        (1.0, "XRD"),
        (3.0, "SAXS"),
        (0.6, "Unknown"),
        (2.56, "Unknown"),
    ],
)
def test_classify_acquisition_mode(distance: float, expected: str) -> None:
    assert classify_acquisition_mode(distance, 0.6, 2.56) == expected


def test_config_reads_requested_file(tmp_path) -> None:
    config_path = tmp_path / "pdf-auto.ini"
    config_path.write_text("[SUM]\nnum_positions = 3\n", encoding="utf-8")

    config = ImageDataConfig(config_path)
    config.read()

    assert config.getint("SUM", "num_positions") == 3


def test_dark_subtraction(tmp_path) -> None:
    processor, raw = make_processor(tmp_path)

    result = processor.subtract_dark()

    np.testing.assert_array_equal(result, raw - 2.0)


def test_missing_dark_returns_raw_image(tmp_path) -> None:
    processor, raw = make_processor(tmp_path, dark=False)

    result = processor.subtract_dark()

    np.testing.assert_array_equal(result, raw)


def test_save_processed_image_uses_sub_suffix(tmp_path) -> None:
    processor, raw = make_processor(tmp_path)

    processor.save_processed_image()
    output_path = processor.output_data_path("img", "tiff")

    assert output_path.endswith("_sub.tiff")
    np.testing.assert_array_equal(tifffile.imread(output_path), raw - 2.0)


def test_output_suffix_describes_processing(tmp_path) -> None:
    processor, _ = make_processor(tmp_path)
    assert processor.output_data_path("iq", "iq").endswith("_sub.iq")

    processor.stream_name = ["primary", "secondary", "tertiary"]
    assert processor.output_data_path("iq", "iq").endswith("_sum.iq")

    flat_processor, _ = make_processor(tmp_path / "flat", flat_field=True)
    assert flat_processor.output_data_path("iq", "iq").endswith("_flat.iq")


def test_temperature_is_included_in_filename(tmp_path) -> None:
    processor, _ = make_processor(tmp_path)
    processor.run.start["cryostat_A"] = 300.0

    assert processor.file_name_prefix.endswith("_300K")


def test_overlapping_pilatus_images_are_averaged(tmp_path) -> None:
    config_path, config_base = write_config(tmp_path)
    mask_dir = config_base / "pilatus_PDF"
    mask_dir.mkdir(parents=True)
    for index in range(1, 4):
        np.save(mask_dir / f"mask_{index}.npy", np.zeros((2, 2)))

    start = {
        "uid": "abcdef12-3456",
        "sample_name": "sample",
        "detectors": ["pilatus"],
        "time": 0,
        "calibration_md": {"Distance": 0.2, "Wavelength": 1e-10},
    }
    streams = {
        f"position_{index}": FakeStream(np.full((2, 2), float(index)))
        for index in range(1, 4)
    }
    run = FakeRun(start, streams)
    processor = ImageData2D(start["uid"], {start["uid"]: run}, config_path)
    processor.stream_name = list(streams)

    result = processor.stitch_images()

    np.testing.assert_array_equal(result, np.full((2, 2), 2.0))


def test_legacy_image_class_names_are_compatible() -> None:
    assert imgData_config is ImageDataConfig
    assert imgData_2D is ImageData2D


def test_legacy_image_method_names_are_compatible() -> None:
    assert ImageData2D.sum_pilatus2 is ImageData2D.stitch_images
    assert ImageData2D.sub_dk_img is ImageData2D.subtract_dark
    assert ImageData2D.save_processed_img is ImageData2D.save_processed_image
