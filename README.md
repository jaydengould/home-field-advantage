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

**Status: in development — Phases 1–6b complete (all three loaders build validated panels; sport-blind features populate the model-ready `data/processed/` panels; descriptive HFA quantified with a data-sanity gate; the causal TWFE dose-response engine and the co-primary on/off DiD both estimate the crowd effect per sport, in agreement). Phase 7 (bubble decomposition) next. 104/104 tests.**

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
  spread). → `data/interim/mlb.parquet` (2018–2023, 13,272 games). `crowd_pct`
  mean by season: `.66 .65 .004 .44 .63 .68` — empty 2020, partial-reopening 2021.
- ✅ **Phase 3 (NBA)** — NBA loader on the same `_espn.py` contract → `data/interim/nba.parquet`
  (2018–2023, 7,562 games). All-indoor (`is_dome=True`, weather null); the
  **2020 Orlando bubble** (171 games) is flagged via venue+season (`is_bubble`) and excluded
  from the pooled model but kept for the Phase-7 decomposition; TOR's 2021 Tampa relocation
  flagged. `crowd_pct` mean by season: `.94 .93 .79 .124 .89 .94` — **2021 (0.124) is the
  strongest treatment signal of the three sports** (2020's 0.79 is a mix of full pre-March
  games + the empty bubble, which is why only 2021 is treated).
- ✅ **Capacity fix (all sports)** — a treated season's capacity is `max(non-treated
  fallback, that season's own max)`, so a genuinely reopened full house (e.g. the 2021 Rays
  ALDS after caps lifted) isn't under-anchored into a `crowd_pct > 1`. Preserves the
  anti-inflation intent (a suppressed season never lowers capacity); no-op for NFL.
- ✅ **All-Star exhibition fix (loaders)** — ESPN types All-Star/Rising-Stars games as
  regular season (`season_type=2`), so they had slipped the loaders' filter with
  non-franchise abbrevs (MLB `AL`/`NL`; NBA `DUR`/`GIA`/`LEB`/`STE`/`USA`/`WORLD`).
  `_select_games` now excludes them (5 MLB + 9 NBA rows), and the two parquets were
  regenerated. `crowd_pct` season means are unchanged.
- ✅ **Phase 4 — sport-blind features** → `data/processed/{nfl,mlb,nba}.parquet`, each
  re-validated. One sport-blind module (`src/features/build.py`) populates the placeholder
  columns: **Elo** (a "middle" 538-grounded rating — params web-verified; stores *pre-game*
  ratings so a game's own result never enters its own control; HFA lives only in the
  win-probability, not the stored rating; rest/travel are *not* baked in — they are separate
  controls), **rest days** (per `(sport, team, season)`; first game of a season is null),
  and **travel km** (haversine from a web-verified city-coordinate lookup; bubble → 0,
  neutral/relocated → null). Elo sanity gate (bug-detection, HFA-inclusive): accuracy
  NFL `0.627`, MLB `0.577`, NBA `0.639` — sensible and ranking the right teams; the ~2-pt
  gap to 538's *full* model is the deliberate cost of the simpler "middle" Elo, not a bug
  (no `k`-tuning for a control variable).
- ✅ **Phase 5 — descriptive HFA** → `results/tables/descriptive_hfa.csv` +
  `results/figures/hfa_by_season.png`. One sport-blind module (`src/viz/descriptive.py`)
  reports home win% and mean scoring margin (with naive iid SEs) by sport × season, plus a
  pooled full-crowd headline. Clean home games only (regular season; neutral/relocated/bubble
  excluded). Playoffs are excluded from the descriptive number (home advantage there is
  confounded by seeding, and COVID-season playoffs were largely neutral-site/bubble). A
  **data-sanity gate** (data-driven off each sport's real treated seasons — NFL 2020, MLB
  2020–21, NBA 2021) checks for positive full-crowd HFA and a COVID-season margin dip before
  any modeling begins.
  - **Findings:** pooled home win% is **NFL .552, NBA .570, MLB .528**. The empty-stadium
    effect is visible but noisy at the descriptive level — statistically cleanest in **NBA
    margin** (2021 dips 2.26 → 0.92, *z* ≈ 2.6) and **NFL win%** (2020 drops to a coin-flip
    .504). **MLB scoring-margin HFA is noise-dominated** (pooled +0.04 runs, below its own
    season-to-season noise), so the design's "margin = more power" premise fails for baseball
    — win% is MLB's usable signal. Carried forward as an explicit consideration for Phase 6a.
