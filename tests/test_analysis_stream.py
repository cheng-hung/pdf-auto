from pdf_auto.analysis_stream import (
    ANALYSIS_STREAM_NAME,
    analysis_data_keys,
    analysis_event_data,
)


def test_stream_name_is_stable() -> None:
    assert ANALYSIS_STREAM_NAME == "pdf_analysis"


def test_event_data_includes_core_fields_and_paths() -> None:
    data = analysis_event_data(
        raw_uid="abc123",
        acq_mode="PDF",
        sample_name="Ni",
        detector="pilatus1",
        output_paths={"iq": "/x/a.iq", "tth": "/x/a.xy", "gr": "/x/a.gr"},
    )
    assert data["raw_uid"] == "abc123"
    assert data["acq_mode"] == "PDF"
    assert data["sample_name"] == "Ni"
    assert data["detector"] == "pilatus1"
    assert data["iq_file"] == "/x/a.iq"
    assert data["tth_file"] == "/x/a.xy"
    assert data["gr_file"] == "/x/a.gr"


def test_event_data_skips_empty_paths_and_none_scalars() -> None:
    data = analysis_event_data(
        raw_uid="u",
        acq_mode="XRD",
        sample_name="s",
        detector="d",
        output_paths={"iq": "/x/a.iq", "gr": ""},
        scalars={"bgscale": None, "temperature": 300.0},
    )
    assert "gr_file" not in data
    assert "bgscale" not in data
    assert data["temperature"] == 300.0


def test_event_data_never_embeds_arrays() -> None:
    data = analysis_event_data(
        raw_uid="u",
        acq_mode="PDF",
        sample_name="s",
        detector="d",
        output_paths={"iq": "/x/a.iq"},
        scalars={"stitched": True, "bgscale": 0.98},
    )
    # Every value must be a path string or a plain scalar; no arrays/objects.
    for value in data.values():
        assert isinstance(value, (str, int, float, bool))


def test_data_keys_dtypes() -> None:
    data = analysis_event_data(
        raw_uid="u",
        acq_mode="PDF",
        sample_name="s",
        detector="d",
        output_paths={"iq": "/x/a.iq"},
        scalars={"stitched": True, "bgscale": 0.98, "npt": 4096},
    )
    keys = analysis_data_keys(data)
    assert keys["iq_file"]["dtype"] == "string"
    assert keys["stitched"]["dtype"] == "boolean"
    assert keys["bgscale"]["dtype"] == "number"
    assert keys["npt"]["dtype"] == "number"
    assert all(k["shape"] == [] for k in keys.values())
