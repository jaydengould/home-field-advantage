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
- Caches are gitignored and local-only (19.0 GiB total: MLB 12G, NBA 3.1G, NHL 3.1G, NFL 798M). A fresh
  clone re-fetches. **Archived 2026-09-22:** compressed to `~/hfa-espn-cache.tar.zst` (726 MiB, 36,855
  files, integrity-tested) and the `data/raw/*/espn` originals deleted. Keep the archive: ESPN's
  endpoints are unofficial, so a re-pull may not reproduce the published tables. Restore from the repo
  root with `zstd -dc ~/hfa-espn-cache.tar.zst | tar -xf -`.

## Built panels (measured)

| Sport | Games | Dropped | `crowd_pct` in the treated season |
|---|---|---|---|
| nfl | 1657 | 0 | 2020: **.067** (147 empty games, 6 null reporting zeros) |
| mlb | 13249 | — | 2020 all-empty; 2021 mean **.444** (post zero-fix + dedup; was 13272 with 23 duplicate rows) |
| nba | 7562 | 0 | 2021: **.133** (bubble 171, relocated 36, neutral 19) |
| nhl | 7678 | 0 | 2021: **.111** (952 games, 482 completely empty, 89 null reporting zeros) |

Non-treated seasons run ~.87–.98 for nfl/nba/nhl (Omicron-hit 2022 is the low end; nba/nhl 2020, .79/.83, include the empty bubbles). **MLB is the outlier: a normal MLB season
averages only .64–.69 under Option A**, and only 17% of its games exceed 0.9.

## Known data imperfections, documented and NOT fixed

- **ESPN zero-attendance reporting artifacts — FIXED 2026-09-15, residual disclosed.** ESPN's
  summary returns `attendance == 0` for some games played with fans: MLB 2018 16 · 2019 13 ·
  2021 32 · 2022 27 · 2023 15 (96 of 103 have another same-home-team game within 12 h; `date` is UTC), NBA 2019 1 · 2022 3 · 2023 4,
  NHL 2023 7, NFL 2023 1. Real zeros (NFL 2020, MLB 2020, NBA/NHL 2021, the bubbles, and Canadian
  home games 2021-12-16…2022-02-20) are kept. `null_reporting_zeros` nulls `crowd_pct` outside
  `zero_attendance_windows`; interim keeps the raw 0.
