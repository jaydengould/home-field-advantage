# Data pipeline

Where the data comes from, why, and the traps in it. Read before touching `src/data/`
or `src/features/`.

## All four sports single-source on ESPN

Two public endpoints, keyed by ESPN event id — **no cross-source join**:

- **scoreboard** `.../sports/{path}/scoreboard?dates=YYYYMMDD` → the day's events
  (event id, teams, scores, venue, `neutralSite`, status).
- **summary** `.../sports/{path}/summary?event=<id>` → `gameInfo.attendance`.

`src/data/_espn.py` is the shared layer: `fetch_summary`, `walk_scoreboard`,
`derive_capacity`, `check_coverage`, over a `_cached_get(cache, url, throttle)`.

**Native packages were all rejected** (each was spiked before building):

| Source | Why rejected |
|---|---|
| `nfl_data_py` | Zero attendance in any `import_*` function. |
| `pybaseball` | Has `Attendance`, but baseball-reference marks 2020 empty games "Unknown" → **NaN, not 0** — nulls exactly the treatment games. |
| `nba_api` | `GameInfo.ATTENDANCE = None` even for normal games. |
| Pro-Football-Reference | Hard 403s every automated request. |

NFL is the one exception to scoreboard-sourcing: it still uses `nfl_data_py.import_schedules`
for the schedule (which also hands us `spread_line`, `home_rest`/`away_rest`, `temp`/`wind`,
`roof`, `location`, `referee`, `result` for free) and joins attendance via the schedule's
`espn` id column.

**⚠️ The `espn` column is `float64`** — you must `dropna()` then
`.astype("int64").astype(str)`, or the `.0` suffix 400s the ESPN URL.

## Capacity = empirical full house ("Option A")

ESPN attendance is *announced* (tickets distributed) and routinely exceeds seated capacity
(~60% of NFL games; Dallas ~93k in an 80k stadium). ESPN's own `venue.capacity` is always
`None`. So there is a units mismatch and no public turnstile source.

`capacity[venue, season]` = that venue-season's **max announced attendance**, self-calibrating.
Treated seasons **borrow** the venue's non-treated max, and take
`max(borrowed, own season max)` — suppression is decided from `treated_seasons`, never from a
magnitude threshold (a magnitude guess misfires on the MLB/NBA 2021 partial reopenings).

- The `max()` half was added during the NBA build: the 2021 Rays ALDS Game 1 was a reopened
  full house (37,616) exceeding Tropicana's tarped non-treated max (32,251) → `crowd_pct`
  1.166 tripped the validator's 1.05 ceiling. `max()` keeps the anti-inflation intent while
  not under-anchoring a real full house.
- **⚠️ Option A is only correct if every venue has a non-treated season in the load window.**
  Globe Life Field opened in 2020 (a treated year) and is anchored only by 2022/23 — a narrow
  window omitting those makes its `crowd_pct` spuriously ~1.0. The configured `[2018, 2023]`
  window satisfies the requirement; smoke tests must not.
- **⚠️ `crowd_pct == 0` is a REAL value inside a restriction window** (empty stadium), not missing.
  Never coerce those to null. ESPN zeros *outside* `zero_attendance_windows` are reporting
  artifacts: `build.py` nulls their `crowd_pct` in `data/processed` (see Known imperfections).

## Per-sport edge cases

**NFL** — `roof` → `is_dome`; `location` → `neutral_site`; `spread_line` = `closing_spread`
(NFL only). `is_playoff = game_type != "REG"` assumes no preseason rows.

**MLB** — no weather (deliberate: weather ⊥ COVID caps, symmetric on margin, and the
demand→attendance channel is mediation not confounding). `is_dome` True only for Tropicana
(venue id `"31"`); retractables → False, an inert approximation since weather is null.
`closing_spread` null — baseball is a moneyline sport. `relocated_home` hardcoded `(TOR, 2020)`
(Buffalo). ESPN's `neutralSite` **did** correctly flag the 2020 postseason bubble.

**NBA** — always indoor (`is_dome=True`, weather null). Seasons span two calendar years, so the
scoreboard walk is **continuous** over `[date(min-1, 9, 1), date(max, 11, 30)]` filtered by ESPN
`season_year`. `is_bubble = (venue_id == "4066") & (season == 2020)` — venue+season, **not**
ESPN's neutral flag, which is False for the bubble. `relocated_home` hardcoded `(TOR, 2021)`
(Tampa). `treated_seasons: [2021]`, not `[2020, 2021]`: once the bubble is excluded, 2020's
remaining games are all full-crowd pre-March-2020, and this keeps `derive_capacity`
self-anchoring on 2020's own full houses.

**NHL** — four deltas from the NBA pattern:
1. **32-team whitelist**, not an all-star blacklist (robust to however ESPN types exhibitions).
   `ARI` in, `UTAH` out — ESPN's teams endpoint lists *current* teams and is wrong for 2018–23.
2. **`relocated_home` = modal-venue rule** (`venue_id != value_counts().idxmax()` per
   `(home_team, season)`), which catches Winter Classic / Stadium Series / Heritage Classic /
   Lake Tahoe *and* the Global Series with no hand-maintained list.
3. **`is_bubble` is DATE-based**: `season == 2020 & date >= 2020-08-01`. ⚠️ **Load-bearing.**
   Only 72 of 130 bubble games carry `neutral_site=True`; the exclusion holds today only
   because all 130 are also `is_playoff=True`. Filter on `is_bubble`, never `neutral_site`.
4. **Wider season window**, Sept 1 (y−1) → **Sept 30** (y). Needed twice: season 2020's playoffs
   ran to 28 Sep 2020, and season 2021 ran Jan–Jul 2021. NBA's Nov 30 end truncates both.