- ✅ **Phase 6a — causal TWFE dose-response** → `results/tables/twfe_{nfl,mlb,nba}.csv`,
  `results/tables/twfe_cross_sport.csv`, `results/figures/twfe_crowd_effect.png`. One
  sport-blind estimator (`src/models/twfe.py`) fits two outcomes — scoring margin and a
  win-probability **linear probability model** (whose `crowd_pct` coefficient is the
  cross-sport-comparable Δ win-prob, and MLB's usable signal) — over two samples (pooled +
  a restricted robustness check), with home-team fixed effects and cluster-robust SEs.
  - **Design correction (the headline lesson):** the spec's original **two-way** (team +
    season) fixed effects **inverted every coefficient** (NFL margin −8.75, opposite the
    descriptive dip). The COVID crowd shock is ~a *pure season-level* treatment (`crowd_pct`
    ≈ 0.97 every normal season, ≈ 0.07 in the treated one), so full season dummies are
    near-collinear with the treatment and absorb the very between-season contrast that *is*
    the natural experiment. **Fix: team fixed effects only + a linear season trend** (nets
    out smooth league drift without erasing the COVID contrast). A time-clustered treatment
    is a within-team before/during/after comparison — full time effects delete it.
  - **Estimates (team FE + trend):** a full crowd is worth **NFL +1.7 pts** of margin
    (≈ +4.6 pp win prob), **NBA +1.1 pts** (≈ +1.5 pp), **MLB ≈ 0** (noise, as Phase 5
    predicted). Signs match the descriptive dip; per-sport CIs are wide and cross zero
    (underpowered — a finding, not a failure).
  - **Honesty caveats carried to the write-up:** (1) there is **no within-season dose curve**
    for any sport (within-2020 NFL dose↔margin corr ≈ 0) — all three are effectively on/off;
    (2) the estimate conflates the crowd with **any other 2020–21 league-wide shift** (the
    trend removes only smooth drift, and a treated-season dummy is collinear with the crowd),
    so **Phase 7's bubble decomposition is the disentangler**; (3) the NFL betting-spread
    sensitivity is a **post-treatment bad control** (the spread already prices in the empty
    stadium), so its attenuation is mechanical, not fragility. This also promotes **Phase 6b
    (on/off DiD) to co-primary** — the natural estimator for a treatment that hit everyone at
    once.
- ✅ **Phase 6b — causal on/off DiD** → `results/tables/did_{nfl,mlb,nba}.csv`,
  `results/tables/did_cross_sport.csv`, `results/figures/did_hfa_shrink.png`. The intuitive
  co-primary companion to 6a: one sport-blind module (`src/models/did.py`) reports the **raw,
  unadjusted before/after** change in home advantage — home-field advantage in full-crowd
  seasons vs treated (empty) seasons, for both outcomes, with cluster-robust SEs and no
  controls (that division of labor is deliberate — 6a is the controlled estimate, 6b is the
  headline number a human can hold).
  - **What the "2×2 DiD" actually is:** no untreated *group* exists (COVID hit every team at
    once), but the outcome is already `home − away`, so the **away team is the implicit control
    group** and other seasons are the **control *period***. It nets out symmetric league-wide
    2020–21 shifts but not home-specific ones, so it carries **the same confound as 6a** — it's
    the intuitive picture and a sanity check, not cleaner identification (Phase 7 disentangles).
  - **Estimates agree with 6a within ~10–25%:** a full crowd is worth **NFL +1.6 pts** of
    margin (≈ +4.8 pp win prob), **NBA +1.3 pts** (≈ +2.4 pp), **MLB ≈ 0** (a faint,
    non-significant wrong-sign — statistically zero, as Phase 5 predicted). The dumbbell figure
    (`did_hfa_shrink.png`) makes the shrink the subject: NFL/NBA home advantage collapses toward
    zero without fans, MLB is a flat stub. Cross-method agreement (descriptive → TWFE → DiD)
    is itself reassuring; per-sport CIs remain wide and cross zero (underpowered, not a failure).

