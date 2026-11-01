from lca.schema import write_lc
from lca.viz.plot import good_mask, plot_target


def test_good_mask_excludes_flagged(synthetic_frame):
    m = good_mask(synthetic_frame)
    assert m.sum() == len(synthetic_frame) - 20


def test_plot_smoke(tmp_path, synthetic_frame):
    paths = [
        write_lc(synthetic_frame, tmp_path / f"{s:03d}" / "1.parquet", {"sector": s})
        for s in (1, 2)
    ]
    out = plot_target(paths, tmp_path / "p.png", title="synthetic")
    assert out.exists() and out.stat().st_size > 1000
