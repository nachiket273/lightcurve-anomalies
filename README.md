# lightcurve-anomalies

> Hunting for weird stars in public TESS and ZTF light curves: learn what "normal" looks like, then surface what isn't.

![status](https://img.shields.io/badge/status-week%200-lightgrey)
![python](https://img.shields.io/badge/python-3.11+-blue)
![license](https://img.shields.io/badge/license-Apache-green)

## What is this?

A solo, open-science project that builds a pipeline to:

1. Pull brightness-vs-time data (light curves) for stars from public archives (TESS via MAST, ZTF via IRSA).
2. Clean and detrend them.
3. Learn a model of "normal" stellar variability.
4. Rank the objects that don't fit: odd dips, single-transit events, strange periodicities, flares, unclassified variables.
5. Vet the top candidates against existing catalogs (SIMBAD, TOI, Gaia, VSX) with deterministic queries.
6. Use an LLM to triage the evidence and write each survivor up as a candidate card. The LLM never detects anomalies and never supplies catalogue facts; it only reads a structured evidence packet.
7. Repeat on a schedule: twice a week, incrementally, with a digest for the Sunday review.

The goal is not to out-engineer the big survey pipelines. It is to learn the full stack (signal processing, astro data tooling, unsupervised ML, honest validation) while producing something reusable and, with some luck, a few objects worth a second look.

## Principles

- **Weekly cadence.** The project runs Sunday to Sunday. Every week ends with a tagged, self-contained deliverable and a `LOG.md` entry. Skipping a day never breaks the repo.
- **Injection-recovery before trust.** No detection claim without measuring what the pipeline can and cannot recover from synthetic signals.
- **Reproducible.** Fixed seeds, pinned dependencies, configs in version control, raw data never edited.
- **LLMs triage, they don't detect.** Detection is numeric and injection-tested. Catalogue facts come from code, not model memory.
- **Honest about findings.** A candidate is a candidate until it survives vetting. "Known object, correctly rediscovered" is a legitimate and useful result.

## Roadmap

| Week | Theme | Deliverable |
|------|-------|-------------|
| 1 | Data in | Loader + plots for ~100 known objects (planets, eclipsing binaries, RR Lyrae) |
| 2 | Cleaning and baseline search | Detrending, Lomb-Scargle, BLS recovering known planets |
| 3 | Injection-recovery | Completeness maps vs. depth, duration, period, magnitude |
| 4 | Features + baseline classifier | Hand-built features, classifier on labeled variables |
| 5 | Learned representations | Autoencoder / contrastive embeddings, anomaly scores |
| 6 | Scale-up | Run on a few thousand unlabeled stars, review top 100 by eye |
| 7 | Vetting + LLM triage | Cross-match with SIMBAD, TOI, Gaia; evidence packets; schema-validated LLM verdicts; candidate cards |
| 8 | Automation + write-up | Scheduled twice-weekly runs, weekly digest, report with injection-recovery results and surviving candidates |

Progress is tracked in [`LOG.md`](LOG.md) and by git tags (`week-01`, `week-02`, ...).

## Quickstart

```bash
git clone https://github.com/<your-username>/lightcurve-anomalies.git
cd lightcurve-anomalies

python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Fetch and cache a small demo set of known objects
lca fetch --catalog configs/catalogs/known_objects.yaml

# Plot one target
lca plot --target "TIC 261136679" --mission tess
```

> The CLI (`lca`) is introduced in week 1; commands will grow as the weeks progress.

## Repository layout

```
lightcurve-anomalies/
├── README.md
├── ARCHITECTURE.md
├── LOG.md                  # weekly log: tried / failed / next
├── pyproject.toml
├── configs/                # YAML configs for catalogs, pipeline, models
├── src/lca/
│   ├── io/                 # archive access, caching
│   ├── preprocess/         # cleaning, detrending, normalization
│   ├── search/             # periodograms, BLS, single-event search
│   ├── injection/          # synthetic signals + recovery metrics
│   ├── features/           # hand-crafted time-series features
│   ├── models/             # classifiers, autoencoders, anomaly scoring
│   ├── vetting/            # catalog cross-match, artifact checks
│   ├── triage/             # LLM triage agent, schemas, prompts
│   ├── runner/             # incremental state, scheduled-run entry point
│   └── viz/                # plots, candidate cards, weekly digest
├── notebooks/              # weekly exploration (one folder per week)
├── candidates/             # one vetting card per object
├── data/                   # gitignored: raw/, interim/, processed/
├── tests/
├── docs/
└── .github/workflows/      # scheduled and CI runs
```

## Schedule

| Run | When (UTC) | What |
|-----|------------|------|
| Midweek | Wed 00:00 | Ingest new data, preprocess, search, score, vet |
| Weekend | Sat 00:00 | Same, plus LLM triage, candidate cards, weekly digest |
| Review | Sunday | You read the digest, update `LOG.md`, tag `week-NN` |

Runs are incremental and safe to repeat. See [`ARCHITECTURE.md`](ARCHITECTURE.md) for how state, failures, and the LLM guardrails work.

## Data sources

- **TESS** light curves via [MAST](https://archive.stsci.edu/) (using `lightkurve` / `astroquery`)
- **ZTF** light curves via [IRSA](https://irsa.ipac.caltech.edu/)
- **Cross-match and vetting:** SIMBAD, TESS Objects of Interest (TOI), Gaia DR3, VSX

All data used is public. Please respect the archives' usage policies and cite them if you reuse results.

## Candidates

Each candidate lives in `candidates/<id>.md` with: identifiers, light-curve plots, detection statistics, injection-recovery context, cross-match results, and a verdict (`artifact`, `known`, `unclear`, `interesting`).

| ID | Source | Type | Verdict | Card |
|----|--------|------|---------|------|
| _none yet_ | | | | |

## Contributing

This is primarily a personal learning project, but issues, ideas, and critiques are welcome. If you spot a flaw in the validation, please open an issue; that is the most useful kind of feedback.

## Acknowledgments

Built on the shoulders of open tools and data: Astropy, Lightkurve, Astroquery, NumPy/SciPy, scikit-learn, PyTorch, and the TESS and ZTF teams. This project uses data from public archives hosted by MAST and IRSA.

## License

Apache 2.0. See [`LICENSE`](LICENSE).
