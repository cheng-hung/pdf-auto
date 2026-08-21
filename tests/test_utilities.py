import numpy as np
import pandas as pd

from pdf_auto.core.utilities import bin_ndarray, data_to_numpy, get_header_rows


def test_bin_ndarray_mean() -> None:
    data = np.arange(16).reshape(4, 4)

    result = bin_ndarray(data, new_shape=(2, 2), operation="mean")

    np.testing.assert_array_equal(result, np.array([[2.5, 4.5], [10.5, 12.5]]))


def test_data_to_numpy_accepts_dataframe() -> None:
    frame = pd.DataFrame({"q": [1.0, 2.0], "intensity": [3.0, 4.0]})

    result = data_to_numpy(frame)

    np.testing.assert_array_equal(result, np.array([[1.0, 2.0], [3.0, 4.0]]))


def test_get_header_rows(tmp_path) -> None:
    data_path = tmp_path / "sample.iq"
    data_path.write_text(
        "# metadata\n# q intensity\n1.0 2.0\n2.0 3.0\n",
        encoding="utf-8",
    )

    assert get_header_rows(data_path, check_range=2) == 2
