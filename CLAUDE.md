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

**Do not simply agree with me. Be my sparring partner. Identify my blind spots,
structural risks, and faulty assumptions.**

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

## Phase 2 — NFL pilot loader (done 2026-07-02) — COMPLETE

Brainstorm → spec → plan → subagent-driven build. `src/data/nfl.py` emits the
validated 29-col panel for 2018–2023 to `data/interim/nfl.parquet` (1657 games,
0 dropped). 28/28 tests. Specs/plans under `docs/superpowers/{specs,plans}/2026-07-02-phase2-*`.

**Built (`src/data/nfl.py`):**
- `_build_panel(schedule, attendance, capacity, treated_seasons)` — pure transform
  (no net/disk); maps schedule → 29 schema cols → `validate()`. `capacity` keyed by
  `(stadium_id, season)`.
- `_fetch_attendance(espn_id)` — cached ESPN summary-endpoint fetch → `data/raw/nfl/espn/<id>.json` (immutable, write-once).
- `_derive_capacity(df, treated_seasons)` — **empirical full-house reference** (see below).
- `_check_coverage(miss, total)` — hard-fail if >5% of a season's games lack attendance.
- `load(seasons, treated_seasons)` → `(panel, dropped)`; `main(smoke)` + `--smoke` CLI.

**Key decisions settled this phase:**
- **Season range = config param `nfl.load_seasons: [2018, 2023]`.** Elo needs only
  ~1–2 seasons burn-in (it self-regresses); 2022–2023 are the **post-COVID reversion
  anchors** (asymmetric check: reversion corroborates, non-reversion is ambiguous).
- **Elo bridge = neutral prior 1500.0**, `away_travel_km` = null (both Phase-4 placeholders);
  the interim panel still passes the *full* `validate()` — one gate, no schema change.
- **crowd dose = EMPIRICAL capacity (Option A), NOT seated capacity.** ESPN attendance
  is *announced* (tickets distributed) and exceeds seated capacity for most stadiums
  (Dallas ~93k in an 80k stadium; ~60% of games over seated cap) — a units mismatch.
  No public turnstile source exists. So `capacity[stadium, season]` = that stadium-season's
  **max announced attendance** (self-calibrating full house); **treated seasons borrow**
  the stadium's non-treated max (suppression decided from `treated_seasons`, NOT a
  magnitude threshold — the magnitude guess would misfire on MLB/NBA 2021 partial
  reopenings). `crowd_pct = attendance/capacity` ∈ [0, 1.0]. Removed the hand-built
  seated-capacity yaml.
- **espn-id bug fixed:** the `espn` col is `float64`; must `dropna` then
  `.astype("int64").astype(str)` or the ".0" suffix 400s the ESPN URL.

**Result sanity (the natural experiment, visible in the raw dose):** `crowd_pct` mean
by season = 2018:.97, 2019:.97, **2020:.066**, 2021:.97, 2022:.98, 2023:.98. 154 empty
(crowd_pct==0) games. Clean before→during→after.

**Deferred Minors (for Phase 3 / polish):** `stadium_id.astype(str)` maps null→"nan";
`is_playoff = game_type!="REG"` assumes no preseason rows; a few cosmetic test-style items.

## Phase 3 carry-forward (read before starting)

- **Spike attendance FIRST, before any build** (repeat the pre-Phase-1 NFL spike per sport):
  does `pybaseball`/`nba_api` carry attendance? Does ESPN's `.../baseball/mlb/` and
  `.../basketball/nba/` summary endpoint expose `gameInfo.attendance`? Don't build until confirmed.
- **The join key is the likely sticking point.** NFL had an `espn` game id free in the
  schedule. MLB/NBA sources probably won't — expect to map games to ESPN ids via date+teams
  or ESPN's own schedule. This is the part most likely to differ from NFL.
- **Reuse, don't re-derive:** `_fetch_attendance` (cached ESPN fetch), `_derive_capacity`
  (Option A, suppression keyed off `treated_seasons`), and `_check_coverage` in
  `src/data/nfl.py` are the templates. The spec deferred extracting a shared ESPN helper to
  "when the 2nd consumer arrives" — that's now. Consider `src/data/_espn.py`.
- **Sport edge cases:** NBA always indoor (`is_dome=True`, weather null everywhere) + the
  **2020 Orlando bubble** (`is_bubble=True`, excluded from pooled model, mined in Phase 7);
  NBA seasons span two calendar years so `treated_seasons` labeling needs care. MLB: 2020
  Blue Jays "home" games in Buffalo (`relocated_home`/`neutral_site`), retractable roofs,
  doubleheaders, 81 home games (rich within-season attendance → Option A works well).
