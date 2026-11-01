"""``lca`` command-line interface. Grows week by week."""

from __future__ import annotations

import logging
from pathlib import Path

import typer

from lca.catalog import Catalog, Target, dump_catalog, load_catalog
from lca.io.index import read_index, resolve_tic

app = typer.Typer(help="lightcurve-anomalies", no_args_is_help=True)
RAW_TESS = Path("data/raw/tess")


@app.callback()
def _main(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    logging.basicConfig(level=logging.INFO if verbose else logging.WARNING, format="%(message)s")


@app.command()
def fetch(
    catalog: Path = typer.Option(..., help="YAML target list"),
    raw_dir: Path = typer.Option(RAW_TESS),
    max_sectors: int | None = typer.Option(None, help="cap sectors per target (smoke tests)"),
    overwrite: bool = typer.Option(False),
) -> None:
    """Download and cache TESS 2-min SPOC light curves for every target in a catalog."""
    from lca.io.tess import fetch_tess

    cat = load_catalog(catalog)
    missing: list[str] = []
    for t in cat.targets:
        try:
            paths = fetch_tess(
                t.name,
                category=t.category,
                raw_dir=raw_dir,
                max_sectors=max_sectors,
                overwrite=overwrite,
            )
        except Exception as exc:  # network or archive hiccup: keep going
            typer.echo(f"[error] {t.name}: {exc}")
            missing.append(t.name)
            continue
        typer.echo(f"[{'ok' if paths else 'none'}] {t.name}: {len(paths)} sector file(s)")
        if not paths:
            missing.append(t.name)
    if missing:
        typer.echo(f"\nNo data for {len(missing)} target(s): {', '.join(missing)}")


@app.command()
def plot(
    target: str = typer.Option(..., help="'TIC 123456' or a name already fetched"),
    raw_dir: Path = typer.Option(RAW_TESS),
    out: Path | None = typer.Option(None),
) -> None:
    """Plot all cached sectors for one target."""
    from lca.viz.plot import plot_target

    tic = resolve_tic(raw_dir, target)
    if tic is None:
        raise typer.BadParameter(f"cannot resolve {target!r}; fetch it first or pass a TIC id")
    paths = list(raw_dir.glob(f"*/{tic}.parquet"))
    if not paths:
        raise typer.BadParameter(f"no cached files for TIC {tic} in {raw_dir}")
    out = out or Path("data/plots") / f"tic{tic}.png"
    typer.echo(str(plot_target(paths, out, title=f"{target} (TIC {tic})")))


@app.command()
def summary(raw_dir: Path = typer.Option(RAW_TESS)) -> None:
    """Coverage report: targets and sector files per category."""
    rows = read_index(raw_dir)
    if not rows:
        typer.echo("nothing fetched yet")
        raise typer.Exit()
    by_cat: dict[str, dict[str, set]] = {}
    for r in rows:
        c = by_cat.setdefault(r["category"] or "other", {"tic": set(), "files": set()})
        c["tic"].add(r["tic"])
        c["files"].add((r["tic"], r["sector"]))
    typer.echo(f"{'category':<18}{'targets':>8}{'sector files':>14}")
    for cat, v in sorted(by_cat.items()):
        typer.echo(f"{cat:<18}{len(v['tic']):>8}{len(v['files']):>14}")
    all_tic = {r["tic"] for r in rows}
    typer.echo(f"{'TOTAL':<18}{len(all_tic):>8}{len({(r['tic'], r['sector']) for r in rows}):>14}")


@app.command("catalog-toi")
def catalog_toi(
    out: Path = typer.Option(Path("configs/catalogs/toi_confirmed.yaml")),
    limit: int = typer.Option(60, help="number of targets, brightest first"),
) -> None:
    """Build a catalog of confirmed / known TESS planets from the NASA Exoplanet Archive.

    Uses the 'toi' table; tfopwg_disp CP = confirmed planet, KP = known planet.
    """
    from astroquery.ipac.nexsci.nasa_exoplanet_archive import NasaExoplanetArchive

    tbl = NasaExoplanetArchive.query_criteria(
        table="toi",
        select="tid,toi,tfopwg_disp,pl_orbper,st_tmag",
        where="tfopwg_disp in ('CP','KP')",
        order="st_tmag",
    )
    seen: set[int] = set()
    targets: list[Target] = []
    for row in tbl:
        tid = int(row["tid"])
        if tid in seen:
            continue
        seen.add(tid)
        period = row["pl_orbper"]
        note = f"TOI-{row['toi']}, Tmag {float(row['st_tmag']):.1f}"
        if period == period:  # not NaN
            note += f", P={float(period):.3f} d"
        targets.append(Target(name=f"TIC {tid}", category="planet", note=note))
        if len(targets) >= limit:
            break
    dump_catalog(Catalog(targets=targets), out)
    typer.echo(f"wrote {len(targets)} targets to {out}")


if __name__ == "__main__":
    app()
