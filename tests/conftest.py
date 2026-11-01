import numpy as np
import pytest

from lca.schema import make_frame


@pytest.fixture
def synthetic_frame():
    rng = np.random.default_rng(42)
    t = np.arange(0, 27, 2 / 1440)  # one sector at 2-min cadence
    flux = 1e5 * (1 + 0.001 * rng.standard_normal(t.size))
    flux[(t % 3.0) < 0.1] *= 0.99  # box transit, P=3 d, depth 1%
    err = np.full(t.size, 100.0)
    quality = np.zeros(t.size, dtype=int)
    quality[100:120] = 128  # flagged cadences
    return make_frame(t, flux, err, quality)
