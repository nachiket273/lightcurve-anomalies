# Architecture

This document describes how `lightcurve-anomalies` is structured and why. It is a living document; significant changes are recorded in the decision log at the bottom.

## 1. Goals and non-goals

**Goals**
- A reproducible pipeline from raw archive light curves to a ranked, vetted candidate list.
- A measured understanding of the pipeline's sensitivity (injection-recovery).
- Modular stages, so each week's work slots in without rewrites.

**Non-goals**
- Competing with survey-team pipelines on throughput or completeness.
- Real-time alert processing (possible later extension).
- A general-purpose astronomy framework.

## 2. High-level pipeline

```
  Archives (MAST, IRSA)
          │
          ▼
  ┌───────────────┐   raw FITS/parquet (immutable)
  │  1. Ingest    │──────────────────────────────┐
  └───────────────┘                              │
          │                                      ▼
          ▼                              data/raw/
  ┌───────────────┐
  │ 2. Preprocess │  quality masks, normalization, detrending
  └───────────────┘
          │                              data/interim/
          ▼
  ┌───────────────┐        ┌────────────────────┐
  │ 3. Search     │◄───────│ 3b. Injection      │  synthetic signals
  │  (LS, BLS,    │        │   (recovery tests) │  → completeness maps
  │  single-event)│        └────────────────────┘
  └───────────────┘
          │
          ▼
  ┌───────────────┐
  │ 4. Features / │  hand-crafted features, learned embeddings
  │   Embeddings  │
  └───────────────┘
          │                              data/processed/
          ▼
  ┌───────────────┐
  │ 5. Anomaly    │  scores + ranking
  │   scoring     │
  └───────────────┘
          │
          ▼
  ┌───────────────┐
  │ 6. Vetting    │  catalog cross-match, artifact checks (deterministic)
  └───────────────┘
          │
          ▼
  ┌───────────────┐
  │ 7. LLM triage │  reads structured evidence, writes verdict + summary
  └───────────────┘
          │
          ▼
     candidates/   (one card per object)  +  weekly digest
```

## 3. Data layout and contracts

```
data/                      # gitignored
├── raw/                   # downloaded as-is; never modified
│   ├── tess/<sector>/<tic_id>.fits
│   └── ztf/<field>/<oid>.parquet
├── interim/               # cleaned, detrended light curves
├── processed/             # features, embeddings, scores
└── cache/                 # catalog query results
```

**Canonical light-curve schema** (parquet, one file per target-per-mission):

| column | type | notes |
|--------|------|-------|
| `time` | float64 | BTJD for TESS, MJD for ZTF; mission recorded in metadata |
| `flux` | float32 | normalized to median 1.0 after preprocessing |
| `flux_err` | float32 | propagated through all steps |
| `quality` | uint16 | bitmask; non-zero rows are excluded downstream |
| `band` | category | TESS or ZTF g/r/i |

Metadata (target ID, mission, sector/field, pipeline version, config hash) is stored in the parquet file's key-value metadata so every artifact is traceable to the code and config that produced it.

All stages read and write this schema. A stage never reaches into another stage's internals; it only consumes files and a config.

## 4. Modules

| Module | Responsibility | Key dependencies |
|--------|----------------|------------------|
| `lca.io` | Archive queries, download, local caching, schema conversion | lightkurve, astroquery |
| `lca.preprocess` | Quality masking, outlier clipping, normalization, detrending | numpy, scipy, wotan |
| `lca.search` | Lomb-Scargle, BLS, single-event (box/template) search | astropy, scipy |
| `lca.injection` | Generate synthetic transits, flares, eclipses; inject into real light curves; compute recovery rates | batman or simple box models |
| `lca.features` | Period, amplitude, skew, autocorrelation, flare stats, etc. | numpy, scipy |
| `lca.models` | Baseline classifier, autoencoder/contrastive encoder, anomaly scorers | scikit-learn, PyTorch |
| `lca.vetting` | SIMBAD/TOI/Gaia/VSX cross-match, centroid and contamination checks, candidate cards | astroquery |
| `lca.triage` | LLM triage agent: evidence packet in, schema-validated verdict out | anthropic SDK, pydantic |
| `lca.runner` | Incremental state tracking, scheduled-run entry point | sqlite3 |
| `lca.viz` | Standard diagnostic plots | matplotlib |
| `lca.cli` | `lca` command wiring stages together | typer |

