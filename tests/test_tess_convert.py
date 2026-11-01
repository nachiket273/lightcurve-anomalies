import numpy as np
import pytest

lk = pytest.importorskip("lightkurve")

from lca.io.tess import lightkurve_to_frame  # noqa: E402
from lca.schema import validate  # noqa: E402


def test_lightkurve_to_frame():
    t = np.linspace(1500, 1510, 500)
    lc = lk.LightCurve(
        time=t,
        flux=np.full(t.size, 1000.0),
        flux_err=np.full(t.size, 3.0),
    )
    lc["quality"] = np.zeros(t.size, dtype=int)
    lc.flux[10] = np.nan
    df = lightkurve_to_frame(lc)
    validate(df)
    assert len(df) == 500
    assert np.isnan(df["flux"].iloc[10])
