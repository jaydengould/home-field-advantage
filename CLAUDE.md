# home-field-advantage

## Goal

Estimate the **causal effect of crowd presence on home-team win probability**,
using the 2020 empty-stadium COVID season as a natural experiment across MLB,
NBA, and NFL. Each sport is analyzed separately, then combined into a
cross-sport comparison. Final output: a paper-quality Quarto write-up (PDF + HTML).

## Tech stack

- Python 3.11+ (`.venv`)
- pandas / numpy — data wrangling
- statsmodels / linearmodels — causal estimation (DiD, panel models)
- pybaseball / nba_api / nfl_data_py — per-sport data sources
- matplotlib / seaborn — figures
- Quarto — paper rendering (system CLI, not the pip package)

## Core design principles

1. **The sport is just a PARAMETER.** All three sports normalize into a single
   unified game-level panel schema. Sport-specific logic lives **only** in
   `src/data/`. Everything downstream — feature building, modeling, plots — is
   sport-blind and written once.

2. **`data/raw/` is never overwritten.** Downloaded source data is treated as
   immutable. Loaders read from `data/raw/`, write derived data to
   `data/interim/` or `data/processed/`. Never mutate raw in place.

## Layout

- `config/sports.yaml` — treatment dates and per-sport parameters
- `data/{raw,interim,processed}/` — raw is immutable input; the rest is derived
- `src/data/` — per-sport loaders → unified panel schema
- `src/features/` — sport-blind feature building
- `src/models/` — sport-agnostic causal models
- `src/viz/` — sport-blind plotting
- `results/{figures,tables}/` — generated outputs
- `paper/` — Quarto write-up + references.bib
- `notebooks/` — exploration
- `tests/`

## Working convention

**Update this CLAUDE.md at the end of each working session** — record decisions
made, schema/config changes, and what's next. It's the memory that survives
between sessions.

## Next session — design walkthrough + brainstorming

Before writing any loader/model code, walk through the full pipeline end to end
and settle these design choices (they cascade into everything downstream):

1. **Unified panel schema** — define the exact columns every `src/data/` loader
   returns. Keystone: the "sport is a parameter" promise depends on this being
   right and identical across MLB/NBA/NFL. One row per game.
2. **Treatment definition** — 2020 crowds were partial/staggered (NFL admitted
   some fans, varying by stadium/week). Decide: binary (empty vs. not) or
   continuous (capacity %). Drives whether it's clean DiD or messier.
3. **Comparison / control** — DiD against pre-2020 seasons? Synthetic control
   per team? This shapes the whole `src/models/` design.
4. **Confounders** — 2020 also changed schedules, travel/rest, and roster
   availability (COVID absences). List the threats to "crowd caused it" before
   modeling.

Open prep: bring an opinion on #2 — it has the biggest research-design
consequences.

## Status

Scaffold only. Analysis logic, loaders, and models come in later sessions.