**Rules of the road**
- Pure functions where possible; I/O isolated in `lca.io` and stage runners.
- Every stage has a config section and writes its config hash into outputs.
- No notebook-only logic: anything reused moves into `src/lca/`.

## 5. Configuration

YAML files under `configs/`, loaded into typed dataclasses (pydantic). Layers:

- `configs/catalogs/`: target lists (known objects, random field samples)
- `configs/pipeline/`: preprocessing and search parameters
- `configs/models/`: model hyperparameters and training setup

A run is identified by `(code git SHA, config hash, target list hash)`. Re-running with identical inputs must reproduce identical outputs (fixed seeds throughout).

## 6. Injection-recovery (the trust layer)

Injection-recovery is a first-class component, not an afterthought.

1. Sample parameters (period, depth, duration, epoch, host magnitude) from a grid or prior.
2. Inject the synthetic signal into a real light curve (keeps real noise and systematics).
3. Run the full preprocess + search stages unchanged.
4. Record whether the signal was recovered (period within tolerance, SNR above threshold).
5. Aggregate into completeness maps (recovery rate vs. depth, period, magnitude).

Outputs are stored under `data/processed/injection/` and summarized in the final report. Any detection statistic used to rank candidates should be interpretable against these maps.

## 7. Anomaly scoring

Planned approaches, introduced incrementally:

1. **Feature-space baseline:** isolation forest / Mahalanobis distance on hand-crafted features.
2. **Reconstruction-based:** autoencoder on phase-folded or fixed-length windows; score = reconstruction error.
3. **Embedding-based:** contrastive or self-supervised encoder; score = distance to nearest neighbors or density estimate.

Scores are always accompanied by: the method, the model version, and a sanity check on labeled known-weird objects (e.g., known eclipsing binaries held out as "should be flagged" tests).

Anomaly scores are ranks, not probabilities. Final ordering may combine methods via rank aggregation.

## 8. Vetting

Each top-ranked object passes through, in order:

1. **Artifact checks:** quality flags, scattered-light windows, momentum dumps, detector edges, neighboring-star contamination.
2. **Catalog cross-match:** SIMBAD (known type), TOI/KOI (known planet candidate), Gaia (parallax, RUWE, neighbors), VSX (known variable).
3. **Manual review:** plots inspected by eye.
4. **Verdict:** `artifact`, `known`, `unclear`, or `interesting`, recorded in `candidates/<id>.md` using a fixed template.

## 9. LLM-assisted triage

**Where LLMs help, and where they don't.** LLMs are poor at finding anomalies in raw numeric series. Detection stays numeric (stages 3 to 5). LLMs are useful after that, where the work is reading messy evidence and writing it up.

| Task | Tool | Why |
|------|------|-----|
| Find the anomaly | Periodograms, features, autoencoder/embeddings | Numeric, testable, injection-recoverable |
| Query catalogues | `astroquery` (deterministic code) | Facts must come from the archive, not from model memory |
| Interpret the evidence packet | LLM | Combines flags, cross-match hits, and scores into a readable verdict |
| Look at the plot | Multimodal LLM (optional second opinion) | Good at "this looks like scattered light" |
| Write the candidate card and weekly digest | LLM | Cheap, consistent prose |

**Evidence packet** (JSON, built by code, never by the LLM):

```json
{
  "target": "TIC 123456789",
  "anomaly": {"method": "ae_recon", "score": 0.97, "rank": 12, "model_version": "..."},
  "search": {"bls_period_d": 12.4, "snr": 9.1, "n_transits": 1},
  "artifact_flags": {"momentum_dump_overlap": false, "scattered_light": true},
  "crossmatch": {"simbad": null, "toi": null, "vsx": null, "gaia": {"ruwe": 1.1, "neighbors_5arcsec": 2}},
  "plots": ["path/to/fold.png", "path/to/raw.png"]
}
```

**Output contract** (pydantic-validated, rejected and retried if malformed):

```json
{
  "verdict": "known | artifact | unclear | interesting",
  "reasoning": "short, referencing only fields present in the packet",
  "evidence_used": ["crossmatch.toi", "artifact_flags.scattered_light"],
  "follow_up": ["check centroid", "inspect sector 14 background"]
}
```

