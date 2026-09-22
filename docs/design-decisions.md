# Design decisions

Why the study is built the way it is. Settled decisions only — if you are tempted to
re-litigate one, read the reasoning here first. Full original design:
`docs/superpowers/specs/2026-06-29-home-field-advantage-design.md`.

## The question (settled 2026-06-29)

1. **Two-part question** — descriptive ("how big is HFA?") + causal ("how much is the
   crowd?"). The descriptive number is what makes the causal number interpretable.
2. **Treatment** — *continuous* crowd dose (`crowd_pct`), identified off *policy capacity
   caps* over the full 2020–21 restriction window (not 2020 only). Endogenous historical
   attendance is kept as a *labeled descriptive* companion, never the causal headline.
3. **Estimator** — TWFE panel is the engine; the on/off before/after comparison is
   co-primary (promoted from "back-pocket" during Phase 6a, because the treatment turned
   out to be time-clustered). Synthetic control skipped as overkill.
4. **Confounders** — team quality (Elo), rest, travel, weather as controls. NBA bubble and
   relocated/neutral "home" games are flagged and EXCLUDED from the main model.
5. **Bubble** — never in the pooled model. Originally scoped as a code phase; **cancelled
   2026-07-24** and folded into the write-up as a hedged subsection. It was never the
   disentangler it was billed as (see `docs/results.md`).
6. **Schema** — ~29-column unified panel, one row per game, identical across sports (sports
   null what doesn't apply). Sport logic only in `src/data/`.

## Schema contract (Phase 1)

- **Validator is hand-rolled** (`Col` + `validate()` in `src/schema.py`), not pandera/pydantic
  — no new dependency, and the spec doubles as documentation.
- **`validate()` collects ALL violations** into one `ValueError` rather than failing fast.
- **Strictness = structural + domain + conditional.** Conditional rules: `home_margin ==
  home_score - away_score`; `crowd_pct ≈ attendance/capacity`; `home_win` matches margin sign,
  null only on ties; `is_dome ⇒ weather null`.
- **The weather rule is one-directional.** dome ⇒ null is a hard error; outdoor ⇒
  weather-present is NOT enforced (sources legitimately lack weather, and `roof` is
  three-state including retractable-`closed`). The reverse rule would cry wolf.
- **Nullable extension dtypes** for the three nullable int/bool columns (`home_win` →
  `boolean`, `home_rest_days`/`away_rest_days` → `Int64`) so a null can't silently upcast
  int→float and break the dtype contract.
- **`covid_era` is a treated-season set, not a date window.** Reopening was
  per-team-per-week (state policy), so a per-sport date would be false precision;
  `crowd_pct` already carries the exact per-game dose. `covid_era`'s job is to mark which
  crowd variation is **policy-driven** (not demand-driven, though confounded with calendar time; the paper no longer calls it exogenous, B.S E1) vs demand-driven (endogenous). It stays
  config-free in `validate()`; the *loader* sets it from `config/sports.yaml`.

## Features (Phase 4)

- **Elo is "middle", not full 538.** MOV multiplier `ln(|margin|+1)`, no 538 autocorrelation
  term. HFA and carryover taken verbatim from 538 (they are MOV-independent); **K is
  scale-matched to our simpler multiplier** (NBA 10 not 20 — 538's K sits inside a
  normalized formula). Params live in `config/sports.yaml` `elo:` blocks, web-verified.
- **Stored ratings are PRE-game** — a game's own result never enters its own stored rating.
  HFA enters only inside the win-probability expectation.
- **Do not bake rest/travel into Elo** (538 does). They are separate regression controls;
  baking them in would double-count.
- **Elo HFA is constant and never fan-adjusted.** 538 uses MLB 24 with fans / 9.6 empty —
  that IS the crowd effect we are estimating, so baking it in would absorb the answer.
  (It is also nice independent corroboration, and citable.)
- **Elo accuracy is a bug gate, not a tuning target.** Measured: NBA .639 > NFL .627 >
  NHL .585 > MLB .577 — correct ordering, all far above the .52 bug floor. The ~2pt gap to
  538's 66–68% band is the designed middle-vs-full cost. No K-tuning for a control variable.
- **Stage convention:** `data/interim/` is loader output, `data/processed/` is
  feature-complete.

## Estimators (Phases 6a / 6b)

- **Two outcomes, identical RHS:** `home_margin` (power) and `home_win` as an **LPM**. The
  LPM `crowd_pct` coefficient *is* Δwin-probability, which makes it the cross-sport common
  unit. No logit (incidental parameters; and it would break the one-estimator rule).
- **Two samples:** `pooled` (headline) and `restricted` = treated ∪ adjacent (robustness).
- **Controls, sport-blind:** `elo_diff`, `rest_diff`, `away_travel_km`. `closing_spread` and
  weather are NFL-only, so they are a separate NFL sensitivity check — never main-model.
- **Exclusions (shared by 6a and 6b via `twfe._exclusion_mask`):**
  `neutral_site | relocated_home | is_bubble | is_playoff`. SEs clustered by `home_team`.
- **⚠️ Team FE only + a linear `season_trend` — NOT two-way FE.** The COVID crowd shock is
  ~a pure season-level treatment (`crowd_pct` ≈ .97 every normal season, ≈ .07 in the treated
  one), so full season FE are near-collinear with `crowd_pct` and absorb the between-season
  contrast that *is* the natural experiment. Two-way FE inverts NFL and NBA (NFL margin
  −10.92 vs +1.93 with team FE only), inflates NHL win ~8×, and leaves MLB's sign intact (MLB
  R² .64 is not near-collinear) — `season_fe_sensitivity.csv`. The linear trend nets out smooth drift without erasing
  the discrete COVID contrast.
- **6b uses raw means, no controls** — that is the point (the intuitive number). "Does it
  survive controls?" is what 6a answers. Its crowd binary is **season-level** off
  `treated_seasons`, never a game-level `crowd_pct < threshold` (which would re-inject the
  endogeneity the design exists to dodge).
- **What 6b actually is:** no untreated *group* exists (COVID hit every team), so this is a
  **comparative interrupted time series / within-unit before-after**. The outcome is already
  `home − away`, so the **away team is the implicit control group** and other seasons are the
  control *period*. It nets out *symmetric* league-wide shifts but NOT *home-specific*
  2020–21 changes — the **same confound as 6a**, not cleaner identification.
- **6b sign convention:** `crowd_effect = HFA_full − HFA_reduced = −coef`; positive means
  the crowd helps the home team, matching 6a's sign.

## Identifying assumption, stated plainly

The estimate = crowd effect **+ any other 2020–21 league-wide home-margin shift.** The
linear trend removes smooth drift, not the discrete pandemic shock. A treated dummy cannot
be added (collinear with `crowd_pct`), so there is **no in-model separation**. Nothing in
this project resolves that — the bubble decomposition was investigated and does not.

## Sport roster is closed at four (outcome-independent grounds)

Recorded because sport selection must be defensible as outcome-blind — NHL was added
*before* its result was known and reported unchanged after.

- **Soccer/MLS** — draws break the binary outcome; promotion/relegation breaks the team panel.
- **WNBA** — 2020 was *entirely* a bubble (Bradenton), so the empty-with-travel regime does
  not exist; plus ~12 teams × ~32 games.
- **NCAA FB/BB** — hundreds of unstable rosters break team FE + Elo; different data source.
  A separate study, not a loader.

## Deferred / optional (nothing here is load-bearing)

- **NHL sensitivity checks:** (a) shootout-zeroed margin (`status.period == 5` → 0), a few
  lines against the built panel, available if anyone questions the ±1 censoring given 41.5%
  of games are one-goal; (b) regulation-time outcomes, rejected as primary in the NHL spec §4.1.
- **A market signal for MLB** (moneyline → win probability) as an optional extra control —
  explicitly NOT the `closing_spread` column.
- **Crowd → referee mechanism sub-study** — NFL `referee` is in the panel source and enables it.

## Zero-attendance reporting artifacts (2026-09-15)

- **Rule (pre-committed before any corrected estimate):** `attendance == 0` is real only inside a
  documented restriction window (`config/sports.yaml` `zero_attendance_windows`). Outside every
  window it is an ESPN reporting artifact, and `crowd_pct` becomes null. MLB's window is 2020 only,
  because every club admitted fans in 2021.
- **Null, not drop:** dropping a game would change neighbours' rest, travel and the Elo chain, and
  would remove games from 6b, which never uses dose. With null, only 6a loses the game, through its
  existing listwise deletion. `attendance` keeps the as-reported 0.
- **Where it lives:** `src/features/build.py` `null_reporting_zeros`, not the loaders. Re-running the
  NFL loader re-downloads schedules (network), and the rule is config data with no sport branching.
  `data/interim` stays as reported; `data/processed` carries the correction.
- **Not fixed here, disclosed:** zeros inside a window that fall after the team already hosted fans
  (37 in the model sample). Superseded by the reopening-zeros rule below.

## Reopening-zeros rule (2026-09-16)

- **`fans_from` = min(data, source), not either alone.** The data date (a team's first non-zero
  ESPN home game that season) is available for every team for free and needs no research, but it
  inherits ESPN's own reporting errors — a genuine early fans game can still show `attendance==0`.
  The sourced date can correct that, but only when a source exists and is more precise than the
  data. Taking the earlier of the two, per team-season, gets the correction where it's sourced and
  falls back to the data everywhere else, without ever guessing a date later than the evidence
  (the "never round backward" rule): a source giving only a month is anchored to the panel's
  earliest game that month, never assumed to cover an earlier one.
- **A re-closure needs its own source; it is not "resume the earlier logic."** `fans_from` marks a
  one-way door (a team doesn't un-readmit fans by default), so any zero after it is treated as an
  artifact unless a specific, dated source says the building actually closed again for that game.
  Symmetry would be wrong here: the prior (no more re-closures once fans return) matches what
  actually happened in every audited case that lacked a re-closure source, and a documented
  re-closure is exactly the kind of event that gets reported (arena press releases, beat-writer
  coverage), so an absent source after a real search is evidence of absence, not just missing
  data.
- **Null, not impute, same as fix 1.** A nulled reporting-artifact zero has an unknown true dose —
  imputing a plausible value (e.g. the team's typical dose that month) would manufacture a
  precision the source doesn't support and could tilt the estimate either way while looking more
  "complete." Nulling drops the game from 6a's listwise deletion only; 6b and every descriptive
  table are dose-blind and unaffected.
- **The rule was written after estimates were seen, and both versions ship.** The problem surfaced
  through a literature comparison (Ganz & Allsop; Phase 8 stage B.G5, finding "N1"), not through an
  outcome-blind audit. A scratch version of the rule was run and its estimates seen before this
  spec existed, and the "who counts as fans" definition was then amended after the Task 1 source
  review (public spectators, ticketed or invited; not team-affiliated or working staff). This is a
  legitimate post-hoc correction rather than a forking path because the audit that followed was
  **exhaustive and mechanical** — every zero-bearing team in every treated season was searched for
  a source (44 of 44, queries logged; 29 verdicts rest on a public source, 15 on the data alone —
  the first non-zero ESPN game, which the rule sets with no discretion — and none left unverified),
  regardless of which direction it moved that sport's estimate (it moved NBA toward zero and NHL
  away from zero). Both the scratch numbers and the final numbers are reported side by side in
  `results/tables/reopen_zero_sensitivity.csv`, so a reader can see exactly what looking at the
  estimate first bought.

