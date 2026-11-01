"""Canonical light-curve schema (see ARCHITECTURE.md, section 3).

One parquet file per target per mission per sector/field. Metadata is stored under the
``lca`` key in the parquet schema metadata so every file is traceable.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

META_KEY = b"lca"

DTYPES: dict[str, str] = {
    "time": "float64",
    "flux": "float32",
    "flux_err": "float32",
    "quality": "uint16",
}
BANDS = ("TESS", "g", "r", "i")


class SchemaError(ValueError):
    """Raised when a frame does not match the canonical light-curve schema."""


def make_frame(time, flux, flux_err, quality, band: str = "TESS") -> pd.DataFrame:
    """Build a canonical frame from array-likes. Sorts by time and drops NaN times."""
    df = pd.DataFrame(
        {
            "time": np.asarray(time, dtype="float64"),
            "flux": np.asarray(flux, dtype="float64"),
            "flux_err": np.asarray(flux_err, dtype="float64"),
            "quality": np.asarray(quality, dtype="int64"),
        }
    )
    df = df[np.isfinite(df["time"])].sort_values("time", kind="stable").reset_index(drop=True)
    for col, dtype in DTYPES.items():
        df[col] = df[col].astype(dtype)
    df["band"] = pd.Categorical([band] * len(df), categories=list(BANDS))
    return df


def validate(df: pd.DataFrame) -> None:
    """Raise SchemaError if ``df`` violates the canonical schema."""
    expected = [*DTYPES, "band"]
    if list(df.columns) != expected:
        raise SchemaError(f"columns must be {expected}, got {list(df.columns)}")
    for col, dtype in DTYPES.items():
        if str(df[col].dtype) != dtype:
            raise SchemaError(f"column {col!r} must be {dtype}, got {df[col].dtype}")
    if not isinstance(df["band"].dtype, pd.CategoricalDtype):
        raise SchemaError("column 'band' must be categorical")
    if df["time"].isna().any():
        raise SchemaError("time contains NaN")
    if len(df) > 1 and not df["time"].is_monotonic_increasing:
        raise SchemaError("time must be sorted ascending")


def write_lc(df: pd.DataFrame, path: str | Path, meta: dict) -> Path:
    """Validate and write a light curve with metadata. Creates parent directories."""
    validate(df)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(df, preserve_index=False)
    merged = {**(table.schema.metadata or {}), META_KEY: json.dumps(meta, default=str).encode()}
    pq.write_table(table.replace_schema_metadata(merged), path)
    return path


def read_lc(path: str | Path) -> tuple[pd.DataFrame, dict]:
    """Read a light curve and its metadata."""
    table = pq.read_table(path)
    raw = (table.schema.metadata or {}).get(META_KEY, b"{}")
    df = table.to_pandas()
    df["quality"] = df["quality"].astype("uint16")
    validate(df)
    return df, json.loads(raw)