- **Data files are gitignored (local cache only).** `data/raw/nfl/espn/*.json` (1657 files)
  and `data/interim/nfl.parquet` are NOT in git — decided to keep the repo's original
  "never commit downloaded data" principle. A fresh clone re-fetches from ESPN; the local
  cache is the only copy, so don't `git clean -fdx` it away. Deferred code Minors are logged
  in `.superpowers/sdd/progress.md` (Phase 2 section).

## Phase 3 attendance spike (run 2026-07-07) — PASS, flips an assumption

Verified attendance source + join key for MLB and NBA. **Result: all three sports
go single-source on ESPN; the native packages (`pybaseball`/`nba_api`) are out.**

**Attendance source per sport:**
- **ESPN `baseball/mlb` summary** — ✅ `gameInfo.attendance`. Dose ramp: 2019 full
  (22320) → **2020 empty = 0 (a REAL zero)** → 2021 partial (17804).
- **ESPN `basketball/nba` summary** — ✅ present. 2019 (15388) → 2020 bubble (0) →
  2021 partial (1773).
- **`pybaseball.schedule_and_record`** — ❌ *has* an `Attendance` column BUT
  baseball-reference marks 2020 empty-stadium games "Unknown" → **`NaN`, not `0`**.
  That nulls exactly the treatment games and destroys the dose signal. Rejected.
- **`nba_api` BoxScoreSummaryV2** — ❌ `GameInfo.ATTENDANCE = None` even for a normal
  2019 game. Rejected. (The "nfl_data_py-lacks-attendance" pattern repeats.)

**The join-key worry is GONE.** ESPN's scoreboard-by-date endpoint
(`.../{sport}/scoreboard?dates=YYYYMMDD`) already returns the full day's game list:
event id, home/away teams+abbrevs, scores, venue, `neutralSite`, status. So the
architecture is **ESPN scoreboard (schedule/scores) + ESPN summary (attendance),
keyed by ESPN event id — no cross-source date+team join.** Simpler than NFL's
two-source approach. Iterate season dates (~180 MLB, ~170 NBA); cache every response.

**Decision: extract `src/data/_espn.py`** (shared cached fetch + scoreboard walk) —
2nd + 3rd consumers have arrived. `_derive_capacity` (Option A) and `_check_coverage`
carry over unchanged. Capacity is `None` in ESPN for both sports (same as NFL) → Option A.

**Rest/travel/Elo stay null at load** (Phase 4 fills them, exactly as NFL). ESPN
scoreboard doesn't carry them and they're computed sport-blind downstream anyway.

**Edge cases confirmed (must handle in the build):**
- **NBA bubble** — venue `"ESPN Wide World of Sports Complex"`, att=0, but ESPN says
  `neutralSite=False`. `is_bubble` must be a **date+venue flag** (Orlando, post-2020-07-30),
  NOT ESPN's neutral flag.
- **MLB relocated home** (TOR→Buffalo 2020) — ESPN venue name = the field actually played
  in; detect `relocated_home`/`neutral_site` via venue-mismatch, not ESPN's neutral flag.

## Phase 3 — MLB loader + shared `_espn.py` (done 2026-07-07) — COMPLETE

Brainstorm → spec → plan → subagent-driven build (5 tasks, per-task reviews + a
whole-branch final review = READY TO MERGE). Specs/plans under
`docs/superpowers/{specs,plans}/2026-07-07-phase3-mlb-*`. **48/48 tests. Real-data
smoke passes** (dose signal confirmed on live ESPN). Git is user-owned — all changes
sit uncommitted in the working tree awaiting the human commit.

**Built:**
- `src/data/_espn.py` — the shared, sport-agnostic ESPN layer: `fetch_summary(sport,
  event_id)` (cached summary→attendance), `walk_scoreboard(sport, start, end)`
  (scoreboard-by-date → normalized event dicts), and `derive_capacity`/`check_coverage`
  **moved verbatim from `nfl.py`** (single implementation → all sports compute
  `crowd_pct` identically). A shared `_cached_get(cache, url, throttle)` underlies both
  fetchers with **retry + capped backoff + jitter** (see robustness note).
- `src/data/mlb.py` — thin sport glue: `_select_games` (keep `season_type∈{2,3}`, drop
  preseason/all-star/unplayed) + `_build_panel` (→ validated 29-col panel) + `load`/`main`.