OT/shootout games keep ESPN's final score unchanged — corroborated by 538's NHL Elo, which
tested exactly this and found no predictive power in separating one-goal regulation results
from OT/shootout ones.

## Two bugs that got through tests and reviewers

- **All-Star leak.** ESPN types All-Star / Rising-Stars games as `season_type=2`, so they slip a
  `{2,3}` filter with fake abbrevs (MLB `AL`/`NL`; NBA `DUR`/`GIA`/`LEB`/`STE`/`USA`/`WORLD`).
  Fixed with exclusion sets in `mlb.py`/`nba.py`; NHL avoids the class entirely via its whitelist.
- **YAML "Norway problem".** A bare `NO:` key parses as boolean `false`, silently dropping New
  Orleans coords (NFL Saints + NBA Pelicans). Quoted `"NO"`; regression test
  `test_coords_cover_every_panel_team` asserts every panel team has coords.

## Fetching, caching, cost

- Cache is **immutable / write-once** to `data/raw/<sport>/espn/`, so a pull is self-completing
  across cache-warm re-runs. `data/raw/` is never overwritten.
- ESPN **soft-rate-limits sustained bulk fetching** (transient 502s). `_cached_get` retries with
  capped backoff + jitter (6 attempts). `fetch_summary` swallows a persistent failure and
  returns `None` (counted as missing; the >5% `check_coverage` gate guards systemic loss) so one
  unlucky game can't abort a 3000-game pull. `_fetch_scoreboard` stays **fail-loud** — a lost
  date is unaccounted data loss.
- A cold `[2018, 2023]` MLB pull takes **hours** and may need a couple of runs to fully warm.
- Caches are gitignored and local-only (~14GB MLB + ~6GB NBA + ~3GB NHL). A fresh clone
  re-fetches. Don't `git clean -fdx` them away. Deleting them is a deliberate end-of-project
  step, after the parquets are verified.

## Built panels (measured)

| Sport | Games | Dropped | `crowd_pct` in the treated season |
|---|---|---|---|
| nfl | 1657 | 0 | 2020: **.066** (154 empty games) |
| mlb | 13249 | — | 2020 all-empty; 2021 mean **.436** (post zero-fix + dedup; was 13272 with 23 duplicate rows) |
| nba | 7562 | 0 | 2021: **.124** (bubble 171, relocated 36, neutral 19) |
| nhl | 7678 | 0 | 2021: **.100** (952 games, 571 completely empty) |

Non-treated seasons run ~.93–.98 for nfl/nba/nhl. **MLB is the outlier: a normal MLB season
averages only .63–.67 under Option A**, and only 17% of its games exceed 0.9.

## Known data imperfections, documented and NOT fixed

- **ESPN zero-attendance reporting artifacts — FIXED 2026-09-15, residual disclosed.** ESPN's
  summary returns `attendance == 0` for some games played with fans: MLB 2018 16 · 2019 13 ·
  2021 32 · 2022 27 · 2023 15 (96 of 103 have another same-home-team game within 12 h; `date` is UTC), NBA 2019 1 · 2022 3 · 2023 4,
  NHL 2023 7, NFL 2023 1. Real zeros (NFL 2020, MLB 2020, NBA/NHL 2021, the bubbles, and Canadian
  home games 2021-12-16…2022-02-20) are kept. `null_reporting_zeros` nulls `crowd_pct` outside
  `zero_attendance_windows`; interim keeps the raw 0. **Residual:** inside the treated seasons, zeros that fall after
  that team's first game with fans that season number 17 NFL / 42 NBA / 3 NHL on regular-season
  games (44 NBA including playoffs), and **37** on the dose-response model sample
  (17 NFL / 17 NBA / 3 NHL — the NBA gap is mostly TOR-in-Tampa, excluded as relocated). The NFL ones look like real Dec-2020
  re-closures; isolated NBA ones (CLE, UTAH, …) are likely artifacts. Left at 0 by rule.
- **Duplicate MLB games — FIXED 2026-09-15.** ESPN re-lists a suspended game (final, unchanged)
  on the day it resumed, and listed ARI–PIT 2018-06-13 under two ids. `walk_scoreboard` yielded
  them twice: 23 extra MLB rows (22 repeated ids + 1 twin) that double-updated Elo and gave the copy
  rest 0. `walk_scoreboard` now yields each id and each (start, teams, score) once, and
  `validate()` rejects duplicate `game_id`. The MLB loader was re-run from cache (network blocked):
  13,249 rows, identical to the old interim minus the duplicates.
- **NHL Islanders dual-arena era** (Barclays/Nassau, seasons 2019–21) — 39 games flagged
  `relocated_home`, a false positive against the flag's intent. Left in: 0.5% of games,
  exclusion is conservative, and a split-arena season plausibly does dilute home familiarity.
- **Three NHL outdoor games have ESPN `venue == "None"`** and collapse into one fake venue.
  All three are `neutral_site=True` and excluded, so no estimate is affected.
- **NHL season 2022 is not a clean control (Omicron).** Canadian teams Dec–Feb averaged
  `crowd_pct` .519 with 26 near-empty games. Config deliberately leaves 2022 untreated: the
  continuous dose is *correct* for those games, only the coarse `covid_era` label is imprecise,
  and only the 6b DiD is attenuated (~1–2% of control mass, biased toward zero = conservative).
  Marking all of 2022 treated would be worse — it would break self-anchored capacity.
- **`stadium_id.astype(str)`** maps null → `"nan"`; `walk_scoreboard` `str(None)` → `"None"`.
