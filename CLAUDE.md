# home-field-advantage

## Goal

Two-part study across MLB, NBA, and NFL: (1) **quantify** home-field advantage
descriptively (home win %, scoring margin) and (2) estimate the **causal
crowd-attributable slice** of it, using the COVID empty/partial-stadium period
(**full 2020–21 restriction window**) as a natural experiment. The modeled
outcome is **scoring margin** (more statistical power), with **home win % reported
alongside** as the intuitive number. Each sport is analyzed separately, then
combined into a cross-sport comparison. Final output: a paper-quality Quarto
write-up (PDF + HTML).

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

**Be brutally honest.** This is a research project — a flattering wrong answer
is worse than useless, it corrupts the conclusion. Push back when the user is
wrong, name methodological flaws plainly, flag endogeneity/selection/sample-size
problems even when unwelcome, and never agree just to be agreeable. Distinguish
what the data can support from what it can't.

**Update this CLAUDE.md at the end of each working session** — record decisions
made, schema/config changes, and what's next. It's the memory that survives
between sessions.

## Design decisions (settled 2026-06-29)

Full design: `docs/superpowers/specs/2026-06-29-home-field-advantage-design.md`.

1. **Two-part question** — descriptive ("how big is HFA?", charts/numbers) +
   causal ("how much is the crowd?"). The descriptive number makes the causal
   number interpretable.
2. **Treatment** — *continuous* crowd dose (`crowd_pct`), identified off
   *policy capacity caps* over the *full 2020–21 restriction window* (not 2020
   only). Endogenous historical attendance kept as a *labeled descriptive*
   companion, never the causal headline.
3. **Estimator** — TWFE panel (`home_margin ~ crowd_pct + controls + team_FE +
   season_FE`) is the engine; a simple on/off 2×2 DiD is a back-pocket section;
   synthetic control skipped as overkill. Outcome = scoring margin (power),
   win% reported alongside (intuition).
4. **Confounders** — team quality (→ Elo now, betting lines = TODO), rest,
   travel, weather as controls. NBA bubble + relocated/neutral "home" games
   flagged and EXCLUDED from the main model.
5. **Bubble** — mined separately as a crowd-vs-travel *decomposition* + a
   seeding-games *placebo*; never in the pooled model.
6. **Schema** — ~25-column unified panel, one row per game, identical across
   sports (sports null what doesn't apply). Sport logic only in `src/data/`.

## Implementation phasing

Small, independently-runnable phases. NFL is the pilot sport (prove the vertical
slice on one sport, then the others conform). Full detail per phase — including
the "done when" check — is in the spec §8; this list is the quick reference.

1. **Schema contract + config** — panel columns as a code validator + fill
   `config/sports.yaml` with per-sport COVID windows.
2. **Pilot loader (NFL) → panel** — one sport emitting the validated schema.
3. **Remaining two loaders (MLB, NBA)** — conform to the proven contract.
4. **Sport-blind features** — Elo, `crowd_pct`, rest, travel.
5. **Descriptive HFA** — win% / margin by sport & season + figures (data sanity gate).
6a. **Causal — TWFE dose-response** (the engine).
6b. **Causal — back-pocket on/off DiD** (intuitive section + sanity check).
7. **Bubble decomposition + placebo**.
8. **Quarto write-up** → PDF + HTML.

**How to build:** today's spec is the umbrella design, not a single build script.
Run `writing-plans` + execution **per phase** (the spec is too big for one plan) —
each phase is its own small spec→plan→build loop. Do NOT plan the whole project
at once.

**Next session:** run `writing-plans` for **Phase 1 only**, then execute it.
No analysis code exists yet.

## Status

Design complete and approved. No analysis code yet — implementation begins
Phase 1 next session.
