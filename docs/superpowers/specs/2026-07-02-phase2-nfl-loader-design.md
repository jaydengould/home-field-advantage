# Phase 2 — NFL pilot loader → unified panel

**Date:** 2026-07-02
**Phase:** 2 (pilot loader). Prior: Phase 1 (schema contract + config) complete.
**Depends on:** `src/schema.py` (`validate`, `COLUMNS`), `config/sports.yaml`.

## Goal

Emit the first real consumer of the unified panel: an NFL loader that turns
`nfl_data_py` schedules + ESPN attendance into a DataFrame passing `validate()`,
written to `data/interim/nfl.parquet`. NFL is the pilot — prove the vertical
slice on one sport; Phase 3 conforms MLB/NBA to whatever this proves.

**Done when:** real NFL games (default 2018–2023) load, pass `validate()`, and
land in `data/interim/nfl.parquet`; the smoke test asserts against known-good
2020 attendance values.

## Decisions settled in brainstorming (2026-07-02)

1. **Elo bridge = neutral prior.** `home_elo`/`away_elo` are non-nullable but are
   a Phase 4 feature. The loader writes `1500.0` (the honest pre-game Elo prior);
   `away_travel_km` is left null (nullable). The interim panel passes the *full*
   `validate()` — one gate, no subset/partial validator, no schema change. Phase 4
   overwrites Elo + travel.
2. **Season range = config parameter, default 2018–2023.** Rationale:
   - Elo needs only ~1–2 seasons of burn-in (NFL Elo converges within a season and
     regresses toward the mean between seasons, so old seasons wash out on their
     own). 2018–2019 is ample warm-up before the treated 2020 window.
   - Post-COVID seasons (2022–2023) are a **reversion check** — if the crowd drove
     any 2020 HFA dip, HFA should snap back once stadiums refill — *and* they add
     full-crowd "treatment-off" observations that give the TWFE more power. The
     check is asymmetric: reversion corroborates, non-reversion is ambiguous
     (other post-2020 changes exist). 2021 is a muddy "reopening" season; 2022–2023
     are the clean normal anchors.
   - Range is a config param so widening it later (e.g., a deeper descriptive
     baseline for Phase 5) is a one-line change + re-run, not a code change.
3. **Interim format = parquet.** Preserves the `Int64`/`boolean` nullable dtypes
   the schema requires; CSV would coerce them.
4. **Missing attendance = drop-and-log + circuit breaker.** See §Missing-attendance.
5. **Data is free.** `nfl_data_py` (nflverse public releases) and the ESPN summary
   endpoint (public, unauthenticated) cost nothing. ESPN is undocumented/unofficial
   → throttle politely, cache every response.

## Architecture

New module `src/data/nfl.py`, split so the logic is pure and offline-testable.

- **`_build_panel(schedule_df, attendance, capacity) -> pd.DataFrame`** — the pure
  transform. Inputs: raw schedule DataFrame, `{espn_id: attendance|None}` dict,
  `{stadium_id: capacity}` dict. Renames/derives the 29 schema columns, calls
  `validate()`, returns the panel. **No network, no disk.** All mapping logic and
  all tests target this function.
- **`_fetch_attendance(espn_id) -> int | None`** — the only network code. Reads
  `data/raw/nfl/espn/<espn_id>.json` if present; on miss, GETs
  `https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event=<espn_id>`,
  writes the raw JSON to the cache (immutable — never overwritten), throttles
  politely (~0.5–1s between live fetches). Returns `gameInfo.attendance`
  (`None` if the field is absent).
- **`load(seasons) -> pd.DataFrame`** — orchestrator. `import_schedules(seasons)`
  → drop unplayed games (null result/score) → `_fetch_attendance` per `espn` id
  → load capacity lookup → `_build_panel` → return.
- **`main()`** — reads `load_seasons` from config, runs `load`, writes
  `data/interim/nfl.parquet`, prints a run summary (rows written, games dropped
  and why). Supports `--smoke` (see §Smoke test).

Not extracting a shared ESPN helper yet — NFL is the only consumer. Extract in
Phase 3 when MLB/NBA need it (no premature abstraction).

## Column mapping (schedule → 29-col schema)

Direct / renamed from `import_schedules`:

