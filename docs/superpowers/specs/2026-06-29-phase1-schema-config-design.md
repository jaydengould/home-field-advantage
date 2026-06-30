# Phase 1 design — schema contract + config

**Date:** 2026-06-29
**Status:** Approved design (pre-implementation)
**Parent spec:** `2026-06-29-home-field-advantage-design.md` §8.1

## Goal

Deliver the two Phase 1 artifacts from the umbrella spec:

1. The unified panel schema expressed as a **code validator** — the single source
   of truth every loader must emit and every downstream phase imports.
2. A filled **`config/sports.yaml`** defining the `covid_era` window per sport.

**Done when:** `validate()` accepts a correct panel row and rejects a malformed
one (column missing, derived-column mismatch, weather-in-a-dome, out-of-range
`crowd_pct`).

No data loading, no feature population, no models — those are Phase 2+.

## A. The schema contract (`src/schema.py`)

### Single source of truth

A `COLUMNS` dict maps each panel column to a small `Col` spec holding
`(dtype, nullable, min, max, allowed_values)`. The dict *is* the living
documentation of the contract; `src/data/`, `src/features/`, `src/models/`,
`src/viz/` all import it. The column set matches the parent spec §6 exactly.

```python
COLUMNS = {
  "sport":      Col(str, values={"mlb","nba","nfl"}),
  "game_id":    Col(str),
  "season":     Col(int),
  "date":       Col("date"),
  "is_playoff": Col(bool),
  "home_team":  Col(str),   "away_team": Col(str),
  "home_score": Col(int, min=0),  "away_score": Col(int, min=0),
  "home_margin":Col(int),                      # derived: == home_score - away_score
  "home_win":   Col("boolean", nullable=True), # nullable bool — NFL ties
  "attendance": Col(int, min=0),               # 0 is REAL (empty stadium)
  "capacity":   Col(int, min=1),
  "crowd_pct":  Col(float, min=0.0, max=1.05), # tolerance: standing-room over-capacity
  "covid_era":  Col(bool),
  "home_elo":   Col(float),  "away_elo": Col(float),
  "closing_spread": Col(float, nullable=True),
  "home_rest_days": Col("Int64", nullable=True),  # nullable int — null = first game of season
  "away_rest_days": Col("Int64", nullable=True),
  "away_travel_km": Col(float, nullable=True),
  "venue":      Col(str),
  "is_dome":    Col(bool),
  "temp_f":     Col(float, nullable=True),
  "wind_mph":   Col(float, nullable=True),
  "precip":     Col(float, nullable=True),
  "neutral_site": Col(bool), "relocated_home": Col(bool), "is_bubble": Col(bool),
}
```

### `validate(df)` behaviour

Checks the whole DataFrame and **collects all violations, then raises one
readable `ValueError`** summarising which rows broke which rules — *not*
fail-fast. A data panel is debugged far faster when every violation is reported
at once than fix-one-rerun-repeat.

Per-column checks, in order:

1. **Presence** — every `COLUMNS` key is a column in `df`.
2. **Dtype** — column dtype matches the spec (see "Nullable dtypes" below).
3. **Null rule** — non-nullable columns contain no nulls; `crowd_pct == 0` is a
   valid value, never coerced to null.
4. **Domain / range** — `min`/`max` bounds and `allowed_values` (e.g.
   `sport ∈ {mlb,nba,nfl}`, `crowd_pct ∈ [0, 1.05]`, scores `≥ 0`).

Then the **conditional (cross-field) rules**:

- `home_margin == home_score - away_score`.
- `crowd_pct ≈ attendance / capacity` within a small tolerance; `crowd_pct == 0`
  remains valid.
- `home_win == (home_margin > 0)` for decided games; `home_win` may be null
  **only** when `home_margin == 0` (tie).
- **`is_dome ⇒ temp_f / wind_mph / precip all null`** (hard error — a weather
  reading on a domed game signals a mis-join or data leak).

### Resolved judgment call 1 — weather rule is one-directional

Only the forward rule (`is_dome ⇒ weather null`) is enforced. The reverse rule
(`outdoor ⇒ weather present`) is **deliberately not enforced**, because:

- Sources legitimately lack weather for some outdoor games (`nfl_data_py`'s
  `temp`/`wind` already carry `NaN` for real outdoor games). A hard reverse rule
  would fail on good, unfixable data — a validator that cries wolf gets ignored.
- The source `roof` field is three-state (`outdoors` / `dome` / **`closed`**);
  a `closed` retractable roof plays indoor and correctly has null weather, which
  a two-state `outdoor ⇒ has-weather` rule would wrongly flag.

