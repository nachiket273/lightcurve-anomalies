"""A tiny CSV index of what has been fetched: name -> TIC -> sector -> path."""

from __future__ import annotations

import csv
from pathlib import Path

FIELDS = ["name", "category", "tic", "sector", "path"]


def index_path(raw_dir: Path) -> Path:
    return Path(raw_dir) / "_index.csv"


def read_index(raw_dir: Path) -> list[dict]:
    p = index_path(raw_dir)
    if not p.exists():
        return []
    with open(p, newline="") as fh:
        return list(csv.DictReader(fh))


def append_index(raw_dir: Path, rows: list[dict]) -> None:
    """Append rows, skipping any (tic, sector) pair already present."""
    existing = {(r["tic"], r["sector"]) for r in read_index(raw_dir)}
    new = [r for r in rows if (str(r["tic"]), str(r["sector"])) not in existing]
    if not new:
        return
    p = index_path(raw_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    write_header = not p.exists()
    with open(p, "a", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerows({k: r.get(k, "") for k in FIELDS} for r in new)


def resolve_tic(raw_dir: Path, target: str) -> int | None:
    """Resolve 'TIC 123', '123', or a catalog name to a TIC id using the index."""
    t = target.strip()
    if t.upper().startswith("TIC"):
        t = t[3:].strip(" _-")
    if t.isdigit():
        return int(t)
    for row in read_index(raw_dir):
        if row["name"].strip().lower() == target.strip().lower():
            return int(row["tic"])
    return None