- **Reopening zeros — FIXED 2026-09-16.** Fix 1 above only nulls zeros *outside* a restriction
  window; inside one, ESPN also reports zero for games played after a team had already readmitted
  fans. Rule (`null_reporting_zeros`, extended): inside a treated season, a zero on or after a home
  team's `fans_from` date — the earlier of its first non-zero home game that season (data) and a
  sourced public-fans date (`config/sports.yaml`) — is also a reporting artifact and gets nulled,
  unless a sourced re-closure (`reclosures`) covers it. Newly nulled: **172 games** — nfl 6 (CLE 1,
  GB 2, PHI 3) · mlb 0 · nba 77 (ATL 2, BOS 4, CLE 5, IND 27, MEM 1, MIA 28, SAC 8, UTAH 2) · nhl 89
  (BUF 14, DET 16, FLA 1, NJ 1, NSH 28, NYI 1, STL 28); 154 dated from a sourced entry, 18 from the
  data alone. 8 sourced re-closures (nfl ARI/BAL/DEN/PHI/PIT/WAS, nba MIN/MEM) null nothing — they
  keep a zero real. Every zero-bearing team in nfl 2020 / nba 2021 / nhl 2021 was audited
  (`.superpowers/sdd/reopening-zeros-fix/team_audit.csv`, workspace-only, not read at build or
  render time); **zero teams were left unverified** (15 of 44 reached a `data_only` verdict off
  the first non-zero ESPN reading alone, 6 of those with no source at all — see below). Full
  per-team audit:

  | sport | team | verdict | fans_from (UTC) | re-closures | source |
  |---|---|---|---|---|---|
  | nba | ATL | data_only | 2021-01-27 | — | — |
  | nba | BOS | data_only | 2021-03-29 | — | — |
  | nba | CLE | data_only | 2020-12-24 | — | — |
  | nba | IND | fans_from | 2021-01-24 | — | https://www.wthr.com/article/sports/nba/indiana-pacers/phase-1-of-bankers-life-fieldhouse-renovations-complete-as-fans-return-slowly/531-21e75caa-1766-4148-8908-46d27087b6b3 |
  | nba | MEM | data_only | 2021-01-17 | 2021-02-18..2021-02-18 | https://www.actionnews5.com/2021/02/18/grizzlies-game-will-play-without-fans-because-weather/ |
  | nba | MIA | fans_from | 2021-01-29 | — | https://wsvn.com/sports/miami-heat-welcome-fans-to-home-games-for-1st-time-since-pandemics-start/ |
  | nba | MIN | data_only | 2021-04-05 | 2021-04-13..2021-04-14 | https://www.espn.com/nba/story/_/id/31248968/sources-minnesota-timberwolves-game-vs-brooklyn-nets-rescheduled-tuesday-afternoon |
  | nba | OKC | no_fans | — | — | https://www.espn.com/nba/story/_/id/30992026/oklahoma-city-thunder-host-fans-2020-21-season-becoming-first-nba-team-go-route |
  | nba | SAC | fans_from | 2021-04-21 | — | https://www.abc10.com/article/sports/nba/sacramento-kings/sacramento-kings-frontline-workers-first-fans/103-74ad2025-18fe-42e1-918e-fecba60a7df1 |
  | nba | UTAH | data_only | 2020-12-27 | — | — |
  | nfl | ARI | data_only | 2020-10-25 | 2020-12-06..2020-12-26 | https://www.revengeofthebirds.com/2020/11/27/21723185/adhs-az-arizona-cardinals-to-not-allow-fans-at-december-6th-home-game-against-los-angeles-rams |
  | nfl | BAL | data_only | 2020-11-01 | 2020-11-22..2020-12-27 | https://www.nfl.com/news/eagles-ravens-revert-to-prohibiting-fan-attendance-as-covid-19-cases-rise |
  | nfl | BUF | no_fans | — | — | https://buffalonews.com/sports/bills/bills-announce-no-fans-at-home-games-for-foreseeable-future/article_2b8c94f6-0287-11eb-8762-cbabf513f6bb.html |
  | nfl | CHI | no_fans | — | — | https://www.si.com/nfl/bears/news/no-fans-allowed-at-bears-home-games-in-soldier-field |
  | nfl | CLE | data_only | 2020-09-17 | — | https://www.pro-football-reference.com/boxscores/202010110cle.htm |
  | nfl | DEN | data_only | 2020-09-27 | 2020-11-29..2021-01-03 | https://gazette.com/sports/broncos/broncos-no-fans-at-final-three-home-games-due-to-covid-19/article_38a125cc-2b53-11eb-b98e-5b80cac93565.html |
  | nfl | DET | no_fans | — | — | https://www.clickondetroit.com/sports/2021/07/12/ford-field-to-host-fans-at-full-capacity-for-detroit-lions-2021-season/ |
  | nfl | GB | fans_from | 2020-12-19 | — | https://wrex.com/2020/12/18/green-bay-packers-invite-frontline-workers-to-game-at-lambeau-field |
  | nfl | LA | no_fans | — | — | https://www.therams.com/news/no-fans-at-sofi-stadium-until-further-notice |
  | nfl | LAC | no_fans | — | — | https://www.chargers.com/news/sofi-stadium-fans-attendance-update |
  | nfl | LV | no_fans | — | — | https://www.reviewjournal.com/sports/raiders/raiders-to-play-2020-season-with-no-fans-2087201/ |
  | nfl | MIN | no_fans | — | — | https://www.startribune.com/minnesota-vikings-eager-fans-return-u-s-bank-stadium-home-opener/600101111 |
  | nfl | NE | no_fans | — | — | https://www.patriots.com/news/statement-from-gillette-stadium |
  | nfl | NYG | no_fans | — | — | https://www.nfl.com/news/giants-jets-metlife-stadium-no-fans-allowed |
  | nfl | NYJ | no_fans | — | — | https://www.nfl.com/news/giants-jets-metlife-stadium-no-fans-allowed |
  | nfl | PHI | fans_from | 2020-10-18 | 2020-11-17..2021-01-03 | https://www.philadelphiaeagles.com/news/eagles-welcome-back-fans-to-lincoln-financial-field-in-a-limited-capacity |
  | nfl | PIT | data_only | 2020-10-11 | 2020-12-02..2020-12-27 | https://steelersnow.com/steelers-no-fans-for-rescheduled-game-vs-ravens-on-sunday/ |
  | nfl | SEA | no_fans | — | — | https://www.seattletimes.com/sports/seahawks/seahawks-announce-they-can-have-full-capacity-crowds-at-lumen-field-this-season/ |
  | nfl | SF | no_fans | — | — | https://www.cbsnews.com/sacramento/news/49ers-2020-opener-levis-stadium-no-fans/ |
  | nfl | WAS | data_only | 2020-11-08 | 2020-11-22..2020-12-27 | https://dcist.com/story/20/10/23/the-washington-football-team-will-allow-fans-to-attend-its-game-against-the-giants/ |
  | nhl | BUF | fans_from | 2021-03-18 | — | https://www.nhl.com/sabres/news/sharpen-up-march-18-2021-sabres-bruins-preview-hockey-fights-cancer-night-don-granato-interim-head-coach/c-322642190 |
  | nhl | CGY | no_fans | — | — | https://www.nhl.com/news/canada-approves-border-exemption-for-nhl-325215356 |
  | nhl | DET | fans_from | 2021-03-10 | — | https://dailyhive.com/vancouver/american-nhl-teams-allowed-fans-games |
  | nhl | EDM | no_fans | — | — | https://www.nhl.com/news/canada-approves-border-exemption-for-nhl-325215356 |
  | nhl | FLA | data_only | 2021-01-18 | — | — |
  | nhl | MTL | no_fans | — | — | https://www.nhl.com/news/canada-approves-border-exemption-for-nhl-325215356 |
  | nhl | NJ | data_only | 2021-03-03 | — | — |
  | nhl | NSH | fans_from | 2021-01-15 | — | https://dailyhive.com/vancouver/american-nhl-teams-allowed-fans-games |
  | nhl | NYI | data_only | 2021-03-12 | — | https://longisland.news12.com/islanders-win-final-regular-season-game-at-nassau-coliseum |
  | nhl | OTT | no_fans | — | — | https://www.nhl.com/news/canada-approves-border-exemption-for-nhl-325215356 |
  | nhl | STL | fans_from | 2021-01-19 | — | https://www.nhl.com/blues/news/blues-to-welcome-frontline-workers-to-first-homestand/c-320141424 |
  | nhl | TOR | no_fans | — | — | https://www.nhl.com/news/canada-approves-border-exemption-for-nhl-325215356 |
  | nhl | VAN | no_fans | — | — | https://www.nhl.com/news/canada-approves-border-exemption-for-nhl-325215356 |
  | nhl | WPG | no_fans | — | — | https://www.nhl.com/news/canada-approves-border-exemption-for-nhl-325215356 |

  `data_only` means the first non-zero ESPN game is the only evidence and no independent source
  was needed (isolated late zero) or found (an all-zero team with no public reporting either way);
  its `fans_from` is not source-verified, only data-verified. **Two residuals remain, disclosed in
  the paper, not fixed:** (1) NHL DET's date is kept at 2021-03-10 despite a conflicting source (a
  season-ticket holder saying his family attended "back in January") that no other source
  corroborates or pins to a game — 12 games are at stake if that conflict resolves the other way;
  (2) a `data_only` `fans_from` date is only as good as ESPN's non-zero count — a wrong non-zero
  reading from a family/staff-only game could set the date too early, and this arm is not
  source-checked the way `fans_from` verdicts are. NSH and STL's `fans_from` dates each rest on a
  handful of invited guests and reclassify all 28 of that team's treated-season home games; no
  post-hoc crowd-size threshold was added to guard against this (a spectator's size is carried by
  the dose, not by a category rule chosen after seeing the estimate).