Asymmetry is the honest model: a dome with weather is always a bug; an outdoor
game without weather is just missing data — visible as a null count in the
Phase 5 sanity gate, not a validation failure.

### Resolved judgment call 2 — nullable extension dtypes

pandas cannot store a null in a plain `int`/`bool` column without silently
upcasting (`int → float64`, `bool → object`), which would make the schema's
dtype contract unenforceable. The three genuinely-nullable int/bool columns use
pandas **nullable extension dtypes** so null is representable while the logical
type is preserved:

- `home_win` → `boolean`
- `home_rest_days`, `away_rest_days` → `Int64`

Everything else stays plain: non-nullable ints/bools (`home_score`, `is_dome`,
…) as `int`/`bool`; nullable **float** columns (`closing_spread`, `temp_f`,
`away_travel_km`, …) as `float64` (float already holds `NaN`). Extension dtypes
may need an `.astype()` when handed to older numeric libraries — done at the one
`linearmodels` seam in Phase 6, not pushed onto the schema everywhere else.
Sentinel values (e.g. `-1` for "no rest") are rejected — someone eventually
averages the sentinel in.

### `covid_era` stays config-free in the validator

`validate()` only checks `covid_era` is a bool. The **loader** sets its value
from `config/sports.yaml` (`season in treated_seasons`); a loader test (Phase 2)
covers that correctness. This keeps `validate()` from importing YAML and keeps
the schema layer free of config dependencies.

## B. Config (`config/sports.yaml`)

`treated_seasons` per sport — the seasons whose reduced `crowd_pct` is
**exogenous** (forced by policy caps, not chosen by fans). The continuous
per-game dose lives in `crowd_pct`; this flag only marks *which* seasons' crowd
variation is trustworthy for the causal claim (see "Why a season set" below).

```yaml
# covid_era seasons = the policy-restricted window where a reduced crowd_pct is
# EXOGENOUS (forced by capacity caps, not chosen by fans). The continuous
# per-game dose lives in crowd_pct; this only marks which seasons' crowd
# variation we trust as causal. Season ints follow each data source's labeling.
nfl:
  treated_seasons: [2020]        # 2021 reopened to full capacity league-wide
mlb:
  treated_seasons: [2020, 2021]  # 2020 ~empty, 2021 staggered reopen — confirm in Phase 3
nba:
  treated_seasons: [2020, 2021]  # 2020-21 empty/limited; bubble via is_bubble — confirm in Phase 3
```

NFL is authoritative (the pilot, confirmed by the pre-Phase-1 spike). MLB/NBA
carry best-effort values with an explicit "confirm in Phase 3" comment — honest
placeholders rather than fake precision, since their exact season labeling is
unknown until those loaders are built.

### Why a season set, not a date window (design rationale)

"Reopening" was never a per-sport calendar event — capacity caps were set by
**state/county** health authorities, so the `0% → partial → 100%` ramp was
staggered **per team, per week** (in 2020 the Chiefs sat ~16k while the Jets sat
0 all season). A single per-sport date window would average over exactly the
variation of interest, i.e. false precision. The real per-game dose is already
captured exactly by `crowd_pct = attendance / capacity`. `covid_era` therefore
does only the coarse, season-grain job of marking which crowd variation is
policy-driven (exogenous) vs demand-driven (endogenous), and season grain is the
right resolution for that. Bubble/neutral games are handled separately by
`is_bubble` / `neutral_site`, not by `covid_era`.

## C. The "done when" check (`tests/test_schema.py`)

One test, no framework sprawl. Build a valid one-row panel DataFrame →
`validate()` passes. Mutate it four ways, each must raise with the matching
violation named:

- wrong `home_margin` (≠ `home_score - away_score`),
- weather populated on a `is_dome == True` row,
- `crowd_pct = 2.0` (out of range),
- a dropped column.

## D. Out of scope for Phase 1

- Data loading — Phase 2 (NFL pilot).
- Populating `crowd_pct`, Elo, rest, travel — the columns exist in the contract;
  filling them is Phase 2/4.
- Any model.

## E. Open item carried forward (decide in Phase 6a)

Whether the causal model **restricts the sample** to COVID-window games (plus a
pre-COVID baseline) or **pools all seasons** and leans on fixed effects to
isolate the COVID swing. These give different estimates, and it matters because
normal-season `crowd_pct` variation is endogenous (bad teams draw small crowds
*and* lose). Recorded here so it is decided explicitly in Phase 6a, not
sleepwalked into by pooling endogenous variation.

## Files touched

- `src/schema.py` — new (the `Col` spec, `COLUMNS`, `validate()`).
- `config/sports.yaml` — fill with `treated_seasons` per sport.
- `tests/test_schema.py` — new (the done-when check).
