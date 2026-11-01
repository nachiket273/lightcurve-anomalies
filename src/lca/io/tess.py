"""TESS light curves from MAST via lightkurve, converted to the canonical schema."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from lca import __version__
from lca.io.index import append_index
from lca.schema import make_frame, write_lc

log = logging.getLogger(__name__)

FLUX_COLUMN = "pdcsap_flux"


def _filled(values) -> np.ndarray:
    """Masked or plain array-like -> float ndarray with masked entries as NaN."""
    arr = getattr(values, "value", values)
    return np.ma.filled(np.ma.asarray(arr, dtype="float64"), np.nan)


def lightkurve_to_frame(lc):
    """Convert a lightkurve LightCurve (TESS) to a canonical frame."""
    return make_frame(
        time=_filled(lc.time.value),
        flux=_filled(lc.flux),
        flux_err=_filled(lc.flux_err),
        quality=np.ma.filled(np.ma.asarray(lc["quality"]), 0),
        band="TESS",
    )


def _row_key(res, i: int) -> tuple[int, int] | None:
    """Best-effort (sector, tic) from a search-result row, so cached files can be skipped."""
    try:
        sector = int(re.search(r"Sector\s+(\d+)", str(res.table["mission"][i])).group(1))
        return sector, int(res.table["target_name"][i])
    except Exception:
        return None


def lc_path(raw_dir: Path, sector: int, tic: int) -> Path:
    return Path(raw_dir) / f"{sector:03d}" / f"{tic}.parquet"


def fetch_tess(
    target: str,
    *,
    category: str = "other",
    raw_dir: Path = Path("data/raw/tess"),
    author: str = "SPOC",
    exptime: int = 120,
    max_sectors: int | None = None,
    overwrite: bool = False,
) -> list[Path]:
    """Download TESS 2-min SPOC light curves for ``target`` and cache them as parquet.

    Quality flags are kept (bitmask 'none') and applied downstream; PDCSAP flux is stored
    unnormalised. Already-cached (sector, TIC) pairs are skipped when they can be identified
    before download.
    """
    import lightkurve as lk

    res = lk.search_lightcurve(target, mission="TESS", author=author, exptime=exptime)
    n = len(res)
    if n == 0:
        log.warning("no TESS %s light curves found for %r", author, target)
        return []
    if max_sectors is not None:
        n = min(n, max_sectors)

    written: list[Path] = []
    index_rows: list[dict] = []
    for i in range(n):
        key = _row_key(res, i)
        if key and not overwrite and lc_path(raw_dir, key[0], key[1]).exists():
            path = lc_path(raw_dir, key[0], key[1])
            log.info("cached: %s", path)
            written.append(path)
            index_rows.append(
                {
                    "name": target,
                    "category": category,
                    "tic": key[1],
                    "sector": key[0],
                    "path": path,
                }
            )
            continue
        lc = res[i].download(flux_column=FLUX_COLUMN, quality_bitmask="none")
        if lc is None:
            log.warning("download failed: %r row %d", target, i)
            continue
        sector, tic = int(lc.meta["SECTOR"]), int(lc.meta["TICID"])
        meta = {
            "target_query": target,
            "category": category,
            "mission": "TESS",
            "tic": tic,
            "sector": sector,
            "camera": lc.meta.get("CAMERA"),
            "ccd": lc.meta.get("CCD"),
            "author": author,
            "exptime_s": exptime,
            "flux_column": FLUX_COLUMN,
            "flux_normalised": False,
            "time_system": "BTJD",
            "quality_bitmask": "none (flags kept; filter downstream)",
            "pipeline_version": __version__,
            "fetched_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        }
        path = write_lc(lightkurve_to_frame(lc), lc_path(raw_dir, sector, tic), meta)
        written.append(path)
        index_rows.append(
            {"name": target, "category": category, "tic": tic, "sector": sector, "path": path}
        )
    append_index(raw_dir, index_rows)
    return written
