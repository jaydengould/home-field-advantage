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

**Status: in development — Phases 1–3 complete (all three loaders build validated panels). Phase 4 (features) next. 65/65 tests.**

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
  spread). → `data/interim/mlb.parquet` (2018–2023, 13,277 games, 0 dropped). `crowd_pct`
  mean by season: `.66 .65 .004 .44 .63 .68` — empty 2020, partial-reopening 2021.
- ✅ **Phase 3 (NBA)** — NBA loader on the same `_espn.py` contract → `data/interim/nba.parquet`
  (2018–2023, 7,571 games, 0 dropped). All-indoor (`is_dome=True`, weather null); the
  **2020 Orlando bubble** (171 games) is flagged via venue+season (`is_bubble`) and excluded
  from the pooled model but kept for the Phase-7 decomposition; TOR's 2021 Tampa relocation
  flagged. `crowd_pct` mean by season: `.94 .93 .79 .124 .89 .94` — **2021 (0.124) is the
  strongest treatment signal of the three sports** (2020's 0.79 is a mix of full pre-March
  games + the empty bubble, which is why only 2021 is treated).
- ✅ **Capacity fix (all sports)** — a treated season's capacity is `max(non-treated
  fallback, that season's own max)`, so a genuinely reopened full house (e.g. the 2021 Rays
  ALDS after caps lifted) isn't under-anchored into a `crowd_pct > 1`. Preserves the
  anti-inflation intent (a suppressed season never lowers capacity); no-op for NFL.

## Roadmap (working, subject to change)

Per-sport logic lives only in `src/data/`; everything downstream is sport-blind.
NFL is the pilot — prove the vertical slice on one sport, then the others conform.

| Phase | What | Status |
|---|---|---|
| 1 | Schema contract validator + `config/sports.yaml` | ✅ done |
| 2 | NFL pilot loader → validated panel (ESPN attendance + empirical Option-A capacity) | ✅ done |
| 3 | MLB + NBA loaders conform to the contract (on shared `src/data/_espn.py`) | ✅ done |
| 4 | Sport-blind features — Elo, `crowd_pct`, rest, travel | ⬅ next |
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
.venv/bin/python -m src.data.mlb              # → data/interim/mlb.parquet   (long: see note)
.venv/bin/python -m src.data.nba              # → data/interim/nba.parquet   (long: see note)
.venv/bin/python -m src.data.mlb --smoke      # quick real-data dose check, no parquet write
.venv/bin/python -m src.data.nba --smoke      # quick 2020+2021 dose check (bubble + reopening ramp)
```

**Note on the long pulls (MLB ~14.5k games, NBA ~7.9k):** a full pull is thousands of
ESPN requests, and ESPN soft-rate-limits sustained fetching (transient 502s). The loader
retries with backoff and tolerates the rare unlucky game (counted as missing; a >5%
coverage gate guards systemic loss), so a cold full pull takes ~hours and may need a few
cache-warm re-runs to complete. The cache is immutable/write-once, so each re-run resumes
where it left off and subsequent runs are fast.
