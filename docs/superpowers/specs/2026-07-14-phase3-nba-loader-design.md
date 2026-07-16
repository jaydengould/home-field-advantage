# Phase 3 — NBA loader design (2026-07-14)

NBA is the third and final sport to conform to the unified panel contract. It
reuses the shared `src/data/_espn.py` layer **unchanged** (built in the MLB phase)
and mirrors `src/data/mlb.py` structurally. This spec covers only what is genuinely
NBA-specific; everything else is a conforming copy of the MLB loader.

Prereq: the Phase 3 attendance spike (CLAUDE.md, run 2026-07-07) verified ESPN
`basketball/nba` carries `gameInfo.attendance` (real `0` for the bubble). A
follow-up recon (2026-07-14) pinned the NBA-specific facts this spec depends on
against live endpoints — see "Recon findings" below.

## Goal

Emit the validated 29-column panel for NBA seasons **2018–2023** to
`data/interim/nba.parquet`, one row per game, identical schema to `nfl.parquet` /
`mlb.parquet`. The panel must carry the COVID crowd-dose signal — `crowd_pct ≈ 0`
for the 2020-21 empty arenas ramping to partial reopening — that the causal engine
identifies off, and must flag the 2020 Orlando bubble so downstream excludes it
from the pooled model while Phase 7 can mine it.

## Recon findings (2026-07-14, live ESPN)

- **ESPN labels NBA seasons by END year.** 2019-20 opening night (2019-10-22) →
  `season_year=2020`; the Aug-2020 bubble → `season_year=2020`; 2020-21 mid-season
  (2021-01-15) → `season_year=2021`. So a single ESPN "season" spans two calendar
  years, and the 2020 bubble tail lands in Aug–Oct **2020**.