- **Duplicate MLB games — FIXED 2026-09-15.** ESPN re-lists a suspended game (final, unchanged)
  on the day it resumed, and listed ARI–PIT 2018-06-13 under two ids. `walk_scoreboard` yielded
  them twice: 23 extra MLB rows (22 repeated ids + 1 twin) that double-updated Elo and gave the copy
  rest 0. `walk_scoreboard` now yields each id and each (start, teams, score) once, and
  `validate()` rejects duplicate `game_id`. The MLB loader was re-run from cache (network blocked):
  13,249 rows, identical to the old interim minus the duplicates.
- **NHL Islanders dual-arena era** (Barclays/Nassau, split seasons 2019–20 only) — 49 games flagged
  `relocated_home`: 31 regular-season (2019: 20, 2020: 11), 8 non-bubble playoffs (2019: 2; 2021: 6,
  the Nassau-labeled ones — see below) and 10 bubble games, all but the 31 excluded anyway. A false positive
  against the flag's intent. Left in: 0.4% of regular-season games, exclusion is conservative, and
  a split-arena season plausibly does dilute home familiarity.
- **NHL Islanders 2020–21 venue mislabel.** Every 2020–21 home game was at Nassau Coliseum
  (NHL.com, 2020-09-30), but ESPN labels the 28 regular-season ones "Barclays Center", so they take
  Barclays' empirical capacity (15,795 vs Nassau's 13,971) and dose is recorded at ~0.88 of truth.
  The 6 flagged-relocated 2021 games are the Nassau-labeled playoffs. Disclosed, not fixed (B.S E2,
  2026-09-21): a fix means regenerating every table for a ~0.01 dose error on 28 games.
- **Three NHL outdoor games have ESPN `venue == "None"`** and collapse into one fake venue.
  All three are `neutral_site=True` and excluded, so no estimate is affected.
- **NHL season 2022 is not a clean control (Omicron).** Canadian teams Dec–Feb averaged
  `crowd_pct` .519 with 26 near-empty games. Config deliberately leaves 2022 untreated: the
  continuous dose is *correct* for those games, only the coarse `covid_era` label is imprecise,
  and only the 6b DiD is attenuated (~1–2% of control mass, biased toward zero = conservative).
  Marking all of 2022 treated would be worse — it would break self-anchored capacity.
- **`stadium_id.astype(str)`** maps null → `"nan"`; `walk_scoreboard` `str(None)` → `"None"`.