| schema column      | source                                             |
|--------------------|----------------------------------------------------|
| `sport`            | literal `"nfl"`                                     |
| `game_id`          | `game_id`                                           |
| `season`           | `season`                                            |
| `date`             | `gameday` (→ datetime)                              |
| `is_playoff`       | `game_type != "REG"`                               |
| `home_team`        | `home_team`                                         |
| `away_team`        | `away_team`                                         |
| `home_score`       | `home_score`                                        |
| `away_score`       | `away_score`                                        |
| `home_margin`      | `result` (== home_score − away_score)              |
| `home_win`         | sign of `home_margin`; **null on tie** (margin==0) |
| `closing_spread`   | `spread_line`                                       |
| `home_rest_days`   | `home_rest` (→ `Int64`)                            |
| `away_rest_days`   | `away_rest` (→ `Int64`)                            |
| `venue`            | `stadium` (readable name)                           |
| `neutral_site`     | `location == "Neutral"`                            |

**Dtype coercion (the schema is strict):** `import_schedules` returns scores as
`float64` (NaN for unplayed games). After dropping unplayed games, cast
`home_score`/`away_score`/`home_margin`/`attendance`/`capacity`/`season` to plain
`int`; `home_rest_days`/`away_rest_days` to `Int64`; `home_win` to `boolean`;
`date` to datetime. The plain-`int` vs `Int64` vs `float` distinction is enforced
by `validate()`, so coercion is not optional.

Derived:

- **`attendance`** — from the ESPN dict, keyed on `espn` id. Real `0` for 2020
  empty stadiums (distinct from `None` = missing → dropped).
- **`capacity`** — from the `stadium_id → capacity` lookup.
- **`crowd_pct`** — `attendance / capacity`. Capacity is the full-house number even
  in 2020 (the COVID cap is in attendance, not capacity), so empty games →
  `crowd_pct == 0` (real zero, not null).
- **`covid_era`** — `season in treated_seasons` (from config). Keyed on the season
  int, so Jan/Feb playoff games tag correctly for free.
- **`is_dome`** — `roof in {"dome", "closed"}` (retractable-closed = effectively
  indoor).
- **`temp_f` / `wind_mph`** — from `temp` / `wind`, but **nulled unconditionally
  when `is_dome`** (nfl_data_py sometimes puts junk temps on dome games; the
  validator enforces dome ⇒ weather null). Present for `roof in {outdoors, open}`.
- **`precip`** — not in the schedule → always null.
- **`home_elo` / `away_elo`** — literal `1500.0` (Phase 4 overwrites).
- **`away_travel_km`** — null (Phase 4 fills).
- **`relocated_home` / `is_bubble`** — all `False` (NFL has neither in this window).

## Capacity lookup

`config/nfl_venue_capacity.yaml` — `stadium_id → nominal full capacity`.

- **Keyed on `stadium_id`, not stadium name** — `stadium_id` is stable; names drift
  with sponsors.
- **One capacity per stadium**, the full-house football number. `ponytail:` comment
  notes this ignores year-to-year expansions/reconfigurations; upgrade to
  per-(stadium, season) only if it ever matters.
- Built by generating the unique `(stadium_id, stadium)` set from the loaded
  schedule, then hand-filling real capacities. Any `stadium_id` present in the
  schedule but absent from the lookup is a **hard error** (fail loudly, don't
  silently null `crowd_pct`).

## Missing-attendance policy

- **Unplayed game** (null result/score) → dropped in `load` before fetching.
- **Played game, ESPN `attendance` is `None`** (field absent, distinct from real
  `0`) → **dropped + logged** (a game with no treatment value is useless to the
  model).
- **Circuit breaker:** if > 5% of a season's played games are missing attendance,
  **hard-fail the whole load** — that signals ESPN coverage broke, not a stray
  game. The run summary reports counts and the dropped game ids.

## Smoke test (de-risk the full pull)

`main --smoke` runs the *complete* pipeline (fetch → capacity → `_build_panel` →
`validate`) on a tiny slice — **2020, weeks 1–2 (~30 games)** — prints the panel
for inspection, and stops. 2020 is chosen deliberately: most schema-stressing
season (empty stadiums, staggered caps, domes).