**Guardrails**
- The LLM only sees the packet. It has no tool for inventing catalogue facts, and any claim not traceable to `evidence_used` is dropped.
- An object can only be labelled `interesting` if every cross-match source was actually queried and returned. A failed or missing query forces `unclear`.
- Verdicts are advisory. `interesting` always goes to manual review before it counts.
- Every prompt, model name, and response is logged alongside the run ID for reproducibility.
- Calibration: a fixed set of known objects (planets, EBs, known artifacts) is run through triage each week. If agreement with the known labels drops, the prompt or model changed something and the run is flagged.
- Cost control: triage runs only on the top-N objects after deterministic vetting (for example N = 50 to 200 per run), not on every light curve.

**Optional later extension:** time-series foundation models (for example Chronos or MOMENT-style encoders) as an additional embedding source behind the `Scorer` interface. Treat these as experimental feature extractors, not as detectors.

## 10. Scheduled runs

Target cadence: **twice per week**, with the weekend run feeding the Sunday review.

| Run | When (UTC) | Stages |
|-----|------------|--------|
| Midweek | Wed 00:00 | Ingest new data, preprocess, search, score, vetting |
| Weekend | Sat 00:00 | Same, plus LLM triage, candidate cards, weekly digest |
| Review (manual) | Sunday | Read digest, inspect `interesting` and `unclear`, update `LOG.md`, tag `week-NN` |

**Incremental by design.** `lca.runner` keeps a small SQLite state file (`data/state.db`) recording, per target and sector/field: ingested, preprocessed, scored, vetted, triaged, with the code SHA and config hash. A run only processes work that is new or whose inputs changed. Re-running is safe.

**Where it runs**

| Option | Good for | Limits |
|--------|----------|--------|
| GitHub Actions cron | Small samples, triage, digest, tests | Runner time and memory caps; no persistent disk, so state goes to an artifact or a dedicated data branch/release |
| Local machine or home server + cron/systemd | Heavy ingest and model scoring | You maintain it |
| Cheap cloud VM on a timer | Large runs | Cost and setup |

Recommended start: **local cron for ingest and scoring, GitHub Actions for the weekend triage and digest**, since triage only needs the compact evidence packets and plots. Move heavier stages to a VM only if local runs get too slow.

**Failure handling**
- Archive outages and rate limits: retry with backoff, then mark the target `deferred` for the next run.
- Any stage failure leaves earlier outputs intact and the digest states what did not run.
- The digest always opens with run metadata (SHA, config hash, counts processed, counts failed).

**Digest contents:** new candidates by verdict, rank changes for returning objects, injection-recovery completeness snapshot, triage calibration result, and a "needs your eyes" list.

## 11. Testing and quality

- **Unit tests** (`pytest`) for preprocessing, search, and injection functions using small synthetic fixtures.
- **Regression tests:** a handful of known planets/binaries must be recovered with expected periods.
- **Data tests:** schema validation on every parquet written.
- **Triage tests:** schema validation of LLM output, a fixed calibration set of known objects, and a test that a missing cross-match source can never yield `interesting`.
- **Tooling:** ruff, mypy (gradual), pre-commit, GitHub Actions running tests on push.

## 12. Weekly workflow

```
Sunday     plan the week, write the goal in LOG.md
Mon-Sat    work in small sessions; notebooks for exploration, src/ for anything reusable
Sunday     review, update LOG.md (tried / failed / next), tag `week-NN`, push
```

Each week must leave `main` in a runnable state.

## 13. Extension points

- Additional surveys (Kepler/K2, ASAS-SN, Gaia photometry) by adding an adapter in `lca.io` that emits the canonical schema.
- Streaming mode for ZTF alerts.
- Additional anomaly models behind the common `Scorer` interface (`fit`, `score`, `save`, `load`).

## 14. Decision log

| # | Date | Decision | Reason |
|---|------|----------|--------|
| 1 | week 0 | Parquet as the canonical light-curve format | Fast, typed, supports metadata, easy with pandas/pyarrow |
| 2 | week 0 | Start with TESS and ZTF only | Open, well-documented, complementary cadences and baselines |
| 3 | week 0 | Injection-recovery built before any ML | Prevents trusting detections the pipeline can't actually recover |
| 4 | week 0 | Config-hash + git SHA stamped on every artifact | Reproducibility across weekly iterations |

| 5 | week 0 | LLMs used for triage and write-up only, not for detection | Detection must be numeric and injection-testable; LLMs are unreliable on raw series |
| 6 | week 0 | All catalogue facts come from deterministic queries, passed to the LLM as an evidence packet | Prevents hallucinated cross-match results |
| 7 | week 0 | Twice-weekly incremental runs with a SQLite state file | Fits the Sunday-to-Sunday cadence and makes re-runs safe |

_Add new rows as decisions are made._
