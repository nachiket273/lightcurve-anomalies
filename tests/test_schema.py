import numpy as np
import pandas as pd
import pytest

from lca.schema import SchemaError, make_frame, read_lc, validate, write_lc


def test_make_frame_sorts_and_drops_nan_time():
    df = make_frame([3.0, np.nan, 1.0, 2.0], [1, 2, 3, 4], [0.1] * 4, [0, 0, 0, 0])
    assert list(df["time"]) == [1.0, 2.0, 3.0]
    validate(df)


def test_dtypes(synthetic_frame):
    assert str(synthetic_frame["flux"].dtype) == "float32"
    assert str(synthetic_frame["quality"].dtype) == "uint16"
    assert str(synthetic_frame["time"].dtype) == "float64"


def test_roundtrip_preserves_data_and_metadata(tmp_path, synthetic_frame):
    meta = {"tic": 123, "sector": 7}
    p = write_lc(synthetic_frame, tmp_path / "007" / "123.parquet", meta)
    df, meta2 = read_lc(p)
    assert meta2 == meta
    pd.testing.assert_frame_equal(df, synthetic_frame)


def test_validate_rejects_unsorted(synthetic_frame):
    bad = synthetic_frame.iloc[::-1].reset_index(drop=True)
    with pytest.raises(SchemaError):
        validate(bad)


def test_validate_rejects_wrong_columns(synthetic_frame):
    with pytest.raises(SchemaError):
        validate(synthetic_frame.drop(columns=["band"]))