- `src/data/nfl.py` — **minimal edit**: aliases `derive_capacity`/`check_coverage` from
  `_espn.py` under their old private names; keeps its own `_fetch_attendance`. NFL
  behavior byte-identical; its 28 tests stayed green (verified in the final review).
- `config/sports.yaml` — `mlb.load_seasons: [2018, 2023]`, `treated_seasons: [2020, 2021]`.
- Tests: `tests/test_espn.py`, `tests/test_mlb_loader.py`.

**Decisions settled this phase (build):**
- **Single-source ESPN for MLB** (scoreboard + summary, keyed by event id) — the native
  packages are out (spike). No cross-source join.
- **No weather for MLB** — not a confounder of a policy-identified, margin-outcome crowd
  estimate (weather ⊥ COVID caps; symmetric on margin; the demand→attendance channel is
  mediation, not confounding). `temp_f/wind_mph/precip` null; `is_dome` True only for the
  one permanent dome (Tropicana venue id "31"), retractables→False (documented
  approximation, inert since weather is null).
- **MLB quality control = Elo** (Phase 4). `closing_spread` null — baseball is a
  *moneyline* sport with no meaningful point spread; a market signal (moneyline→win-prob)
  is a deferred optional feature, NOT the `closing_spread` column.
- **Relocated home** = hardcoded `(TOR, 2020)` (Buffalo); neutral special events not
  enumerated (option 4a) — `neutral_site` taken from ESPN's flag for free.
- Rest/travel/Elo = null/1500.0 placeholders (Phase 4), exactly as NFL.

**Robustness (learned from the real pull — NOT in the original plan):** MLB is ~2430
games/season, so a full pull is thousands of ESPN requests and ESPN **soft-rate-limits
sustained bulk fetching** (transient 502s; verified the endpoints are fine in isolation).
Added: (1) `_cached_get` retry with capped backoff + jitter (6 attempts); (2)
`fetch_summary` **swallows a persistent fetch failure → returns None** (counted as
missing attendance; the >5% coverage gate guards systemic loss) so one unlucky game can't
abort a 3300-game pull. `_fetch_scoreboard` stays **fail-loud** (a lost date is
unaccounted data loss). Cache is immutable/write-once, so a pull is self-completing across
cache-warm re-runs. **A full `[2018,2023]` pull takes ~hours cold** and may need a couple
re-runs to fully warm the cache — run `python -m src.data.mlb` to write
`data/interim/mlb.parquet` (not yet generated).

**Globe Life Field capacity note (important for interpreting output):** Option A borrows a
treated season's capacity from the venue's *non-treated* seasons. This is correct ONLY if
every venue has a non-treated season in the load window. The full config window
`[2018,2023]` satisfies this (2018/19/22/23 non-treated). But a venue that *opened in a
treated year* — Globe Life Field (2020, the MLB 2020 postseason bubble site) — is anchored
only by 2022/23, so a **narrow window that omits 2022/23 makes its `crowd_pct` spuriously
~1.0** (fallback to own max). This surfaced in the 2-season smoke and is why the smoke
asserts on **regular-season 2020 (all-empty, `crowd_pct==0`)** rather than a global max.
Bonus finding: **ESPN's `neutralSite` flag DID correctly mark the MLB 2020 bubble** (unlike
the NBA bubble) → those games carry `neutral_site=True` and drop out of the main model.

