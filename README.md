# home-field-advantage

A cross-sport study of home-field advantage across MLB, NBA, and NFL with two
parts: (1) **quantify** it descriptively (home win %, scoring margin) and
(2) estimate the **crowd-attributable slice** of it, using the COVID
empty/partial-stadium period (**full 2020–21 restriction window**) as a natural
experiment. The modeled outcome is **scoring margin** (more statistical power),
with **home win % reported alongside** as the intuitive number. Each sport is
analyzed separately, then combined into a cross-sport comparison, with a
paper-quality write-up rendered via Quarto (PDF + HTML).

Design: `docs/superpowers/specs/2026-06-29-home-field-advantage-design.md`.

**Status: in development — Phases 1–2 complete, Phase 3 in progress (MLB done, NBA next). 48/48 tests.**

## Progress

- ✅ **Design approved** — two-part question (descriptive + causal), continuous
  `crowd_pct` dose identified off policy capacity caps, TWFE panel estimator.
- ✅ **Attendance spikes (all three sports)** — the ESPN summary endpoint carries
  `gameInfo.attendance` for NFL, MLB, and NBA (empty 2020 games are a real `0`). The
  native packages don't: `nfl_data_py` has no attendance, `pybaseball` nulls the 2020
  empties (destroying the dose), `nba_api` returns `None`. **Decision: all sports
  single-source on ESPN** (scoreboard for schedule/scores + summary for attendance,
  keyed by ESPN event id — no cross-source join).
- ✅ **Phase 1 — schema contract + config** — `src/schema.py` (`validate()` over a
  29-column unified panel) and `config/sports.yaml` (per-sport COVID windows).
- ✅ **Phase 2 — NFL pilot loader** → `data/interim/nfl.parquet` (2018–2023, 1657
  games). **Capacity = empirical full-house (Option A)**, *not* a static seated-capacity
  lookup: ESPN reports *announced* attendance (which exceeds seated capacity), so each
  stadium-season's capacity is its own max announced attendance, and treated (2020–21)
  seasons borrow their non-treated max. `crowd_pct` mean by season: `.97 .97 .066 .97
  .98 .98` — a clean before/during/after.
- ✅ **Phase 3 (MLB)** — MLB loader + shared **`src/data/_espn.py`** (cached ESPN fetch,
  scoreboard-by-date walk, and the Option-A capacity/coverage helpers, now shared so all
  sports compute `crowd_pct` identically). No weather for MLB (not a confounder of a
  policy-identified margin estimate); quality controlled via Elo (baseball has no point
  spread). Real-data smoke confirms the 2020 dose: **regular season 100% empty**. NBA
  loader is next.

## Roadmap (working, subject to change)

Per-sport logic lives only in `src/data/`; everything downstream is sport-blind.
NFL is the pilot — prove the vertical slice on one sport, then the others conform.

| Phase | What | Status |
|---|---|---|
| 1 | Schema contract validator + `config/sports.yaml` | ✅ done |
| 2 | NFL pilot loader → validated panel (ESPN attendance + empirical Option-A capacity) | ✅ done |
| 3 | MLB + NBA loaders conform to the contract (on shared `src/data/_espn.py`) | 🔨 MLB done, NBA next |
| 4 | Sport-blind features — Elo, `crowd_pct`, rest, travel | |
| 5 | Descriptive HFA (win% / margin by sport & season) — data sanity gate | |
| 6a | Causal — TWFE dose-response (the engine) | |
| 6b | Causal — back-pocket on/off DiD (intuitive sanity check) | |
| 7 | Bubble decomposition + seeding-games placebo | |
| 8 | Quarto write-up → PDF + HTML | |

Each phase is its own spec → plan → build loop (see `docs/superpowers/`).

## Layout

- `config/sports.yaml` — treatment windows and per-sport parameters
- `data/{raw,interim,processed}/` — raw is immutable input; the rest is derived
- `src/data/` — per-sport loaders → unified panel schema
- `src/schema.py` — the unified panel contract (`validate()`); imported everywhere
- `src/features/`, `src/models/`, `src/viz/` — sport-blind feature building, models, plots
- `results/{figures,tables}/` — generated outputs
- `paper/` — Quarto write-up + references.bib
- `tests/`

## Setup

```bash
.venv/bin/pip install -r requirements.txt   # + pytest (dev)
.venv/bin/pytest -q                          # run the test suite
```

## Building the data

Loaders pull from ESPN and cache every response under `data/raw/<sport>/espn/`
(immutable, write-once), then write the validated panel to `data/interim/<sport>.parquet`.
Downloaded data is gitignored — a fresh clone re-fetches.

```bash
.venv/bin/python -m src.data.nfl              # → data/interim/nfl.parquet
.venv/bin/python -m src.data.mlb --smoke      # quick 2019+2020 dose check
.venv/bin/python -m src.data.mlb              # → data/interim/mlb.parquet (long: see note)
```

**Note on MLB:** ~2,430 games/season means a full pull is thousands of ESPN requests,
and ESPN soft-rate-limits sustained fetching (transient 502s). The loader retries with
backoff and tolerates the rare unlucky game (counted as missing; a >5% coverage gate
guards systemic loss), so a cold full pull takes ~hours and may need a couple cache-warm
re-runs to complete. The cache persists, so subsequent runs are fast.
