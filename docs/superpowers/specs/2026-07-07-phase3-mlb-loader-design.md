# Phase 3 — MLB loader design (2026-07-07)

MLB is the second sport to conform to the unified panel contract. It reuses the
NFL pattern (ESPN attendance → Option A empirical capacity → validated 29-col
panel) but is **single-source on ESPN**: unlike NFL, both the schedule/scores and
the attendance come from ESPN, so there is no cross-source join. This spec covers
the MLB loader **and** the extraction of the shared `src/data/_espn.py` helper that
MLB (now) and NBA (next) both depend on.

Prereq: the Phase 3 attendance spike (CLAUDE.md, run 2026-07-07) already verified
every ESPN field this design relies on against live endpoints.

## Goal

Emit the validated 29-column panel for MLB seasons **2018–2023** to
`data/interim/mlb.parquet`, one row per game, identical schema to `nfl.parquet`.
The panel must carry the COVID crowd-dose signal (`crowd_pct` ≈ 0 for 2020 empty
stadiums, partial for 2021) that the causal engine identifies off.

## Why single-source ESPN (spike result)

- `pybaseball.schedule_and_record` **has** an `Attendance` column but marks 2020
  empty-stadium games "Unknown" → `NaN`, not `0`. That nulls exactly the treatment
  games and destroys the dose signal. Rejected.
- `nba_api` pattern (native package lacks usable attendance) repeats.
- ESPN `.../baseball/mlb/summary?event=<id>` returns `gameInfo.attendance` with a
  **real `0`** for empty games. ESPN `.../baseball/mlb/scoreboard?dates=YYYYMMDD`
  returns the full day's game list (event id, teams+abbrev, scores, venue id+name,
  `neutralSite`, `season.type`). So schedule + scores + attendance all come from
  ESPN, keyed by ESPN event id — no date+team join needed.

## Architecture

Two new files; one trivial edit to the existing NFL loader.

### `src/data/_espn.py` (new — shared, sport-agnostic)

The "2nd/3rd consumer arrived" extraction. Holds only what is genuinely shared:

- `fetch_summary(sport_path, event_id) -> int | None` — cached ESPN summary fetch
  → `data/raw/<sport>/espn/<event_id>.json` (immutable, write-once, polite
  throttle). Takes an **already-clean string id**. Returns `gameInfo.attendance`
  or `None`. `sport_path` is e.g. `"baseball/mlb"`.
- `walk_scoreboard(sport_path, start_date, end_date) -> Iterator[dict]` — iterate
  calendar dates, GET `.../{sport_path}/scoreboard?dates=YYYYMMDD` (cached per
  date), yield one dict per event:
  `{event_id, date, season_year, season_type, home_abbr, away_abbr, home_score,
  away_score, venue_id, venue_name, neutral_site, status}`. Skips events lacking a
  `competitions` block (postponed/placeholder rows). It yields **all** event types
  as-is (regular/postseason/preseason/all-star); the sport loader is responsible
  for filtering by `season_type` (see mlb.py). The caller passes per-season date
  bounds; MLB uses a generous `{year}-03-01 .. {year}-11-30` window per season
  (covers late-March openers through the early-November World Series).
- `derive_capacity(df, treated_seasons) -> dict` — **moved verbatim from `nfl.py`**.
  Option A empirical full-house per `(venue_key, season)`: a normal season
  self-references its own max announced attendance; a treated season borrows the
  venue's max over its non-treated seasons. Keyed off `treated_seasons`, not a
  magnitude threshold. **Guarantee:** capped treated-year attendance (empty 2020
  regular games, the ~11k 2020 postseason bubble, partial 2021) is **never** used
  as a capacity — capacity is drawn only from non-treated seasons, so `crowd_pct`
  for a capped game is (capped attendance / true full house) and the treatment
  stays visible. Verified no MLB venue in-window appears *only* in treated seasons,
  so the "own-max" fallback never fires on a capped venue.
- `check_coverage(miss, total) -> None` — **moved verbatim from `nfl.py`**.
  Hard-fail if any season lost >5% of played games to missing attendance.

Rationale for moving `derive_capacity`/`check_coverage`: they are sport-blind, and
making them the single implementation guarantees all three sports compute
`crowd_pct` the **same way** (a structural guarantee, not a hope). They are not
ESPN-specific, but `_espn.py` is the one shared data-loader module Phase 3 needs;
a second shared module would be YAGNI.

### `src/data/nfl.py` (edited — minimal)

Swap NFL's local `_derive_capacity`/`_check_coverage` for imports from `_espn.py`.
NFL keeps its own `nfl_data_py` schedule path and its float-`espn`-id cleaning at
the call site (that stays NFL-specific). No behavior change; the 28 existing tests
are the regression guard and must stay green.

