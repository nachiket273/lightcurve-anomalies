"""Target lists (configs/catalogs/*.yaml)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel

Category = Literal[
    "planet", "eclipsing_binary", "rr_lyrae", "flare_star", "pulsator", "quiet", "other"
]


class Target(BaseModel):
    name: str  # anything MAST's name resolver understands, e.g. "Pi Mensae" or "TIC 261136679"
    category: Category = "other"
    note: str | None = None


class Catalog(BaseModel):
    targets: list[Target]


def load_catalog(path: str | Path) -> Catalog:
    with open(path) as fh:
        return Catalog.model_validate(yaml.safe_load(fh))


def dump_catalog(catalog: Catalog, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as fh:
        yaml.safe_dump(catalog.model_dump(exclude_none=True), fh, sort_keys=False)
