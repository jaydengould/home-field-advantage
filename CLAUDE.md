# home-field-advantage

## Goal

Two-part study across MLB, NBA, NFL, and NHL: (1) **quantify** home-field advantage
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

1. **The sport is just a PARAMETER.** All four sports normalize into a single
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
   *(NHL was added later as a 4th sport on the same contract — see its section below.)*
4. **Sport-blind features** — Elo, `crowd_pct`, rest, travel.
5. **Descriptive HFA** — win% / margin by sport & season + figures (data sanity gate).
6a. **Causal — TWFE dose-response** (the engine).
6b. **Causal — back-pocket on/off DiD** — *promoted to co-primary during 6a; the treatment is
    time-clustered, so the on/off comparison is the natural estimator, not a back-pocket.*
7. **Pre-write-up consolidation** — sensitivity module (5 prose-only numbers → 5 CSVs),
   literature positioning + `references.bib`, paper-facing fixes. *(The slot originally held
   ~~**Bubble decomposition + placebo**~~, **CANCELLED as a code phase 2026-07-24** — folded into
   the Phase 8 write-up as a hedged subsection; it was never the disentangler it was billed as.)*
8. **Quarto write-up** → PDF + HTML.

**How to build:** today's spec is the umbrella design, not a single build script.
Run `writing-plans` + execution **per phase** (the spec is too big for one plan) —
each phase is its own small spec→plan→build loop. Do NOT plan the whole project
at once.

*(The "next session" note that stood here was from the original design session, when no analysis
code existed. Current state lives in the **Status** section at the bottom of this file — read that
first.)*

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
failure**); pooled cross-sport win-prob is where any precision lives. ⚠️ **That last clause is
refuted — see the NHL section's meta-analysis paragraph.** The code now exists
(`meta_cross_sport.csv`, Phase 7), but the four sports share a **BIAS**, not merely independent
noise, so pooling shrinks sampling error only and the pooled SE is a **lower bound**. Do not lift
this sentence into the paper.

**Deferred Minor (cosmetic):** `plot_slope` legend swatches inherit the first-sorted sport's
color (mlb green) not neutral gray — hollow/filled *shape* still reads; fix only if the
figure is touched later (draw legend handles in gray).

## NHL — 4th sport (done 2026-07-25) — COMPLETE

Brainstorm → spec → plan → subagent-driven build (6 tasks, per-task reviews). Spec:
`docs/superpowers/specs/2026-07-24-nhl-fourth-sport-design.md`; plan:
`docs/superpowers/plans/2026-07-24-nhl-fourth-sport.md`. **122/122 tests.** All uncommitted.

**Built:** `src/data/nhl.py` + `tests/test_nhl_loader.py` (16 tests); `_espn.SPORT_PATH["nhl"]`;
`schema.py` sport values gained `"nhl"`; `config/sports.yaml` nhl block;
`config/venue_coords.yaml` nhl block (32 teams); `"nhl"` added to the 4 downstream sport lists
+ `SPORT_COLORS` amber `#e08b00` (in **both** `twfe.py` and `descriptive.py`);
`twfe.fit(..., drop_controls=())` + NHL travel diagnostic in `twfe.main()`.

**Four NHL-specific deltas** (everything else mirrors `nba.py`):
1. **32-team WHITELIST** instead of an all-star blacklist — robust to however ESPN types
   exhibitions. (The MLB/NBA all-star leak was `season_type=2`.) `ARI` in, `UTAH` out —
   ESPN's teams endpoint lists *current* teams and is wrong for a 2018–23 window.
2. **`relocated_home` = modal-venue rule** (`venue_id != value_counts().idxmax()` per
   `(home_team, season)`). Catches Winter Classic / Stadium Series / Heritage Classic /
   Lake Tahoe outdoor games AND the NHL Global Series (Stockholm, Helsinki, Gothenburg,
   Prague, Tampere) with no hand-maintained list.
3. **`is_bubble` is DATE-based**: `season==2020 & date>=2020-08-01` (Toronto/Edmonton hubs,
   1 Aug–28 Sep 2020). ⚠️ **CORRECTION (final review): the spec's claim that ESPN's
   `neutralSite=True` excludes the bubble for free is WRONG.** Measured: only **72 of 130**
   bubble games carry `neutral_site=True`; 58 do not. The exclusion holds today only because
   all 130 are `is_playoff=True`. **The date rule is load-bearing, not optional bookkeeping.**
   Phase 8's bubble/regime subsection must filter on `is_bubble`, NOT `neutral_site` — the
   latter silently admits 58 hub games.
4. **Wider season window**: Sept 1 (y−1) → **Sept 30** (y). Needed twice — season 2020's
   playoffs ran to 28 Sep 2020 and season 2021 ran Jan–Jul 2021. NBA's Nov 30 end would
   have silently truncated both.

**Decisions settled:**
- **OT/shootout games keep ESPN's final score, unchanged.** No zeroing, no regulation-time
  outcome, no schema change. Corroborated by 538's NHL Elo, which tested exactly this and
  found **"no predictive power in differentiating between one-goal results in regulation
  versus overtime/shootouts"** ([Neil Paine](https://neilpaine.substack.com/p/how-my-nhl-elo-ratings-and-forecast)) — cite in Phase 8.