### `src/data/mlb.py` (new — thin sport glue)

Pipeline: `walk_scoreboard("baseball/mlb", ...)` over the season date ranges →
**filter to `season_type in {2, 3}`** (regular + postseason only; drops spring
training `type=1` and the all-star game `type=4`, which the generous date window
would otherwise sweep in) → `fetch_summary` per event for attendance →
`_build_panel` (pure transform) → `derive_capacity` → `validate()` →
`data/interim/mlb.parquet`.

`_build_panel(events, attendance, capacity, treated_seasons) -> DataFrame` is a
pure transform (no net/disk), mirroring NFL's. It assumes the preseason/all-star
filter already ran (it does not re-filter).

## Column mapping (29-col panel)

| Column | Source / rule |
|---|---|
| `sport` | `"mlb"` |
| `game_id` | `"mlb_" + event_id` (unique incl. doubleheaders; sport-prefixed so the pooled panel can't collide across sports) |
| `season` | ESPN `season_year` |
| `date` | event date |
| `is_playoff` | `season_type == 3` (2 = regular, 3 = postseason — verified; preseason/all-star already filtered out) |
| `home_team`, `away_team` | ESPN team abbreviations |
| `home_score`, `away_score` | event scores |
| `home_margin` | `home_score - away_score` |
| `home_win` | sign of margin; null on ties (MLB has no ties in practice, but the rule holds) |
| `attendance` | `fetch_summary` → `gameInfo.attendance` (real `0` for empties) |
| `capacity` | Option A `derive_capacity`, keyed `(venue_id, season)` |
| `crowd_pct` | `attendance / capacity` ∈ [0, ~1] |
| `covid_era` | `season in treated_seasons` ({2020, 2021}) |
| `home_elo`, `away_elo` | `1500.0` placeholder (Phase 4 overwrites) |
| `closing_spread` | **null** — baseball is a moneyline sport with no meaningful point spread; quality is controlled via Elo (see Deferred) |
| `home_rest_days`, `away_rest_days` | **null** (Phase 4 computes from schedule) |
| `away_travel_km` | **null** (Phase 4) |
| `venue` | ESPN venue name (`venue_id` used only as the capacity key) |
| `is_dome` | `True` only for permanent domes (Tropicana Field); else `False`. Retractables → `False` (documented venue-level approximation; per-game roof state not in ESPN and analytically inert since MLB weather is null) |
| `temp_f`, `wind_mph`, `precip` | **null** — no weather captured for MLB (see Rationale) |
| `neutral_site` | ESPN `neutralSite` flag, OR-ed with the hardcoded exceptions (see below) |
| `relocated_home` | `True` for `(TOR, 2020)`; else `False` |
| `is_bubble` | `False` (NBA-only concept) |

## Config (`config/sports.yaml`)

```yaml
mlb:
  load_seasons: [2018, 2023]
  treated_seasons: [2020, 2021]
```

- 2018–2019: full-crowd pre-period baseline + Elo burn-in.
- 2020: empty stadiums (60-game season, the pure extreme).
- 2021: staggered reopening — the within-season partial-dose richness.
- 2022–2023: post-COVID reversion anchors.
- Window matches NFL for a clean cross-sport comparison. MLB seasons are
  single-calendar-year, so `treated_seasons` labeling is trivial (NBA's two-year
  span is a later problem).

## Edge cases

- **Relocated home (the one that matters): 2020 Toronto Blue Jays** played all home
  games at Sahlen Field, Buffalo (border closure) — a full season of compromised
  home-field *inside the treatment window*. Hardcoded exceptions table flags
  `(TOR, 2020) → relocated_home=True` so the main model excludes them. Without this
  they would masquerade as ordinary low-crowd 2020 home games.
- **Neutral special events** (London 2019, Field of Dreams 2021–22, Little League
  Classic annual, Mexico City 2023, ~10 games over six years) are **not
  enumerated** (option 4a): whatever ESPN's `neutralSite` flag catches for free is
  kept, and anything it misses is a **documented minor limitation**. Impact on the
  estimate is negligible (~10 of ~14,000 rows), and a generic venue-mismatch
  detector can't distinguish a temporary relocation from a permanent move (e.g. the
  Rangers' new 2020 park) without external knowledge — over-engineering for a fixed
  window.
- **Preseason / all-star**: the generous date window sweeps in spring-training
  (`season_type=1`) and all-star (`season_type=4`) games. The loader filters to
  `season_type in {2, 3}` before building the panel, so neither enters. (NFL's
  latent "assumes no preseason rows" caveat is thus handled explicitly here.)
- **2020 postseason neutral bubble**: MLB's 2020 Division Series onward were played
  at neutral bubble sites (Globe Life, Petco, Dodger Stadium, Minute Maid) with
  capped ~11k crowds. These `is_playoff=True` games stay in the panel; `neutral_site`
  is taken from ESPN's flag if set. ESPN's neutral flag proved **unreliable for
  pandemic bubbles** (verified `False` for the NBA bubble), so some may not be
  flagged — accepted as a **documented limitation**, not a second bubble detector.
  Impact on the core estimate is nil: it's ~30 *postseason* games, and the primary
  HFA model is regular-season (playoffs are a robustness layer). Capacity is
  unaffected — 2020 is a treated season, so it *borrows* a non-treated full house
  (2018–19 / 2022–23) rather than setting one; the new-in-2020 Globe Life Field has
  non-treated 2022–23 seasons in-window, so it too borrows a true full house.
- **Doubleheaders**: same date/teams/venue, but ESPN assigns each game a distinct
  event id → `game_id` stays unique. Verified.
- **Coverage gate**: reuse `check_coverage` — hard-fail if any season loses >5% of
  its played games to missing attendance (signals ESPN coverage broke, not a stray
  game).

## Rationale: no weather for MLB

Weather is **not needed** and no parser is built. Reasons, in order:

1. **Not a confounder of the crowd estimate.** The treatment is policy-driven
   capacity caps (COVID closures), which are orthogonal to weather. An omitted
   variable only biases the `crowd_pct` coefficient if it correlates with the
   treatment; weather does not.
2. **Outcome is margin.** Weather is a near-symmetric shock to both teams, so it
   moves total runs, not the home−away gap. Its direct effect on margin is
   second-order.
3. **Mediation, not confounding.** The part of weather that flows *through*
   attendance (cold → fewer fans → weaker HFA) is the crowd effect we are
   measuring; controlling for it would be over-control.
4. ESPN MLB weather is inconsistent to parse; NFL got weather free, MLB does not.

Weather columns stay in the schema (nullable; NFL populates them). If Phase 6a ever
leans on normal-season demand variation, revisit — but even then weather is minor.

## Testing (mirror NFL's 28-test bar)

Pure-transform tests on `_build_panel` (no net/disk):
- Emits a schema-valid panel (`validate()` passes).
- `home_margin` / `home_win` logic (incl. tie → null `home_win`).
- `is_dome` True only for permanent domes.
- `(TOR, 2020)` → `relocated_home=True`; others False.
- `game_id` uniqueness across a synthetic doubleheader.
- `season_type` filter: `type in {1, 4}` events dropped, only `{2, 3}` retained;
  `is_playoff` True iff `type == 3`.
- Capacity Option A incl. treated-season borrow (via the shared helper).

`_espn.py` unit tests:
- `derive_capacity` treated-season borrow + `max(cap, 1)` floor.
- `check_coverage` passes ≤5%, raises >5%.
- `walk_scoreboard` maps a canned scoreboard JSON → expected event dicts; skips a
  no-`competitions` placeholder event.

Integration / smoke (real 2020 data, one assertion block):
- Empties exist (`crowd_pct == 0`) — 2020 regular season was 100% no-fans — and
  nothing full (`crowd_pct.max() < ~0.6`; the only 2020 crowds are the capped ~11k
  postseason bubble, ≈0.3). `attendance ≤ capacity` everywhere. A broken join would
  show ~1.0 or NaN instead.

Regression:
- The full **NFL** suite stays green after the import swap — the guard on the
  refactor.

## Deferred / carried forward

- **MLB team-quality control = Elo** (Phase 4, sport-blind, consumed in Phase 6a).
  Betting lines are a deferred *optional* enhancement: NFL gets a point spread free,
  but baseball is a moneyline sport, so the honest MLB version is
  moneyline→win-probability as its **own** feature — not the `closing_spread`
  column. Not built here.
- `home_elo`/`away_elo` = 1500.0, rest/travel = null — all Phase 4 placeholders,
  identical to NFL. The interim panel still passes the full `validate()`.
- Data files stay gitignored (local ESPN cache only), per the repo's
  never-commit-downloaded-data principle. A fresh clone re-fetches from ESPN.
- NBA (next) reuses `_espn.py` unchanged; its extra concerns (2020 Orlando bubble
  `is_bubble`, two-calendar-year season labeling, all-indoor `is_dome=True`) are
  out of scope here and handled in the NBA spec.

## Out of scope (explicitly not built)

Weather parser; neutral-event enumeration; per-game retractable-roof state; MLB
betting lines; any NFL logic change beyond the two-function import swap; Elo, rest,
travel computation (all Phase 4).