- **Bubble venue** = `venue_id="4066"` ("ESPN Wide World of Sports Complex"),
  `neutralSite=False` (ESPN's neutral flag does NOT catch the bubble — confirmed).
  Bubble seeding games are `season_type=2` (regular), bubble playoffs `season_type=3`.
- **TOR 2020-21 relocation**: the Raptors played "home" games at `venue_id="1396"`
  (Tampa, "Benchmark International Arena") with `neutralSite=False` — an NBA
  analogue to MLB's 2020 TOR→Buffalo relocation.
- `STATUS_POSTPONED` games appear (COVID postponements). The existing
  `_select_games` FINAL + non-null-score filter drops them.

## Architecture

One new file; **no** edits to `_espn.py`, `nfl.py`, or `mlb.py`.

### `src/data/nba.py` (new — thin sport glue)

Mirrors `mlb.py`: `_select_games` (reused pattern: `season_type in {2,3}`, status
FINAL, non-null scores) → `_build_panel` (pure transform → validated 29-col panel)
→ `load` / `main` / `--smoke` CLI. Reuses from `_espn.py` verbatim:
`walk_scoreboard("nba", ...)`, `fetch_summary("nba", ...)`, `derive_capacity`,
`check_coverage`. Placeholders identical to NFL/MLB: `home_elo/away_elo=1500.0`,
rest/travel null (Phase 4).

## NBA-specific differences (the only non-copy parts)

### 1. Continuous scoreboard walk (not MLB's per-year window loop)

NBA seasons span two calendar years, ESPN labels by end-year, and the 2020 summer
bubble pushes `season_year=2020` games into Aug–Oct 2020. A per-year date window
(MLB's approach) would overlap between adjacent seasons and misfence the bubble.

Instead, `load(seasons, treated_seasons)` does **one continuous** `walk_scoreboard`
over `[date(min(seasons)-1, 9, 1), date(max(seasons), 11, 30)]`, then keeps games
whose ESPN `season_year ∈ set(seasons)`. Each event lands on exactly one calendar
date, so the walk yields each event once — **no dedup needed**. The Sept-1 start of
the prior year captures October openers; the Nov-30 end of the final year captures
the Oct bubble tail and normal-season starts. (Preseason games the window sweeps in
are dropped by the `season_type` filter.)

### 2. `is_bubble` — venue + season, NOT ESPN's neutral flag

`is_bubble = (venue_id == "4066") & (season == 2020)`. Venue 4066 appears only in
the bubble, so this is airtight; the `season == 2020` conjunct is defensive
self-documentation. Bubble games **stay in the panel** (Phase 7 mines them) with
`is_bubble=True`; downstream excludes them from the pooled model. Orthogonal to
`is_playoff` — both bubble seeding (`type=2`) and bubble playoff (`type=3`) games
are flagged.

### 3. `relocated_home = (TOR, 2021)` — hardcoded, like MLB's `(TOR, 2020)`

TOR's 2020-21 (`season_year=2021`) home games were in Tampa (`venue_id="1396"`),
`neutralSite=False`, so ESPN's flag misses it — detect by the hardcoded
`(home_team, season)` exception exactly as MLB does. Flagged so the main model
excludes them.

### 4. All-indoor: `is_dome=True` everywhere, weather null

Every NBA game is indoors → `is_dome=True` for all rows; `temp_f/wind_mph/precip`
null (matches the null-weather template; the weather-null rationale from the MLB
spec applies identically). No permanent-dome venue lookup needed — it's unconditional.

## Column mapping (29-col panel) — deltas from MLB only

Identical to the MLB mapping except:

| Column | NBA rule |
|---|---|
| `sport` | `"nba"` |
| `game_id` | `"nba_" + event_id` |
| `covid_era` | `season in treated_seasons` (**{2021}** — see below) |
| `is_dome` | `True` unconditionally (all-indoor) |
| `is_bubble` | `(venue_id == "4066") & (season == 2020)` |
| `relocated_home` | `True` for `(TOR, 2021)`; else `False` |
| `closing_spread` | **null** — NBA has point spreads, but ESPN's scoreboard carries no odds; quality is controlled via Elo (Phase 4). A betting source is a deferred optional feature, same stance as MLB. |

All other columns map exactly as in `mlb.py` (`season` ← `season_year`, scores,
margin, win, attendance/capacity/`crowd_pct` via `derive_capacity`, Elo/rest/travel
placeholders, `neutral_site` ← ESPN flag).

## Config (`config/sports.yaml`)

```yaml
nba:
  load_seasons: [2018, 2023]
  treated_seasons: [2021]        # was [2020, 2021] — see rationale
```

**Why `treated_seasons: [2021]`, not `[2020, 2021]` (methodological call).** Once
the bubble is excluded via `is_bubble`, NBA `season_year=2020`'s remaining games are
all Oct 2019 → Mar 11 2020 — full-crowd, pre-pandemic, normal-demand games. The
2019-20 season was suspended, then resumed *only* in the zero-fan bubble (excluded).
So season 2020 contributes **zero** policy-restricted non-bubble crowd variation;
the clean exogenous empty→partial-reopening signal lives **entirely** in season 2021
(2020-21). Marking 2020 as `covid_era=True` would mislabel full-house pre-COVID
games as policy-restricted and corrupt any `covid_era`-based DiD (Phase 6b). Leaving
2020 out also makes `derive_capacity` correctly self-reference 2020's own full houses
as the capacity anchor. `[2021]` is right on both the causal-flag and the capacity
math. (2018–2020 still load as full-crowd baseline + Elo burn-in; 2022–2023 are the
post-COVID reversion anchors — same window as NFL/MLB for cross-sport comparison.)

## Edge cases

- **2020 Orlando bubble** — the headline NBA edge case. Flagged `is_bubble=True` via
  venue 4066 (§2), kept in the panel for Phase 7, excluded from the pooled model
  downstream. See the "why exclude the bubble" reasoning in the design doc: crowd,
  travel, and home-arena familiarity all collapse to zero *simultaneously* there, so
  the games are perfectly confounded for the pooled `crowd_pct` estimate but are
  exactly what a Phase-7 crowd-vs-travel decomposition + seeding-games placebo needs.
- **Bubble capacity artifact (inert).** Venue 4066 appears only in treated 2020, so
  `derive_capacity` has no non-treated anchor for it → falls back to its own (zero /
  near-zero) max. Its `crowd_pct` is therefore meaningless — but the games are
  `is_bubble=True` and excluded downstream, so the artifact never touches the
  estimate. Same class of inert artifact as MLB's Globe Life Field; documented, not
  fixed.
- **TOR-in-Tampa capacity artifact (inert).** Venue 1396 also appears only in treated
  2021 → same own-max fallback → spurious `crowd_pct ≈ 1.0`. Those games are
  `relocated_home=True` and excluded downstream, so it's inert too. Documented.
- **Preseason**: the continuous window sweeps in preseason (`season_type=1`);
  `_select_games` drops it (only `{2,3}` retained). No NBA all-star game reaches the
  panel for the same reason (`season_type=4`).
- **Postponed games**: `STATUS_POSTPONED` (and any non-FINAL) rows dropped by the
  status filter; a postponed-then-replayed game gets a fresh ESPN event id, so the
  replay is counted once and `game_id` stays unique.
- **Coverage gate**: reuse `check_coverage` — hard-fail if any season loses >5% of
  its played games to missing attendance.

## Testing (mirror the MLB bar)

Pure-transform tests on `_build_panel` (no net/disk):
- Emits a schema-valid panel (`validate()` passes).
- `home_margin` / `home_win` logic (NBA has no ties, but the rule holds).
- `is_dome == True` for every row.
- `is_bubble` True iff `(venue_id=="4066") & season==2020`; a non-bubble venue in
  2020 and venue 4066 in a non-2020 hypothetical both → False.
- `(TOR, 2021)` → `relocated_home=True`; other TOR seasons and other teams → False.
- `is_playoff` True iff `season_type==3`, incl. a bubble-playoff row that is BOTH
  `is_bubble` and `is_playoff`.
- `game_id` uniqueness + `nba_` prefix.
- `covid_era` True iff `season in {2021}` (2020 row → False).

Loader-shape test:
- `_select_games` drops `type∈{1,4}`, non-FINAL, and null-score rows; keeps `{2,3}`
  FINAL.
- Season-window bounds: `load`'s continuous range covers a bubble date (Aug 2020)
  and filters to the requested `season_year` set. (Can unit-test the window helper
  and the `season_year ∈ seasons` filter on canned events without hitting the net.)

Integration / smoke (real data, `--smoke` on `[2020, 2021]`, one assertion block):
- **2020 bubble**: games at venue 4066 exist, all `is_bubble=True`, all
  `crowd_pct == 0` (attendance 0). Non-bubble 2020 games (pre-March) show full
  crowds → `crowd_pct` near 1 — i.e. 2020 is NOT uniformly empty (unlike MLB 2020),
  which is the whole reason `treated_seasons` excludes it.
- **2021 (the treatment)**: `crowd_pct` shows the empty→partial ramp — some
  `== 0`, max `< 1.0` (staggered reopening), i.e. the dose signal is present and
  sub-full.
- `attendance ≤ capacity` everywhere except the two documented inert artifacts
  (bubble venue 4066, Tampa venue 1396) — assert on non-relocated, non-bubble rows.

## Deferred / carried forward

- **NBA team-quality control = Elo** (Phase 4, sport-blind). Betting lines (NBA
  *does* have point spreads) are a deferred optional enhancement, not built here and
  not the `closing_spread` column at load time.
- `home_elo`/`away_elo` = 1500.0, rest/travel = null — Phase 4 placeholders,
  identical to NFL/MLB. The interim panel still passes the full `validate()`.
- `data/interim/nba.parquet` full write is a long ESPN pull (~1300 games/season ×6,
  cache-warming, may need re-runs — same as MLB); run `python -m src.data.nba`.
- Data files stay gitignored (local ESPN cache only), per the repo principle.

## Out of scope (explicitly not built)

Any edit to `_espn.py`/`nfl.py`/`mlb.py`; NBA betting lines; a bubble crowd-vs-travel
decomposition (that's Phase 7, consuming `is_bubble`); Elo, rest, travel computation
(all Phase 4); a permanent-dome venue lookup (NBA `is_dome` is unconditional).
