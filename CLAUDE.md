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

## Pre-Phase-1 attendance spike (run 2026-06-29) — PASS

Verified risk #1 (does the `crowd_pct` treatment variable exist?). **It does**,
but **not where the spec assumed**. Findings:

**Treatment source = ESPN public API, NOT nfl_data_py.**
- `nfl_data_py` carries **zero** attendance — confirmed across all its
  `import_*` functions. No attendance/capacity/crowd field anywhere.
- Pro-Football-Reference *has* attendance but hard-`403`s every automated
  request (Sports Reference blocks scrapers — curl and the fetch proxy both
  blocked). Not a usable source here.
- **ESPN summary endpoint works:**
  `https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event=<ESPN_ID>`
  → `gameInfo.attendance`. The `<ESPN_ID>` is already in the schedule
  (`espn` column). So the NFL loader is: `import_schedules` → join attendance
  via the `espn` id.
- Sampled 2019/2020/2021: clean within-team dose ramp — 2019 full (~62–70k),
  2020 staggered partial (15,895 / 10,166 / **0** / **0**), 2021 reopened
  (~62–77k). Empty-stadium `0`s are **real zeros, not nulls**. This is exactly
  the staggered-cap variation the TWFE engine identifies off.

**Capacity is NOT in either API.** ESPN returns `gameInfo.venue.capacity =
None`. Capacity is a static venue property → build a small `venue → capacity`
lookup file. It rides on the same static lookup the spec already needs for
Phase 4 travel coords (`venue → lat/long`). `crowd_pct = attendance / capacity`
is then constructible.

**Bonus — controls already free in `nfl_data_py.import_schedules`:** the schedule
(269 rows for 2020) already supplies several columns the spec scheduled as later
work. Full column list:
`game_id, season, game_type, week, gameday, weekday, gametime, away_team,
away_score, home_team, home_score, location, result, total, overtime,
old_game_id, gsis, nfl_detail_id, pfr, pff, espn, ftn, away_rest, home_rest,
away_moneyline, home_moneyline, spread_line, away_spread_odds, home_spread_odds,
total_line, under_odds, over_odds, div_game, roof, surface, temp, wind, ...,
referee, stadium_id, stadium`.
- **`spread_line` = `closing_spread`** — the betting line the spec marked a
  *future TODO* (§9) is available NOW for NFL, per game. Promote from TODO.
- `home_rest`/`away_rest` → `home_rest_days`/`away_rest_days` directly.
- `temp`/`wind` → weather columns; `roof` (`outdoors`/`dome`/`closed`) → `is_dome`.
- `location` (`Home`/`Neutral`, 4 neutral games in 2020) → `neutral_site` flag.
- `referee` present → enables the deferred crowd→referee mechanism sub-study (§9).
- `result` = home_margin (home-perspective); `pfr`/`espn`/`gsis` are cross-source
  join ids.

**Build-time notes carried forward:**
- `crowd_pct = 0` is a REAL value (empty stadium), not missing — validator and
  feature code must not coerce empty games to null.
- ESPN needs polite throttling + caching: cache raw responses to
  `data/raw/nfl/` (immutable) so each game is fetched once.
- Open question for MLB/NBA: confirm an equivalent ESPN summary endpoint
  (`.../baseball/mlb/...`, `.../basketball/nba/...`) carries attendance before
  Phase 3 — the nfl_data_py-lacks-attendance pattern may repeat per sport.

## Phase 1 — schema contract + config (done 2026-06-29) — COMPLETE

Brainstormed → spec → plan → built via subagent-driven development. 15/15 tests
passing. **Git is user-owned — never run git commit/push/branch; the user
commits their own history.**

**Built:**
- `src/schema.py` — the unified panel contract. `Col` spec dataclass +
  `COLUMNS` dict (29 columns, test-locked) + `validate(df)`. Sport-blind,
  config-free (no YAML import). Imported by everything downstream.
- `tests/test_schema.py` (13 tests), `tests/test_config.py` (2 tests).
- `config/sports.yaml` — `treated_seasons` per sport.
- `pyproject.toml` — pytest `pythonpath = ["."]` (so `from src.schema import …`
  resolves; `src/` is a namespace package, no `__init__.py`).
- Specs/plans under `docs/superpowers/{specs,plans}/2026-06-29-phase1-*`.

**Design decisions settled this phase:**
- **Validator = hand-rolled** (`Col` + `validate()`), not pandera/pydantic — no
  new dependency, the spec doubles as documentation.
- **`validate()` collects ALL violations** into one `ValueError` (not fail-fast)
  — faster to debug a data panel.
- **Strictness = structural + domain + conditional.** Conditional rules:
  `home_margin == home_score - away_score`; `crowd_pct ≈ attendance/capacity`
  (`crowd_pct == 0` stays valid); `home_win` matches margin sign, null only on
  ties; **`is_dome ⇒ weather null` (forward only)**.
- **Weather rule is one-directional** — dome⇒null is a hard error; outdoor⇒
  weather-present is NOT enforced (sources legitimately lack weather; `roof` is
  three-state incl. `closed` retractable). Reverse rule would cry wolf.
- **Nullable extension dtypes** for the 3 nullable int/bool columns (`home_win`
  → `boolean`; `home_rest_days`/`away_rest_days` → `Int64`) so a null doesn't
  silently upcast int→float and break the dtype contract. `Col` is hashable
  (`values` is a `frozenset`).
- **`covid_era` = treated-season set, not a date window.** Reopening was
  per-team-per-week (state policy), so a per-sport date is false precision;
  `crowd_pct` already carries the exact per-game dose. `covid_era`'s real job is
  to mark which crowd variation is **policy-driven (exogenous)** vs
  demand-driven (endogenous). It stays config-free in `validate()`; the *loader*
  sets it from `config/sports.yaml`.

**Deferred / open items (carry forward):**
- **Phase 6a open decision (important):** does the causal model **restrict the
  sample** to COVID-window games (+ pre-COVID baseline) or **pool all seasons**
  and lean on FE? Different estimates — matters because normal-season `crowd_pct`
  is endogenous (bad teams draw small crowds *and* lose). Decide explicitly in 6a.
- **Phase 3 confirm:** MLB/NBA `treated_seasons` are best-effort placeholders;
  confirm exact season labeling + that ESPN's summary endpoint carries
  attendance for baseball/basketball before building those loaders.
- **Add `pytest` to `requirements.txt`** (or a dev-requirements) — it was missing
  from the venv and installed ad hoc during Phase 1.
- Two trivial code Minors left as-is (dead `notna()` guards in the `crowd_pct`
  check; one uncovered-but-correct edge case for decided-game + null `home_win`).

## Status

**Phase 1 COMPLETE** (schema validator + config, 15/15 tests). Next: **Phase 2 —
NFL pilot loader** (the first real consumer of `validate()`): `import_schedules`
→ join ESPN attendance via the `espn` id → build `venue → capacity` lookup →
emit the validated panel to `data/interim/`. Run brainstorm + `writing-plans`
for Phase 2.