The slice has **known-good anchors from the pre-Phase-1 spike** — 2020 attendance
samples `15,895 / 10,166 / 0 / 0`. The smoke test **asserts against those actual
values**, proving the `espn`-id → attendance join is correct (not merely that some
number returned), that capacity resolves, and that `crowd_pct` is sane (real `0`
for empties). Only after `--smoke` passes do we run the full 2018–2023 range
(~1,600 games, ~30–60 min, cached once).

## Config change

Add under `nfl:` in `config/sports.yaml`:

```yaml
nfl:
  treated_seasons: [2020]
  load_seasons: [2018, 2023]   # [start, end] inclusive
```

## Output

`data/interim/nfl.parquet` — the validated 29-column panel, ~1,600 rows.

## Testing

`tests/test_nfl_loader.py`, **no network** — all against `_build_panel` with a
hand-built fake schedule + attendance/capacity dicts:

1. Panel passes `validate()`.
2. 2020 empty game (`attendance=0`) → `crowd_pct == 0` (real zero, not null).
3. Tie (`home_margin==0`) → `home_win` is null.
4. Dome game (`roof="dome"`, junk temp in input) → `temp_f`/`wind_mph`/`precip`
   all null.
5. `home_margin`/`home_win` sign consistency for a decided game.

Plus one IO test: `_fetch_attendance` reads an existing cache file and does **not**
hit the network.

## Non-goals (deferred)

- Elo, travel distance (Phase 4).
- MLB/NBA loaders + any shared ESPN helper extraction (Phase 3).
- Deeper descriptive baseline seasons — widen `load_seasons` if Phase 5 wants it.

---

## Addendum (2026-07-02): Option A — empirical capacity (SUPERSEDES the static "Capacity lookup" section)

**Finding:** ESPN `gameInfo.attendance` is *announced* attendance (tickets distributed),
which for most NFL stadiums exceeds official *seated* capacity — a units mismatch, not a
data error. A full audit of all 1,657 games (2018–2023) found ~60% of normal-season games
above hand-entered seated capacities (Dallas announces ~93k in an 80k-seat stadium, +17%;
100+ games would breach `crowd_pct ≤ 1.05`). No public source gives real turnstile
attendance — announced is the universal standard across ESPN / PFR / nflverse.

**Decision (user-approved):** define the crowd dose against an **empirical full-house
reference** drawn from the same announced-attendance series, so numerator and denominator
share units and the ratio is a clean "fraction of a normal full house."

**`_derive_capacity(schedule_with_attendance) -> dict[(stadium_id, season), int]`:**
- Reference for a `(stadium_id, season)` = the **max announced attendance** that stadium
  drew that season (its self-calibrating full house — sticky announced sellouts make this
  stable, e.g. Cleveland's 67,431 every game).
- A season is **COVID-suppressed** if its max < 0.5 × that stadium's all-time max
  (this flags ~2020 for every team). Suppressed seasons **borrow** the stadium's max over
  its non-suppressed seasons — a near-empty season's own max is not a full house. (Exact
  borrowed value barely matters: suppressed-season attendance ≈ 0, so `crowd_pct ≈ 0`
  regardless.)
- Per-season self-reference **auto-handles genuine capacity changes** (FedEx ~82k→~67k;
  each season scales to its own full house) and relocations (different `stadium_id`s).

**Consequences:**
- `crowd_pct ≤ 1.0` within every normal season by construction (the fullest game = 1.0),
  so the schema's `crowd_pct ≤ 1.05` ceiling is kept unchanged.
- `capacity` in the panel is this per-(stadium, season) reference (announced full house),
  not a seated-capacity constant. Its schema slot (`int, min=1`) is unchanged.
- **Removed:** `config/nfl_venue_capacity.yaml` and `_load_capacity`. Capacity is derived
  in `load()` from the fetched attendance and passed to `_build_panel`.
- `_build_panel`'s `capacity` argument is now keyed by `(stadium_id, season)` tuples, not
  by `stadium_id`.

**Bug found during the audit (folded into `load`):** the schedule's `espn` column is
`float64` (holds NaNs), so `str(espn)` yields `"401030693.0"` and 400s the ESPN URL. `load`
must drop null `espn`, then `.astype("int64").astype(str)` before fetching/joining.

**Smoke test note:** capacity derivation needs full normal-season context, so smoke now runs
the full (cache-warm → fast) load and asserts on the **2020 subset** (`crowd_pct == 0`
present; 2020 max `crowd_pct` < 0.6, reflecting caps) rather than a 2-week slice.