- **Elo (538-sourced, web-verified): `k: 6, hfa: 50, carryover: 0.70`.** K transfers directly
  (our `ln(|margin|+1)` runs 86–95% of 538's `0.6686·ln(MOV)+0.8048` over 1–5 goals — the
  NFL/MLB case, not NBA's). **Documented deviation:** 538 reverts NHL toward 1505; we use a
  sport-blind 1500 (≈0.7pp of win prob).
- `closing_spread` null (puck line is a fixed ±1.5); `is_dome=True`, weather null.
- `treated_seasons: [2021]`, `load_seasons: [2018, 2023]` (end-year labels, NBA pattern).

**Data (measured):** 7678 games, **0 dropped** (100% ESPN attendance coverage), 32 teams,
3.1 GB cache. `crowd_pct` by season: 2018 .942 · 2019 .938 · 2020 .835 (truncated 11 Mar) ·
**2021 .100** · 2022 .865 · 2023 .937. Season 2021 = 952 games, **571 completely empty (60%)**.
⚠️ The "up to .976" figure is a **playoff game and is EXCLUDED from every model.** In the actual
**estimation sample**, 2021 `crowd_pct` runs **0 → 0.400** with the 99th percentile at **0.283**.
The earlier "richest within-season dose variation in the study" selling point was measured on
excluded games and is inflated — the honest version is below.
**`one_goal_share = 0.415`** (measured; replaces the spec's unverified "~10%" shootout guess).
Elo accuracy **0.585** / Brier .239 — PASS (pre-registered band .57–.58, bug floor .52).
Four-sport Elo ranking NBA .639 > NFL .627 > NHL .585 > MLB .577 = correct ordering.

**⚠️ THE RESULT — NHL is centred near zero and underpowered, and it is the sport with the
strongest treatment.** *(This header read "NHL is a **clean null**" until Phase 7 corrected it —
that phrasing is language ban #1 in the Status section, and it sat 300 lines above its own
rebuttal. NHL's win% SE is .0227 → MDE ≈ 6.3pp, and its CI **contains both** NFL's +0.046 and
NBA's +0.015, so it cannot distinguish zero from an NFL-sized effect. "Clean null" and
"independent null replication" both overstate it.)*

| Estimator | margin | win% |
|---|---|---|
| Descriptive pooled full-crowd | +0.254 (SE .033) | .538 (SE .0063) |
| TWFE pooled | **+0.008** [−0.219, +0.234] p=.947 | **+0.007** [−0.038, +0.051] p=.772 |
| DiD pooled | **−0.008** [−0.227, +0.211] p=.941 | **+0.006** [−0.038, +0.050] p=.791 |

6a and 6b agree to within 0.015 — the tightest cross-estimator agreement of any sport.
Descriptive gate = `[CHECK]` (no margin dip), same as MLB. **NHL HFA drifts downward across the
window independent of COVID** (win% .563 → .536 → .531 → **.532 (treated)** → .537 → .523).
⚠️ NOT monotonic — **2 of the 5 steps are UP** (+.0009, +.0047), and 2018→2019 alone (−.0271) is
larger than the rest of the window combined. Do not write "monotonic"; a referee plotting six
points will catch it. The substantive claim IS verified: a linear trend through the five control
seasons predicts 2021 win% .5348 vs actual **.5323 — a gap of 0.15 SE**. The empty-arena season
sits *on* the trend, not below it.

**The `season_trend` term is NOT absorbing the treatment** (the obvious objection, tested):

| trend spec | margin | win% |
|---|---|---|
| no trend at all | +0.0296 (se .118) | +0.0118 (se .023) |
| **linear (shipped)** | **+0.0077** | **+0.0066** |
| quadratic | +0.0316 | +0.0025 |

Removing the trend entirely moves win% by 0.005 — a fifth of an SE. Put this table in Phase 8;
it pre-empts the first question any referee will ask.

**Travel diagnostic (pre-committed, reported either way) — confound is empirically minor.**
`corr(crowd_pct, away_travel_km | 2021) = −0.138` (weak; the feared realignment collinearity
did not materialise). Dropping the travel control moves the coef by **+0.0045** (margin) and
**+0.0028** (win). `n_obs` **6949 → 6949 identical**, so the comparison is clean, not a sample
shift. Honest caveat: with a coefficient already ≈0 the diagnostic is less informative than it
would be against a non-null — but it does show travel is **not masking** an effect.

**⚠️ THE WITHIN-2021 DOSE CURVE — advertised as NHL's whole selling point, never run until the
final review. It comes out WRONG-SIGNED and must be reported (pre-commitment §2.4).**
Season 2021 only, team FE, same controls, clustered by home team:

| outcome | within-2021 dose | 95% CI | p | n |
|---|---|---|---|---|
| `home_margin` | **−1.414** (se .858) | [−3.099, +0.271] | .100 | 849 |
| `home_win` | **−0.281** (se .183) | [−0.639, +0.078] | .125 | 849 |

These are the **largest within-season dose magnitudes anywhere in the study**, and they point the
wrong way (more crowd → *worse* home performance). **Raw means go the OTHER way**: empty n=542
margin +0.149; with-fans n=307 margin +0.446. *(Values corrected in Phase 7 — the raw means are
now computed on the **fit sample** so `n_empty + n_fans == n_obs`; previously n=556/+0.146 and
n=310/+0.471 on a wider exclusion-only sample. Coefs, SEs, `n_obs` and support ranges unchanged.
`results/tables/within_season_dose.csv` is now authoritative over this prose.)* The sign flip on
adding team FE *is* the endogeneity lesson the whole design is built around — worth a paragraph
in Phase 8.
**Two caveats belong with it:** (1) within-team fan access in 2021 is confounded with calendar
time (states/provinces reopened progressively, so "more fans" ≈ "later in season"); (2) the
fitted range is 0–0.40, so a `crowd_pct` coefficient **extrapolates 2.5×** beyond support.
Neither p-value clears .05; do not report this as a negative effect, report it as *the
within-season design being uninformative and endogenous* — which is why the headline is
identified between-season.

**⚠️ UNDISCLOSED SPECIFICATION SENSITIVITY — state it in Phase 8 with its rebuttal, or a referee
finds it first.** NHL is the sport where 6a's "season FE are near-collinear with the treatment"
argument is **weakest**: R² of `crowd_pct ~ C(season)+C(home_team)` is NFL .974, NBA .916,
**NHL .878**, MLB .618. Under **full season FE**, NHL's win% coefficient is **+0.076 (se .048)** —
an order of magnitude above the headline and the largest point estimate in the study.
**The shipped spec is still right and the pre-commitment correctly froze it:** within-*normal*-
season crowd variation is demand-driven (good teams draw crowds *and* win), which is precisely
the endogeneity the design exists to dodge. The decomposition confirms it — within-2022 dose is
**+0.056** while within-2021 (the exogenous slice) is **−0.28**. Report the sensitivity *and*
this rebuttal together.

**⚠️ Did NHL tighten the pooled estimate? Yes for SAMPLING error — but pooling CANNOT do the
job earlier phases claimed for it.** (Final-review Critical; the correction matters more than
the number.)

| | FE (inverse-variance) | RE (DerSimonian–Laird) | τ² | I² |
|---|---|---|---|---|
| 3 sports | −0.0025 (SE .0127) | +0.0043 (SE .0183) | .000418 | 40.4% |
| 4 sports | −0.0003 (SE .0111) | +0.0014 (SE .0123) | .000088 | 13.8% |

**Three reasons the pooled number cannot carry a precision claim:**
1. **The four estimates share a BIAS, not just independent noise.** Each is *crowd effect + that
   league's 2020–21 non-crowd home-specific shift* — the confound this file names repeatedly.
   Inverse-variance pooling shrinks *sampling* error as 1/√k and does **nothing** to a bias term
   common across sports (same pandemic, same empty buildings, same schedule compression). The
   pooled SE is a **lower bound** on real uncertainty. Any "the pooled CI rules out effects
   larger than X" sentence is unsupportable and must not appear in Phase 8.
2. **The heterogeneity test has no power at k=4.** Rejecting homogeneity at α=.05 needs Q > 7.81
   (I² > ~62%); observed Q=3.48. And I² fell 40.4% → 13.8% *mechanically* because NHL landed near
   the pooled mean — that is not new evidence of homogeneity. Do NOT write "no significant
   heterogeneity, therefore a common effect": the MLB section of this file argues at length that
   the true effects are **not** common (baseball's HFA mechanisms are crowd-independent).
3. **The gain is specification-dependent and unstable.** FE-vs-FE = −12.8% CI width; RE-vs-RE =
   −32.8%. Both are unreliable at k=3→4 where τ² is barely estimable. Report the range, not one
   number. (Also: FE point estimate "moving" −0.0025 → −0.0003 is noise theatre — both are ~50×
   smaller than their SE. RE even flips the sign.)

~~⚠️ **This meta-analysis is NOT computed by any module**~~ — **RESOLVED in Phase 7.**
`src/models/sensitivity.py::meta_cross_sport` now emits both FE and RE to
`results/tables/meta_cross_sport.csv` (plus per-sport `mde_80`). The table above reproduced
exactly; the CSV is authoritative over this prose.

**⚠️ FINDING for Phase 8 — season 2022 is NOT a clean control (Omicron).** Canadian teams
Dec–Feb averaged `crowd_pct` **.519** with 26 near-empty games; Canadian 2022 .779 vs US .889;
Feb 2022 league-wide .728. `treated_seasons=[2021]` codes 2022 as untreated. **Config left
as-is deliberately:** `crowd_pct` for those games is *correct* (non-treated 2022 self-anchors
capacity on its own max, and Canadian venues hit full houses Mar–Jun), so the continuous-dose
TWFE headline is unaffected or helped; only the coarse season-level `covid_era` label is
imprecise, and only the 6b DiD is attenuated (~100 games of ~5 control seasons ≈ 1–2% of
control mass, biased toward zero = conservative). Marking all of 2022 treated would be worse
(season averages .865; would break self-anchored capacity).

**Other data notes:** `relocated_home` = 191 games (130 bubble + 61). Of the 61, **39 are the
NY Islanders' dual-arena era** (Barclays/Nassau split, seasons 2019–21) — a false positive
against the flag's *intent* (both were home buildings), left in place: 0.5% of games, exclusion
is conservative, and a split-arena season plausibly does dilute home-park familiarity. The other
22 are exactly what the modal rule was designed for. Three outdoor games have ESPN
`venue == "None"` and collapse into one fake venue (their `crowd_pct` compares Regina's gate to
the Cotton Bowl's capacity) — all three are `neutral_site=True` and excluded, so no estimate is
affected; documented, not fixed.

**Pre-commitments honoured (written before the pull):** NHL is reported in the cross-sport table
and pooled estimate regardless of sign/significance; no sport dropped post hoc; the 6a
specification was frozen and NHL got no bespoke tuning; the travel diagnostic was reported as
found.

## Phase 7 — pre-write-up consolidation (done 2026-07-28) — COMPLETE

Spec → plan → subagent-driven build (7 tasks, per-task opus/sonnet reviews, every task clean
after ≤1 fix round). Spec: `docs/superpowers/specs/2026-07-25-pre-writeup-consolidation-design.md`;
plan: `docs/superpowers/plans/2026-07-27-phase7-pre-writeup-consolidation.md`; ledger:
`.superpowers/sdd/2026-07-27-phase7-pre-writeup-consolidation/progress.md`. **122 → 152 tests, all
passing.** All uncommitted, awaiting human commit (git is user-owned).

**⚠️ THE STANDING RULE THIS PHASE ESTABLISHES — the CSVs are now authoritative over this file.**
Any number Phase 8 puts in the paper comes from `results/tables/` or a `.qmd` chunk, **never** from
`CLAUDE.md` prose. The prose here is a narrative index of what was decided and why; where the two
ever disagree, the CSV wins and the prose is the thing that's stale.

**Built:**
- `src/models/sensitivity.py` + `tests/test_sensitivity.py` (11 tests) — five prose-only numbers
  now have code behind them, one CSV each in `results/tables/`:
  `meta_cross_sport.csv` (FE inverse-variance **and** DerSimonian–Laird RE, Cochran's Q, I², τ²,
  per-sport `mde_80 = 2.8·SE`) · `trend_sensitivity.csv` · `season_fe_sensitivity.csv` (with a
  `crowd_pct ~ C(season)+C(home_team)` collinearity R² per sport) · `within_season_dose.csv`
  (all four sports, each row carrying its fitted support range) · `mlb_treated_split.csv`.
- `src/models/twfe.py` — `fit()` gained `trend={"linear","quadratic","none"}`, `season_fe=`,
  `report=` (which coefficient to return), `sample="treated"`, and the `extra_controls`
  duplicate-column de-dupe (stopped being latent — this phase added the callers). Named
  `ValueError`s replace bare `KeyError`s on bad `trend`/`report`.
- `docs/literature-review.md` (7 sections, §0–§6) + `paper/references.bib` (**12 entries**, replacing one
  comment line; every entry read at primary source).
- `src/viz/descriptive.py` — `summarize(panel, playoffs=False)` unblocks the Phase 8 playoff-HFA
  subsection (`~is_playoff` was hardcoded); `MARKERS` per-sport shapes; new palette.
- `requirements.txt` — `scipy` promoted to a declared direct dependency (it was working only
  transitively via statsmodels/linearmodels).

**Reproduction check — the CSVs agree with the prose except for one deliberate basis fix and one
transcription error the "zero discrepancies" claim below originally missed.**
Tasks 3/4/5 each re-derived their numbers and compared line by line against this file: the pooled
meta-analysis (FE −0.000334 / RE +0.001422, τ² .000088, I² 13.8%, Q 3.48; 3-sport FE −0.002511 /
I² 40.4%), the NHL trend sweep, all four collinearity R², NHL season-FE +0.076 (se .048), and all
nine NHL within-2021 reference values. **That sweep was reported as "zero discrepancies" and it had
one:** the NHL trend table above gave the no-trend margin SE as `.121` where
`trend_sensitivity.csv` says **0.11838 → .118** (corrected 2026-07-28; every other cell in that
table does match). This is the **second** false self-verification caught in this phase — the first
was a `'clean null'` grep reported as run that was never run (ledger, Task 7 review C1). Both were
found by a *later* reviewer, not by the agent that claimed the check, which is the whole hazard: a
reported pass stops anyone else from looking. Treat any "verified / zero discrepancies" line in this
file as a claim to re-run, not a result. The frozen 6a/6b headline numbers
were verified unchanged by **three independent checks** — two **byte-identical** (implementer diff,
task reviewer from the package) and one a **live refit matching at rtol=1e-10** across all 16
`twfe_*.csv` rows and all 24 `trend_sensitivity.csv` rows (a tolerance match, not bitwise: it
re-estimates rather than re-reads, which is the stronger check of the three precisely because it
can't go stale). The one value that **moved** is recorded in the NHL section above:
the within-season raw means are now computed on the *fit* sample so `n_empty + n_fans == n_obs`
holds in all eight rows.

**⚠️ CITATION CORRECTION — this file was wrong, and the wrong version was about to enter the paper.**
The NBA "**2.13 → 0.44 pts**" figures are **Ganz & Allsop (2024)**, *A Mere Fan Effect on Home-Court
Advantage*, *Journal of Sports Economics* **25(1), 30–53** — an FE-IV study instrumenting with
2020–21 NBA attendance restrictions. They are **NOT** Higgs & Stavness (2021), which is a Bayesian
negative-binomial model reporting **log-scale** parameters and contains no such pair. Verified
independently by two agents against both primary sources. Both papers are in the bib; cite Ganz &
Allsop for that number. (Related conflation also fixed: the **6/2/8/10** ghost-game split is
Leitner et al.'s 26-study review — primary-verified verbatim at **PMC8724651**, open access, incl.
"not a single study that found an *increased* home advantage". Wang & Qin (2023) is a *different*
review of 28 articles split by **outcome type** 8/6/4/10. Do not merge the two.)

**⚠️ THE LITERATURE IS NOT NEAR-UNANIMOUS — soften the framing this file used.** Three published
nulls sit on our side of the line: **Schank et al. (2024)** finds a null across a *full* Bundesliga
spectator-ban season (2020/21) with a **U-shaped** dose curve in 2021/22; **Higgs & Stavness (2021)**
finds no meaningful **MLB** change; **Gong (2022)** is a null on the **NBA referee-bias mechanism**.
The honest statement is "predominantly, but not unanimously, in favour of a crowd effect" — not
"our null vs a near-unanimous literature".

**⚠️ THE ANSWER TO Q3 (are we underpowered relative to the studies that found effects?) — YES, and
it should become Phase 8's lead framing.** In **seven of eight** sport × outcome cells the 80%-power
MDE **exceeds that sport's entire home advantage**, and in the eighth (NBA win%) it **equals** it:

| MDE ÷ total HFA | margin | win% |
|---|---|---|
| nfl | 1.82× | 1.96× |
| mlb | 10.59× | 1.59× |
| nba | 1.11× | **1.02×** |
| nhl | 1.27× | 1.66× |

**A crowd effect accounting for 100% of home-field advantage would go undetected at 80% power in
seven of the eight cells, and would sit exactly at the detection threshold in the eighth.** (Say it
that way, not "in any cell" — and do NOT bolt "and this is robust to rescaling" onto it; caveat (2)
below moves **three** cells to ≈1.0 or below.) This is sharper and more defensible than
"underpowered and centred near zero" — the conclusion is *this design cannot distinguish zero from a
crowd effect explaining all of HFA*, not "no effect", and not "we contradict the literature".
**Two caveats travel with it, always:**
(1) the denominator is `mde_80 / (pooled_fullcrowd win% − 0.5)` from `descriptive_hfa.csv`
(nfl .0520 · mlb .0282 · nba .0705 · nhl .0383), `mean_home_margin` for the margin column;
(2) **the coefficient is scaled per unit `crowd_pct`, and no sport's data spans a full unit.**
Realised crowd levels differ sharply *by sport* — measured on the exclusion-filtered estimation
panel, control-season mean `crowd_pct` is nfl **.97** · mlb **.65** · nba **.92** · nhl **.92**,
against treated-season means of .064 · **.318** · .073 · .062. **MLB is the outlier in both
columns**: under the Option-A empirical-capacity definition, announced MLB attendance never
approaches the stadium-season maximum, so a normal MLB season averages .63–.67 dose and only 17% of
its games exceed 0.9. (The earlier version of this caveat quoted a single "~0.88–0.93 units" band
and treated-season means "0.066–0.124" — both were computed from NFL and NBA only, with MLB left
out. They are wrong for MLB on both sides.) Rescaling each MDE to its own sport's realised contrast
(a crowd effect explaining 100% of HFA implies β = HFA ÷ control-crowd level) gives:

| rescaled MDE ÷ total HFA | margin | win% |
|---|---|---|
| nfl | 1.77× | 1.90× |
| mlb | 6.86× | **1.03×** |
| nba | **1.02×** | **0.94×** |
| nhl | 1.17× | 1.52× |

**Three cells land at ≈1.0 or below** (nba win% 0.94, nba margin 1.02, mlb win% 1.03), and nhl
margin falls 1.27 → 1.17. So the seven-of-eight statement is correct **at per-unit scaling** and is
**not** robust to rescaling — the rider "neither point touches the other seven", which this file
carried until 2026-07-28, was false. State the scaling basis in Phase 8; do not claim the
conclusion is unaffected by it. **A third consequence, never stated anywhere until now: MLB's
headline `crowd_pct` coefficient extrapolates roughly 1.5× beyond the dose MLB typically attains**
— it reads a 0→1 contrast off an empty→typical-full contrast of 0→.65. That is exactly the
support-range caveat already carried for the NHL within-2021 dose fit, and it applies here to a
*headline* estimate, not a sensitivity. Where a published effect exists in a
convertible unit (**NBA only**), our interval contains it: Ganz & Allsop's 2.13 → 0.44 converts to
Δ = **4.65 pp** (Φ(μ/σ), σ = 14.42 measured on our own clean NBA panel, n = 6,925) against our NBA
win% MDE of **7.18 pp**, and our margin CI [−0.70, +2.81] contains their 1.69-pt effect. No
conversion was invented for the football studies (draws break the binary outcome) or for Higgs &
Stavness (log-scale, no published translation).

**Palette (C2) — both warm hues failed, and the fix is a documented trade, not a free win.**
`#e87ba4` (nba, **2.69** against white — 2.62 against the `#fcfcfb` figure background; fails
either way) failed the 3:1 floor as expected — but so did `#e08b00` (nhl, **2.67**),
and that second failure was **invisible** because the test asserted inside a `for` loop over an
insertion-ordered dict and short-circuited at nba. Shipped: nba **`#a4036f` (7.44)**, nhl
**`#e42800` (4.56)**; nfl `#2a78d6` (4.42) and mlb `#008300` (4.95) unchanged. **The honest trade:**
contrast improved, but deuteranopia separation on the green/red (mlb–nhl) pair regressed
**19.62 → 8.4 ΔE** — still clearing the 6.0 floor and the 8.0 target, but that pair is now the
tightest in the figure. **No non-red alternative exists**: a brute-force sweep of ~1500 warm hexes
plus an independent reviewer sweep showed every amber/brown collapses onto green under
protan/deutan simulation (`#c77800` 3.5 · `#b36b00` 1.2 · Okabe-Ito `#d55e00` 1.6 — deep FAIL, not
WARN). The theoretical all-pairs ceiling given fixed blue/green/magenta is 13.25 and is set by the
*existing* mlb–nba pair, not slot 4. Mitigations shipped alongside: **per-sport marker shapes**
(`MARKERS = {nfl "o", mlb "s", nba "^", nhl "D"}` in both `descriptive.py` and `twfe.py`, wired into
`plot_hfa` and `plot_effect`) so sport is no longer encoded by colour alone; a parametrized contrast
test (one case per sport — the loop structure that hid the nhl failure is gone); a **CVD floor
regression guard** over all 6 pairs asserting ≥ 6.0 ΔE, shown failing on a contrast-fixed-but-
CVD-blind palette; and the cross-module equality test now guards **both** `SPORT_COLORS` **and**
`MARKERS`. `descriptive_hfa.csv` and all 17 tables reproduce byte-identical — figures only.

**C3 claim verification — all three VERIFIED, nothing cut.** (1) NHL 2020–21 four-division
realignment incl. the all-Canadian North Division — structure confirmed, but NHL.com does **not**
state cross-border travel as the *reason*; hedge the rationale (the travel diagnostic's
justification survives regardless: a division-only 56-game schedule mechanically changes the 2021
travel distribution). (2) TOR/EDM played bubble games in their own arenas — confirmed, and the
higher seed was *designated home team* with customised in-arena presentation, which corroborates
that the bubble is **not** a clean placebo zero. (3) Bubble hub dates 1 Aug – 28 Sep 2020 —
confirmed, matching `src/data/nhl.py`'s `is_bubble` rule exactly. Sources 2 and 3 are Wikipedia
(tertiary) — upgrade if either does argumentative work.

**Decisions settled this phase:**
- **`trend="none"` is load-bearing for within-season fits** — a linear trend on a single season
  raises "exog does not have full column rank".
- **`within_season_dose` raw means are on the FIT sample**, not the wider exclusion-only sample, so
  the raw contrast and the adjusted coefficient are attributable to *adjustment* rather than to a
  sample difference. Support ranges (`crowd_min/max/p99`) deliberately stay on the wider sample
  (they move ≤ .0007).
- **`mlb_treated_split` sign convention is NOT 6b's.** `did.py` publishes `crowd_effect = −coef`;
  this table reports the **raw treated-year level, unnegated**. Positive here means home margin was
  *higher* that year, i.e. the implied crowd effect is **negative** — the opposite reading from 6b.
  A Phase-8 writer who reads +0.0595 as "crowd helped home" has it backwards.
- **The collinearity R² is approximate by construction** — it runs on 1–6% more rows than the fit
  (exclusions only vs exclusions + control listwise-drop), moving R² by ≤ 0.0023. It **cannot** be
  made exact: NFL's two outcomes have different fit samples (1463 vs 1459), so one R² per sport is
  necessarily approximate. Invisible at the 2dp the paper cites and it does not disturb the
  NFL > NBA > NHL > MLB ordering that carries the argument. Documented, not fixed.
- **MLB treated-season split puts BOTH year indicators in one model** — each absorbs the other if
  omitted (dropping the 2021 indicator moves the 2020 coefficient .0595 → .0358). The two
  `report=` calls are two **views of one regression**, not two regressions.

**Measured results new this phase:** MLB's faint negative headline does **not** live entirely in
2020 — both treated years come out slightly *positive* on the year-indicator level (2020 +0.0595
se .174 · 2021 +0.1190 se .114 for margin; +0.0146 · +0.0101 for win%, all p > .29, n 12893). The
"is it a 2020 rule artifact?" check is therefore **inconclusive, not confirmatory** — and it cannot
separate 2020's rule changes from crowd effects in any case (`main()` prints that caveat).

**⚠️ CARRY TO PHASE 8 (four items that will otherwise be mis-written):**
1. **NFL's within-season `home_margin` is effectively unidentified** — se **29.24**, CI ±57.6.
   Mark it **non-estimable**; do not table it beside NHL's −1.41 as though the two are comparable.
2. **`summarize(playoffs=True)` OMITS seasons with zero clean playoff games entirely** rather than
   emitting `n_games=0` rows (NBA 2020, NHL 2020 — both all-bubble). Correct behaviour; Phase 8
   must expect *missing* rows, not zero rows.
3. **The raw-contrast-vs-team-FE-coefficient sign opposition reproduces in BOTH NHL and MLB** —
   NHL raw +0.297 vs coef −1.414; MLB raw +0.020 vs coef −0.350. That is the endogeneity lesson
   reproducing **across sports**, not two anomalies. Write it as the design point it is.
4. **`within_season_dose.csv` carries TWO sample bases in one row, and the CSV itself does not say
   so.** `crowd_min/max/p99` sit on the broad exclusion-only `_prep` sample ("what doses exist at
   all"); `raw_empty_mean`/`raw_fans_mean`/`n_empty`/`n_fans` sit on the narrow fit sample (so
   `n_empty + n_fans == n_obs` and the raw contrast is comparable to the adjusted coefficient).
   Deliberate and documented in `within_season_dose`/`_dose_fit_sample` docstrings — but Phase 8
   reads the CSV, not the docstrings. Do not describe the support range and the raw means as coming
   from the same rows.

**Deferred Minors (non-blocking, logged in the phase ledger):** `systematicreview_ghostgames`' PDF remains
publisher-blocked (Springer 303 / ResearchGate 403) — the PMC mirror carries the full text, so the
quotes are primary-verified, but the *published* PDF was never seen. The
`plosone_nhl_penalties` playoffs interaction has an **internal source inconsistency**: the paper's
prose says b = .17, its own regression table says **b = .186 (SE .083, z = 2.254, p = .024)** — the
table is authoritative and `.17` is not even a rounding of `.186`; a transcription note ships with
it. `_delta_e_cvd`'s Machado-2009 matrices are copied verbatim from the dataviz skill's bundled
validator (the skill lives outside the repo, so they must stay in lockstep by hand).

## Status

**Phase 7 (pre-write-up consolidation) COMPLETE.** 152/152 tests. Five new tables in
`results/tables/` (`meta_cross_sport`, `trend_sensitivity`, `season_fe_sensitivity`,
`within_season_dose`, `mlb_treated_split`) alongside the frozen `descriptive_hfa` / `twfe_*` /
`did_*` set — all 17 CSVs content-verified identical where they were meant to be frozen. All three
figures regenerated with the new palette + marker shapes. `docs/literature-review.md` and a
12-entry `paper/references.bib` now exist. All uncommitted, awaiting human commit (git is
user-owned).

**⬅ NEXT — Phase 8: Quarto write-up → PDF + HTML.** Everything the paper needs now exists as code
and CSVs — every **estimator** the paper needs now exists. **Two tables remain to be computed
inline in Phase 8** (neither has a CSV): the descriptive playoff-HFA table via
`summarize(panel, playoffs=True)`, and the NBA bubble decomposition + seeding placebo.

**Four-sport headline (pooled, win-probability LPM — the cross-sport comparable unit):**
nfl **+0.046** · nba **+0.015** · nhl **+0.007** · mlb **−0.019**. Every per-sport CI crosses zero.
NFL remains the only appreciable point estimate (**+4.6pp, p=.20**).

**⚠️ THE HONEST CONCLUSION (Phase 7 sharpened this — lead with the power statement, not the null):**

> In seven of eight sport × outcome cells, the effect this design could detect at 80% power is
> **larger than the entire home-field advantage of that sport**; in the eighth it is equal to it.
> (That ratio is **per unit `crowd_pct`**. Rescaled to each sport's realised crowd contrast —
> nfl .97 · mlb .65 · nba .92 · nhl .92 — **three** cells fall to ≈1.0 or below. Both scalings are
> in the Phase 7 section above; say which one you are quoting, and do not claim the statement is
> unaffected by the choice.)
> Four replications, each individually underpowered, all centred near zero, none able to exclude a
> crowd effect of the size NFL's point estimate implies. In the one sport where a published
> estimate converts to our units (**NBA**), our interval contains it. A shared, unmeasured 2020–21
> home-specific confound remains, and **pooling does not
> reduce it.** The claim this study can defend is that it cannot distinguish zero from a crowd
> effect accounting for all of HFA; it is *not* evidence that crowds don't matter.

**Language bans, binding on Phase 8 (spec §6 — earlier drafts violated all four):**
1. Do **NOT** call any sport's result a "**clean null**" or an "independent null replication".
   NHL's win% SE is .0227 → MDE ≈ 6.3pp, and its CI [−0.038, +0.051] **contains both** NFL's +0.046
   and NBA's +0.015. It is consistent with the other nulls, not corroboration of them.
2. Do **NOT** write any sentence of the form "**the pooled CI rules out effects larger than X**".
   The four sports share a **BIAS**, not merely independent noise — pooling shrinks *sampling*
   error as 1/√k and does nothing to a bias common across leagues. The pooled SE is a **lower
   bound** on real uncertainty.
3. Do **NOT** read absence of heterogeneity as evidence of homogeneity. At k=4 the Q test has no
   power (needs Q > 7.81; observed 3.48), and I² fell 40.4% → 13.8% *mechanically* because NHL
   landed near the pooled mean.
4. Do **NOT** re-specify the frozen 6a model. The specification was pre-committed and every number
   in `results/tables/` is byte-verified against it.

**Phase 8 checklist (carried forward):**
- The three 6a honesty corrections (no within-season dose curve for any sport; `closing_spread` is
  a **post-treatment bad control**; the identifying assumption stated plainly = crowd effect **+**
  any other 2020–21 league-wide home-margin shift, with no in-model separation).
- Present **6a (adjusted)** and **6b (raw before/after)** side by side; use the precise
  "**comparative interrupted time series / away-team-as-control**" naming, not literal "2×2 DiD";
  state the shared 6a/6b confound explicitly. `did_hfa_shrink.png` is the intuitive centerpiece.
- The playoff-exclusion caveat **plus** a descriptive **playoff-HFA subsection** via
  `descriptive.summarize(panel, playoffs=True)` (now unblocked) — blended with seeding quality, so
  it carries an asterisk, and expect *missing* seasons rather than zero rows.
- The **NBA bubble decomposition + seeding placebo** as a short, explicitly-hedged subsection
  computed inline — **not** a disentangler. The placebo is n=88, margin +1.65 (SE 1.35) → CI ≈
  [−1.0, +4.3], containing both 0 and full normal HFA (2.26): a test that cannot fail. The
  decomposition's second row is wrong-signed (`empty − bubble = −0.73`). The bubble sits *inside*
  the pandemic window and swaps one bundled treatment for another, and bubble "home" teams kept
  court branding, uniform choice and bench conventions, so its null isn't cleanly zero. **NHL's
  bubble does not help** — all 130 games are playoffs, therefore quality-confounded, so they can
  feed **neither** the placebo (which needs `is_playoff==False`) **nor** the regular-season
  decomposition table. Report the regime table with SEs and draw no
  inference.
- The **NHL sections** above in full: the trend-sensitivity table, the season-FE sensitivity **with
  its rebuttal**, the wrong-signed within-2021 dose curve **with both caveats**, the travel
  diagnostic, and the 2022-Omicron control-contamination note.
- **Why MLB shows no/faint-wrong-sign crowd effect.** (1) Statistically ZERO, not a reversal —
  margin CI [−0.39, +0.16] p.42, win% CI [−0.038, +0.013] p.33; the negative sign is noise.
  (2) Baseball's total HFA is smallest in major sports (home win% ~.53–.54 vs NFL ~.57, NBA ~.60 —
  **WEB-VERIFY before citing**) and its known mechanisms are **crowd-independent**: batting last
  (rules edge) + park familiarity survive an empty stadium; the crowd→official-bias channel that
  drives NFL/NBA HFA is weak in baseball. (3) Run-margin is the noisiest outcome (Phase 5), and
  MLB's MDE is **10.6×** its own HFA — the worst cell in the study. (4) Confound is WORST in
  baseball: 2020–21 stacked the extra-innings ghost runner (favours batting-last = home), the
  universal DH, 7-inning doubleheaders and a regional 60-game schedule — inseparable in-model,
  several pushing HFA the home team's way. The `mlb_treated_split.csv` check came out
  **inconclusive** (both years slightly positive) — it does **not** confirm the rule-artifact
  story. Honest claim: "no detectable MLB crowd effect"; can **NOT** claim "crowds don't matter in
  baseball".
- **Cite Ganz & Allsop (2024) — not Higgs & Stavness — for NBA 2.13 → 0.44.** Soften "near-unanimous
  literature" to "predominantly but not unanimously". Lift §§1–5 of `docs/literature-review.md`
  directly; every number in it was independently reproduced during review.

**Deferred (post-write-up):**
- **Delete ESPN caches** (`data/raw/*/espn`, ~14GB MLB + ~6GB NBA + ~3GB NHL) once the parquets are
  verified — gitignored/local-only; only near project end (avoid re-pull risk).

**Maybe-later (optional — the 4-sport study is complete on its own):**
- **The sport roster is closed at four, on structural (outcome-independent) grounds.** Soccer/MLS:
  draws break the binary outcome, promotion/relegation breaks the team panel. WNBA: 2020 was
  *entirely* a bubble (Bradenton), so the empty-with-travel regime does not exist, plus ~12 teams ×
  ~32 games. NCAA FB/BB: hundreds of unstable rosters break team-FE + Elo, different data source —
  a separate study, not a loader. Recording these matters: sport selection must be defensible as
  outcome-independent, and NHL was added *before* its result was known and reported unchanged after.
- **Deferred NHL sensitivity checks (neither load-bearing):** (a) shootout-zeroed margin — re-run
  NHL `home_margin` with `status.period == 5` games set to 0, a few lines against the built panel,
  available if anyone questions the ±1 censoring given 41.5% of games are one-goal; (b)
  regulation-time outcomes as the fuller alternative, rejected as primary in spec §4.1.
