"""Standard diagnostic plots."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from lca.schema import read_lc  # noqa: E402


def good_mask(df) -> np.ndarray:
    return (df["quality"].to_numpy() == 0) & np.isfinite(df["flux"].to_numpy())


def plot_target(paths: list[Path], out: Path, title: str | None = None) -> Path:
    """One panel per sector: quality-masked flux, median-normalised per sector."""
    paths = sorted(paths)
    if not paths:
        raise ValueError("no light-curve files to plot")
    fig, axes = plt.subplots(len(paths), 1, figsize=(11, 2.4 * len(paths)), squeeze=False)
    for ax, p in zip(axes[:, 0], paths, strict=True):
        df, meta = read_lc(p)
        m = good_mask(df)
        t = df["time"].to_numpy()[m]
        f = df["flux"].to_numpy()[m]
        if f.size:
            f = f / np.nanmedian(f)
        ax.plot(t, f, ".", ms=1.5, color="k", alpha=0.6)
        ax.set_ylabel("norm. flux")
        ax.set_title(
            f"Sector {meta.get('sector', '?')}  ·  kept {m.sum()}/{len(df)} cadences",
            fontsize=9,
            loc="left",
        )
    axes[-1, 0].set_xlabel("BTJD")
    if title:
        fig.suptitle(title)
    fig.tight_layout()
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=130)
    plt.close(fig)
    return out