## Roadmap (working, subject to change)

Per-sport logic lives only in `src/data/`; everything downstream is sport-blind.
NFL is the pilot — prove the vertical slice on one sport, then the others conform.

| Phase | What | Status |
|---|---|---|
| 1 | Schema contract validator + `config/sports.yaml` | ✅ done |
| 2 | NFL pilot loader → validated panel (ESPN attendance + empirical Option-A capacity) | ✅ done |
| 3 | MLB + NBA loaders conform to the contract (on shared `src/data/_espn.py`) | ✅ done |
| 4 | Sport-blind features — Elo, `crowd_pct`, rest, travel | ✅ done |
| 5 | Descriptive HFA (win% / margin by sport & season) — data sanity gate | ✅ done |
| 6a | Causal — TWFE dose-response (the engine; team FE + trend, not two-way FE) | ✅ done |
| 6b | Causal — on/off DiD (**co-primary**, not back-pocket — treatment is time-clustered) | ✅ done |
| 7 | Bubble decomposition + seeding-games placebo | ⬅ next |
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

Two stages. **Loaders** pull from ESPN and cache every response under
`data/raw/<sport>/espn/` (immutable, write-once), then write the validated panel to
`data/interim/<sport>.parquet`. **Features** read the interim panels and write the
feature-complete, model-ready `data/processed/<sport>.parquet`. All of `data/` is
gitignored — a fresh clone re-fetches (loaders) then rebuilds (features).

```bash
# 1. Loaders → data/interim/
.venv/bin/python -m src.data.nfl              # → data/interim/nfl.parquet
.venv/bin/python -m src.data.mlb              # → data/interim/mlb.parquet   (long: see note)
.venv/bin/python -m src.data.nba              # → data/interim/nba.parquet   (long: see note)
.venv/bin/python -m src.data.mlb --smoke      # quick real-data dose check, no parquet write
.venv/bin/python -m src.data.nba --smoke      # quick 2020+2021 dose check (bubble + reopening ramp)

# 2. Features → data/processed/ (reads interim, no ESPN fetch; prints the Elo accuracy gate)
.venv/bin/python -m src.features.build        # → data/processed/{nfl,mlb,nba}.parquet

# 3. Descriptive HFA → results/ (reads processed; prints the PASS/CHECK sanity gate)
.venv/bin/python -m src.viz.descriptive       # → results/tables/descriptive_hfa.csv + results/figures/hfa_by_season.png

# 4. Causal TWFE dose-response → results/ (reads processed; prints per-sport crowd coefs + NFL spread sensitivity)
.venv/bin/python -m src.models.twfe           # → results/tables/twfe_{nfl,mlb,nba}.csv, twfe_cross_sport.csv + results/figures/twfe_crowd_effect.png

# 5. Causal on/off DiD → results/ (reads processed; prints the raw before/after HFA per sport)
.venv/bin/python -m src.models.did            # → results/tables/did_{nfl,mlb,nba}.csv, did_cross_sport.csv + results/figures/did_hfa_shrink.png
```

**Note on the long pulls (MLB ~14.5k games, NBA ~7.9k):** a full pull is thousands of
ESPN requests, and ESPN soft-rate-limits sustained fetching (transient 502s). The loader
retries with backoff and tolerates the rare unlucky game (counted as missing; a >5%
coverage gate guards systemic loss), so a cold full pull takes ~hours and may need a few
cache-warm re-runs to complete. The cache is immutable/write-once, so each re-run resumes
where it left off and subsequent runs are fast.