**Deferred Minors (final-review triaged, all acceptable):** NFL-side `derive_capacity`/
`check_coverage` tests now duplicate `test_espn.py` (retire NFL copies later);
`fetch_summary` AttributeError if ESPN ever emits `"gameInfo": null` (it doesn't);
`walk_scoreboard` `["team"]`/`str(None)`→"None" fragility (matches Phase-2 convention);
one untested skip branch; trivial doubleheader test; `load()` lacks type annotations.

## Phase 3 — NBA loader (done 2026-07-15) — COMPLETE

Spec → TDD build. `src/data/nba.py` reuses `_espn.py` unchanged, mirrors `mlb.py`,
with four NBA deltas. Spec: `docs/superpowers/specs/2026-07-14-phase3-nba-loader-design.md`
(no separate plan file this phase). **65/65 tests. Both real-data smoke AND full
parquet write passed on live ESPN.**

**Built (`src/data/nba.py`):** `_select_games` (type∈{2,3}, FINAL, non-null scores) →
`_build_panel` → `load`/`main`/`--smoke`. Four NBA-specific deltas:
1. **Continuous scoreboard walk** (not MLB's per-year windows) over `[date(min-1,9,1),
   date(max,11,30)]`, filtered by ESPN `season_year` — NBA seasons span two calendar
   years + the Aug-2020 bubble tail lands in `season_year=2020`.
2. **`is_bubble = (venue_id=="4066") & (season==2020)`** — venue+season, NOT ESPN's
   neutral flag (False for the bubble). Kept in panel for Phase 7, excluded downstream.
3. **`relocated_home = (TOR, 2021)`** — hardcoded Tampa relocation (venue 1396), like
   MLB's `(TOR, 2020)`.
4. **All-indoor:** `is_dome=True` unconditionally, weather null.

**Config:** `nba.treated_seasons: [2021]` (NOT [2020,2021]) — once the bubble is
excluded, 2020's remaining games are all full-crowd pre-March-2020; the clean
empty→partial signal lives entirely in 2021. Also keeps `derive_capacity`
self-referencing 2020's own full houses.

**`nba.parquet`:** 7571 games, 0 dropped. crowd_pct mean by season 2018:.94 2019:.93
2020:.79 (mixed: full pre-March + 171 empty bubble) **2021:.124** (treatment) 2022:.89
2023:.94. bubble=171, relocated=36, neutral=19, is_dome all True, weather all null.
Strongest treatment signal of the three sports.

**Capacity fix shipped this phase (`_espn.derive_capacity`, affects all sports):** a
treated season's capacity is now `max(non-treated fallback, that season's own max)`,
not just the borrowed fallback. Caught by the MLB build: the **2021 Rays ALDS Game 1**
(Oct 8 2021, Tropicana) was a reopened full house (37,616) that exceeded Tropicana's
tarped non-treated max (32,251) → `crowd_pct 1.166` tripped the validator's 1.05 ceiling.
`max()` preserves the anti-inflation intent (a suppressed season never lowers capacity)
while not under-anchoring a real full house. **No-op for NFL** (2020 near-empty
everywhere), fixes MLB, applies to NBA. Test: `test_espn.py::test_derive_capacity_
treated_own_max_wins_when_it_exceeds_borrow`.

## Phase 4 — sport-blind features (done 2026-07-15) — COMPLETE

Brainstorm → spec → plan → subagent-driven build (5 tasks + 2 controller-caught fixes +
1 final-review fix; per-task reviews + opus whole-branch review = READY TO MERGE). Specs/
plans under `docs/superpowers/{specs,plans}/2026-07-15-phase4-features*`. **86 tests. Real-
data build wrote all three `data/processed/{sport}.parquet`, each passing `validate()`.**

**Built (`src/features/build.py` — one sport-blind module, no sport branching):**
- `add_travel(panel, coords)` — haversine(away-city, home-city); `is_bubble`→0;
  `neutral_site`/`relocated_home`→NaN. Coords from new `config/venue_coords.yaml`
  (93 `(sport,team)→[lat,lon]` entries, city-level, **web-verified against Wikipedia
  stadium lists**, era-correct for 2018-23: OAK≠LV, LA/LAC share SoFi, NBA LAC=downtown).
- `add_rest(panel)` — days since prior game per **`(sport,team,season)`**; first game of a
  season → `NA` (Int64). Whole-day diffs.
- `add_elo(panel, params)` — "middle" 538-grounded Elo. **Params web-verified from 538**
  (`config/sports.yaml` `elo:` blocks): nfl 20/48/0.667, mlb 4/24/0.667, nba 10/100/0.75,
  mean 1500. Stores **PRE-game** ratings (a game's own result never enters its stored
  rating); HFA only inside the win-prob expectation; rating state keyed by `(sport,team)`.
- `build(sport)` (interim→3 transforms→`validate()`→processed), `elo_accuracy(panel,hfa)`,
  `main()`.

**Decisions settled this phase:**
- **Elo = "middle" not "full"** — MOV multiplier `ln(|margin|+1)`, no 538 autocorrelation
  term. HFA + carryover taken verbatim from 538 (MOV-independent); **K is scale-matched to
  our simpler multiplier** (NBA 10 not 20 — 538's K sits inside a normalized formula).
- **Don't bake rest/travel into Elo** (538 does) — they are separate regression controls;
  baking in would double-count. **Constant HFA, never fan-adjusted** (538 uses MLB 24 w/
  fans, 9.6 empty — that IS the crowd effect we're estimating; baking it in would absorb it.
  Nice independent corroboration + citable).
- **Output stage = `data/processed/`** (interim=loader output, processed=feature-complete).

**Elo accuracy gate (HFA-inclusive, bug-detection not tuning):** nfl 0.627, mlb 0.577,
nba 0.639. NFL/MLB in-band; **NBA 0.639 is a PASS** — the 66-68% band is 538's *full*
model; our middle Elo at 0.639 is legitimate (nowhere near <0.52 bug threshold, ranks the
right teams: NBA-2019 top = TOR/MIL/GS/HOU/POR). ~2pt gap = designed middle-vs-full cost;
no K-tuning (spec forbids for a control var). COVID dose survives the pipeline unchanged.

**Two bugs caught by controller verification (not by tests/reviewers):**
1. **Loader All-Star leak (Task 1, a Phase-3 gap):** ESPN types All-Star/Rising-Stars games
   as `season_type=2`, so they slipped the `{2,3}` filter with fake abbrevs (MLB AL/NL; NBA
   DUR/GIA/LEB/STE/USA/WORLD). Added exclusion sets to `mlb.py`/`nba.py` `_select_games`;
   **regenerated `mlb.parquet` (13277→13272) and `nba.parquet` (7571→7562)**.
2. **YAML "Norway problem" (Task 2):** bare `NO:` key parses as boolean `false`, dropping
   New Orleans (NFL Saints + NBA Pelicans) coords. Quoted `"NO"`; added regression test
   `test_coords_cover_every_panel_team` (asserts every panel team has coords).
Plus **F1 (final review):** `elo_accuracy` had omitted HFA — fixed to match spec gate #2.

**Deferred Minors (non-blocking, in `.superpowers/sdd/progress.md`):** Elo no-update on
ties (NFL-rare); coords-coverage test FileNotFounds on a cold checkout (no parquets);
doubleheader→rest 0; config test doesn't assert exact k/hfa; `_elo_params` returns YAML
ints; unused test fixtures.

## Phase 5 — descriptive HFA (done 2026-07-17) — COMPLETE

Brainstorm → spec → plan → subagent-driven build (2 tasks, per-task reviews +
opus whole-branch review = READY TO MERGE, zero findings). Specs/plans under
`docs/superpowers/{specs,plans}/2026-07-17-phase5-descriptive-hfa*`. **93/93 tests.**
Data sanity gate before modeling. All uncommitted, awaiting human commit.

**Built (`src/viz/descriptive.py` — one sport-blind module, no branching):**
- `summarize(panel) -> DataFrame` — pure/tested. Filters to **clean regular-season
  home games** (`is_playoff==False` AND NOT `neutral_site|relocated_home|is_bubble`),
  groups by season → win% + margin, each with a **naive iid SE** (proportion SE for
  win%, sample-mean SE for margin). Win% uses **decided** games only (ties→null
  dropped); margin uses all clean-home games (`n_games` includes ties). Appends a
  **pooled_fullcrowd** row over `covid_era==False` seasons only (the true-HFA headline
  — pooling all seasons would fold in the COVID dip). Emits a per-season `covid_era`
  bool (drives the gate; also documents which seasons were policy-restricted).
- `plot_hfa(table)` — 2-panel figure (win% / margin) by season, one line per sport,
  SE error bars, 0.5/0.0 reference lines, 2019.5–2021.5 COVID band shaded.
- `main()` → writes `results/tables/descriptive_hfa.csv` + `results/figures/hfa_by_season.png`, prints the gate.
- `tests/test_descriptive.py` (7 tests).

**Decisions settled this phase:**
- **Playoffs EXCLUDED from descriptive HFA** (not a subsection). Playoff home teams
  are the better seed (HFA blends with quality asymmetry → non-comparable), samples
  are tiny (NFL 10–12/season), and COVID-season playoffs collapse (NBA 2020 = 0 clean
  home games, all bubble; MLB 2020 postseason mostly neutral bubble sites) — so a
  playoff slice can't even show the dip. Document as a one-line caveat in Phase 8.
- **SEs are naive iid guards, NOT causal CIs** — a hedge against over-reading a noisy
  season; Phase 6 does the real clustered/robust inference.
- **Sanity gate is data-driven off `covid_era`, not a hardcoded 2020.** Treated seasons
  differ per sport (NFL 2020, MLB 2020–21, NBA 2021); the gate checks whether the worst
  *treated* season's margin falls below the full-crowd pooled baseline. (Caught in review:
  a hardcoded-2020 check gave NBA a **false PASS** off a coincidental 0.05 gap while its
  real dip lives in 2021.)

**Sanity-gate result (the pre-modeling data check):**
`[PASS] nfl` (pooled win .552, margin 1.75, 2020 dips) · `[CHECK] mlb` (win .528,
margin **0.04**, 2020–21 don't dip) · `[PASS] nba` (win .570, margin 2.26, 2021 dips).

**⚠️ SUBSTANTIVE FINDING carried to Phase 6a — MLB scoring-margin HFA is
noise-dominated.** Pooled MLB run-margin edge is +0.04 (SE .05); per-season SE ~.09
dwarfs it; 2019 is even negative (−0.004). The natural experiment is **visible in
NFL/NBA margin, invisible in MLB margin.** The design's "margin = more power" premise
**fails for baseball** — report win% (~.528) as MLB's primary HFA signal and expect
wide/insignificant MLB margin CIs in the causal model. Not a bug; the gate surfaced a
real property. (The COVID *dose* is still strong in MLB `crowd_pct`; it's the *margin
outcome* that lacks power, not the treatment.)

## Phase 6a — causal TWFE dose-response (done 2026-07-20) — COMPLETE

Brainstorm → spec → plan → subagent-driven build (2 tasks + a mid-build **design
correction**; per-task reviews + opus whole-branch review = READY TO MERGE). Specs/plans
under `docs/superpowers/{specs,plans}/2026-07-20-phase6a-twfe*`. **99/99 tests. Real-data
run wrote all artifacts.** All uncommitted, awaiting human commit.

**Built (`src/models/twfe.py` — one sport-blind module, no branching):**
- `fit(panel, outcome, sample, treated_seasons, extra_controls)` — pure estimator (no
  disk/net). Filters exclusions, builds `elo_diff`/`rest_diff`, fits `linearmodels.PanelOLS`,
  returns a flat dict (`coef, se, ci_low, ci_high, pvalue, n_obs, n_dropped, n_entities` +
  `coef_<control>`). `outcome ∈ {home_margin, home_win}`, `sample ∈ {pooled, restricted}`.
- `_restricted_seasons(treated) = set(treated) ∪ {min−1, max+1}`; `_prep` (exclusion filter
  + diff controls); `plot_effect` (forest plot); `main` (3 sports × 2 outcomes × 2 samples).
- Outputs: `results/tables/twfe_{nfl,mlb,nba}.csv`, `twfe_cross_sport.csv` (LPM only),
  `results/figures/twfe_crowd_effect.png`. Tests: `tests/test_twfe.py` (6).

**Decisions settled this phase (brainstorm):**
- **Two outcomes, identical RHS:** `home_margin` (power, NFL/NBA) + `home_win` as an **LPM**
  (0/1). LPM `crowd_pct` coef *is* Δwin-prob → the cross-sport common unit + MLB's real
  signal (Phase 5). No logit (incidental-parameters; breaks one-estimator rule).
- **Two samples:** pooled headline + restricted (`treated ∪ adjacent`) robustness check.
- **Controls (sport-blind):** `elo_diff`, `rest_diff`, `away_travel_km`. `closing_spread`/
  weather are NFL-only → separate NFL sensitivity check.
- **Exclusions:** `neutral_site | relocated_home | is_bubble | is_playoff`. Clustered SE by
  `home_team`.

**⚠️ THE BIG FINDING — season FE invert the estimate (mid-build correction, user-approved):**
The spec's original two-way FE (`entity + time`) produced **all 12 crowd coefs NEGATIVE**
(NFL margin −8.75), opposite the Phase-5 descriptive dip. Root cause: the COVID crowd shock
is **~a pure season-level treatment** (`crowd_pct` ~0.97 every normal season, ~0.07 in the
treated one), so **full season FE are near-collinear with `crowd_pct`** and absorb the
between-season contrast that *is* the natural experiment → coef identified off tiny residual
noise → garbage. Diagnostic (NFL margin): team+season FE −8.75 · **team FE only +1.92** · no
FE +2.19 · season-level corr(crowd,margin) +0.63. **Fix = team (entity) FE ONLY + a linear
`season_trend`** (nets out smooth drift without erasing the COVID contrast). A time-clustered
treatment is a within-team before/during/after comparison; full time FE erase it.

**Corrected headline estimates (team FE + trend):** NFL margin **+1.71** [−0.53, 3.95],
win% +0.046; NBA margin **+1.06** [−0.70, 2.81], win% +0.015; MLB margin −0.14 (noise),
win% −0.019. Signs match descriptive; per-sport CIs wide & cross zero (underpowered — Risk
#5, a finding not a failure).

**Final-review honesty corrections carried to Phase 8 (opus, independently reproduced coefs):**
1. **NO within-season dose curve for ANY sport** — within-2020 NFL dose↔margin corr ≈ −0.03.
   The Phase-2 "NFL carries the curve" hope is dead; all three are **on/off**. +1.71 is a
   level shift, not a curve (that absence is *why* two-way FE degenerates).
2. **`closing_spread` is a POST-TREATMENT bad control** — the spread is set knowing the
   stadium is empty and prices in reduced HFA, so the 1.71→0.81 attenuation is mechanical
   absorption of the crowd effect, NOT evidence the estimate is fragile.
3. **Identifying assumption stated plainly:** estimate = crowd effect **+ any other 2020–21
   league-wide home-margin shift**; the linear trend removes smooth drift, NOT the discrete
   pandemic shock; a treated dummy can't be added (collinear) → **no in-model separation**.
   **Phase 7's bubble decomposition is the disentangler.**

**6b promoted to co-primary:** since the treatment is time-clustered, the 2×2 on/off DiD is
the natural estimator, not a back-pocket — build it that way in Phase 6b.

## Phase 6b — on/off 2×2 DiD (done 2026-07-22) — COMPLETE

Brainstorm → spec → plan → subagent-driven build (2 tasks, per-task reviews + opus
whole-branch review = READY TO MERGE, zero Critical/Important). Specs/plans under
`docs/superpowers/{specs,plans}/2026-07-22-phase6b-did*`. **104/104 tests. Real-data run
wrote all artifacts.** All uncommitted, awaiting human commit.

**Built (`src/models/did.py` — one sport-blind module, no branching):**
- `fit(panel, outcome, sample, treated_seasons)` — pure raw before/after estimator. OLS
  `outcome ~ reduced` (`reduced = season ∈ treated_seasons`, season-level binary), SE
  **clustered by `home_team`**. Returns flat dict: `hfa_full` (=intercept), `hfa_reduced`
  (=intercept+coef), `crowd_effect = HFA_full − HFA_reduced = −coef` (positive = crowd helps
  home, **matches 6a's sign**), `se/ci_low/ci_high/pvalue` (CI **negated AND swapped** off the
  reduced coef; SE/p invariant under the flip), `n_full/n_reduced/n_obs/n_entities`.
- `plot_slope(results)` — dumbbell/slope, one panel per outcome, one row per sport,
  `hfa_reduced`(empty, hollow)→`hfa_full`(fans, filled); **pooled rows only** (restricted is
  table-only). `main()` → `results/tables/did_{nfl,mlb,nba}.csv`, `did_cross_sport.csv`
  (`home_win` rows only, same rule as 6a), `results/figures/did_hfa_shrink.png`.
- **`_exclusion_mask` extracted out of `twfe._prep`** → single shared exclusion definition
  across 6a/6b (behavior-preserving refactor; twfe's 6 tests stayed green). `did.py` reuses
  `_restricted_seasons` + `SPORT_COLORS` from `twfe`. `tests/test_did.py` (5 tests).

**Decisions settled this phase:**
- **What the "2×2 DiD" actually is.** No untreated *group* exists (COVID hit every team), so
  strictly this is a **comparative interrupted time series / within-unit before-after**. The
  outcome is already `home − away`, so the **away team is the implicit control group** and
  other seasons are the **control *period*** (not the control group — a distinction the user
  pushed on and it's right). Nets out *symmetric* league-wide 2020–21 shifts; does NOT net out
  *home-specific* non-crowd 2020–21 changes → **same confound as 6a**, NOT cleaner
  identification. Keep the precise naming in Phase 8; "2×2 DiD" is the intuitive label only.
- **Crowd binary = season-level off `treated_seasons`** (exogenous policy caps), not a
  game-level `crowd_pct<thr` (which would re-inject the endogeneity we dodged — a bad team
  drawing a small crowd in a normal season would be mislabeled "reduced").
- **Raw means, no controls** — that's the point (the intuitive number); "does it survive
  controls?" is answered by 6a. Clustered-by-team SE via the one-line regression, not
  `descriptive.py`'s naive iid SE.

**Corrected headline estimates (raw, pooled) — cohere with 6a within ~10–25%:** NFL margin
**+1.62** [−0.73, 3.96] (6a +1.71), win% +0.048; NBA margin **+1.34** [−0.72, 3.39] (6a
+1.06), win% +0.024; MLB margin −0.11 (noise, 6a −0.14), win% −0.013. DiD slightly larger
than 6a is expected (raw vs Elo/rest/travel-adjusted). MLB slope near-flat by design
(Phase-5 noise); per-sport CIs wide & zero-crossing (**underpowered — a finding, not a
failure**); pooled cross-sport win-prob is where any precision lives.

**Deferred Minor (cosmetic):** `plot_slope` legend swatches inherit the first-sorted sport's
color (mlb green) not neutral gray — hollow/filled *shape* still reads; fix only if the
figure is touched later (draw legend handles in gray).

## Status

**Phase 6b COMPLETE.** `src/models/did.py` + `tests/test_did.py` (5 tests) + `twfe.py`
`_exclusion_mask` extraction; `results/tables/did_{nfl,mlb,nba}.csv` + `did_cross_sport.csv`
+ `results/figures/did_hfa_shrink.png` generated. 104/104 tests. Opus whole-branch review
READY TO MERGE (one cosmetic Minor deferred; write-up honesty items carried to Phase 8). All
uncommitted, awaiting human commit (git is user-owned).

**Deferred / next:**
- **Phase 7 — bubble decomposition + seeding placebo (NEXT).** Doubles as the **disentangler** for
  6a's un-separated "crowd + other pandemic shifts" (normal − empty ≈ crowd; empty − bubble ≈
  travel + home-park).
- **Phase 8 — Quarto write-up.** Carry the three 6a honesty corrections above + the
  playoff-exclusion caveat + a **descriptive playoff-HFA subsection** (reuse
  `descriptive.summarize()` with `is_playoff==True`; blended with seeding quality → asterisk).
  **From 6b:** present 6a (adjusted) + 6b (raw before/after) side by side; use the precise
  "comparative interrupted time series / away-team-as-control" naming, not literal "2×2 DiD";
  state the shared 6a/6b confound explicitly and point at Phase 7 as the only disentangler.
  `did_hfa_shrink.png` is the intuitive centerpiece figure.
- **Why MLB shows no/faint-wrong-sign crowd effect (write-up section, all 3 methods agree).**
  (1) It's statistically ZERO, not a reversal — margin CI [−0.39,+0.16] p.42, win% CI
  [−0.038,+0.013] p.33; the negative sign is noise, don't over-read it. (2) Baseball's total
  HFA is smallest in major sports (home win% ~.53–.54 vs NFL ~.57, NBA ~.60 — WEB-VERIFY before
  citing), and its known mechanisms are **crowd-independent**: batting last (rules edge) + park
  familiarity (walls/sightlines/positioning) survive an empty stadium; the crowd→official-bias
  channel that drives NFL/NBA HFA is weak in baseball. (3) Run-margin is the noisiest outcome
  (worst signal/noise cell — Phase 5). (4) Confound is WORST in baseball: 2020–21 had more
  home-relevant rule changes than NFL/NBA — extra-innings ghost runner (favors batting-last =
  home), universal DH (2020), 7-inning DHs, regional 60-game schedule — inseparable in-model and
  several push HFA the home team's way, plausibly producing the faint wrong sign. Honest claim:
  "no detectable MLB crowd effect"; can NOT claim "crowds don't matter in baseball" (underpowered
  + confounded). **Optional cheap check (deferred):** split MLB treated into 2020 vs 2021
  separately — if the faint positive-HFA blip lives entirely in 2020 (rule-change season), that
  supports rule-artifact-not-crowd. A few lines against the existing panel, no new infra.
- **Delete ESPN caches** (`data/raw/*/espn`, ~14GB MLB + ~6GB NBA) once parquets verified —
  gitignored/local-only; only near project end (avoid re-pull risk).

**Maybe-later (optional, not required — the 3-sport study is complete on its own):**
- **Add NHL as a 4th sport.** *Why:* the study's main weakness is wide, cross-zero per-sport
  CIs; each extra sport that lived through the empty-stadium period is an independent
  replication that tightens the **pooled cross-sport** crowd estimate — the real power lever
  (more *seasons* don't help; treated games are fixed by history). *Why NHL specifically:* it
  fits the existing architecture almost for free — ~30 stable teams (team-FE + Elo hold),
  indoor like NBA (weather null), a clean empty→partial 2020–21 shock, and almost certainly
  the same ESPN `hockey/nhl` scoreboard+summary endpoints `_espn.py` is already parameterized
  for → just a new `src/data/nhl.py` loader; everything downstream is already sport-blind.
  *Before building:* run the same ~30-min attendance spike as the other sports (confirm ESPN
  carries `gameInfo.attendance` with a real `0` for empty games). *Caveat:* more sports buy
  precision + generalizability, NOT cleaner identification — the crowd-vs-other-2020–21-shifts
  confound is the same pandemic hitting everyone, so only Phase 7's bubble decomposition
  disentangles it. **Soccer is NOT a cheap add** (draws break the binary outcome, promotion/
  relegation breaks the panel, non-US data shape) — it would be its own separate study, not a
  4th loader.
