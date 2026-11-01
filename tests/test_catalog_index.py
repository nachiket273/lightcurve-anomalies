from pathlib import Path

from lca.catalog import load_catalog
from lca.io.index import append_index, read_index, resolve_tic

SEED = Path(__file__).parents[1] / "configs" / "catalogs" / "known_objects.yaml"


def test_seed_catalog_parses():
    cat = load_catalog(SEED)
    assert len(cat.targets) >= 10
    assert {t.category for t in cat.targets} >= {"planet", "flare_star"}


def test_index_dedup_and_resolve(tmp_path):
    rows = [{"name": "Pi Mensae", "category": "planet", "tic": 261136679, "sector": 1, "path": "x"}]
    append_index(tmp_path, rows)
    append_index(tmp_path, rows)  # duplicate ignored
    assert len(read_index(tmp_path)) == 1
    assert resolve_tic(tmp_path, "pi mensae") == 261136679
    assert resolve_tic(tmp_path, "TIC 42") == 42
    assert resolve_tic(tmp_path, "42") == 42
    assert resolve_tic(tmp_path, "unknown star") is None
