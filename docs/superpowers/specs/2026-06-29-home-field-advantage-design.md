# home-field-advantage — research design

**Date:** 2026-06-29
**Status:** Approved design (pre-implementation)

## 1. Research question (two-part)

1. **Descriptive — "how big is home-field advantage?"** Quantify it per sport and
   over time (home win %, scoring margin), with charts, tables, and numbers.
2. **Causal — "how much of it is the crowd?"** Estimate the crowd-attributable
   slice of home advantage using the COVID empty/partial-stadium period as a
   natural experiment.

The descriptive number makes the causal number interpretable. The headline
sentence the paper must be able to write: *"Home teams win ~X%; we estimate the
crowd accounts for ~Y of that, leaving the rest to travel, familiarity, and
officiating."*

## 2. Treatment definition

- **Continuous dose**, not binary. The crowd is a dial (`crowd_pct`), not a switch.
  A dose-response curve ("does 50% of a crowd give half the advantage?") is the
  quantification we want.
- **Identified off policy-imposed capacity caps** over the **full 2020–21 COVID
  restriction window** (~Mar 2020 → full reopening in 2021), which ran a staggered
  `0% → partial → 100%` ramp by city/sport/week driven by local health policy.
  This window has real dose variation in all three sports, unlike "2020 season
  only" (NBA 2020 was a flat-0% bubble; MLB 2020 regular season was ~0%).
- **Why caps, not raw attendance, for the causal claim:** in normal seasons
  attendance is endogenous — bad teams draw small crowds *and* lose, so team
  quality causes both. Policy caps were forced by rules, not chosen by fans, so
  they are plausibly exogenous to game outcome.
- **Endogenous companion (descriptive only):** the rich historical
  attendance↔winning relationship (especially MLB) is reported as a *labeled
  descriptive* dose-response with every available control — explicitly flagged as
  correlation contaminated by team quality, never as the causal headline.

## 3. Estimator / control design

- **A — Two-way fixed-effects (TWFE) panel = the engine.**
  `home_margin ~ crowd_pct + controls + team_FE + season_FE`.
  Team FE absorb franchise/era quality; season FE absorb league-wide shifts. The
  crowd effect is identified off dose changing *within a team over time*, which in
  2020–21 was policy-driven. Same model for all three sports — no sport branching.
- **B — Classic 2×2 on/off DiD = back-pocket section.** Binarize the crowd
  (full vs reduced), compare the before/after change in home advantage. A smaller,
  deliberately-simple section that gives readers the intuitive picture before the
  dose-response, and sanity-checks the main model.
- **C — Synthetic control = skipped.** Built for one unit + one sharp
  intervention; a poor fit for ~100+ teams and a continuous staggered dose.
  Over-engineering here. Revisit only if a reviewer demands it.

**Outcome:** scoring margin is the modeled outcome (more information per game →
more power, and power is scarce: a fixed modest number of COVID-era games). Home
win % is reported alongside in every chart/table because it is the intuitive
number.

## 4. Confounders & how each is handled

**Fixed with controls (become panel columns):**
- *Team quality shifted in 2020–21* (COVID absences) — Elo control now; betting
  spread later (see TODO). This is the biggest threat.
- *Rest & travel* — compressed schedules, doubleheaders, back-to-backs →
  `home_rest_days`, `away_rest_days`, `away_travel_km`.
- *Weather* (outdoor MLB/NFL) — drives attendance and scoring → weather columns.

**Fixed only by flagging/exclusion (landmines):**
- *NBA 2020 bubble* — crowd, travel, and home park all vanished at once; cannot
  isolate the crowd. Flagged `is_bubble`, **excluded from the main model**.
- *Relocated/neutral "home" games* (e.g., 2020 Blue Jays in Buffalo) — home-park
  familiarity broken independent of crowd → `neutral_site`, `relocated_home`.

**Not confounders (they are the estimand or a bonus):**
- *Empty stadiums keep non-crowd home perks* (own bed, last change, bat last) —
  so we estimate the *crowd-attributable slice* of HFA, not all of it. Stated plainly.
- *Officiating bias* is a *mechanism* of the crowd effect, not a confounder.
  Optional future sub-study: decompose crowd→players vs crowd→refs
  (fouls/penalties home vs away). Deferred — needs sport-specific columns.

**Load-bearing identifying assumption (to pressure-test, not assume):** 2020–21
capacity caps are as-good-as-random with respect to game outcome, conditional on
controls.

## 5. The bubble as a decomposition anchor (deliberate use)

The bubble is excluded from the main model but **mined in a dedicated section**,
because contrasting three regimes decomposes home advantage:

| Regime | Crowd | Travel | Home park | Home advantage = |
|---|---|---|---|---|
| Normal seasons | yes | yes | yes | **Full** HFA |
| 2020–21 empty/partial | no/reduced | yes | yes | HFA **minus crowd** |
| Bubble | no | no | neutral | HFA **minus everything** |

- Normal − 2020–21-empty ≈ **crowd contribution**.
- 2020–21-empty − bubble ≈ **travel + home-park contribution**.
- **Placebo:** in bubble *seeding* games ("home" is a schedule label, not a better
  team) home advantage should be ~0; if so, strong confirmation HFA is environmental.

Caveats stated openly: small N (noisy estimates, wide CIs); the *playoff* bubble
is quality-confounded (higher seed = nominal home), so the clean placebo uses
*seeding* games only.

## 6. Unified panel schema (the keystone)

One row per game, **identical columns across MLB/NBA/NFL**. Sports fill what
applies and leave the rest null; the *shape* is identical. Sport-specific logic
lives only in `src/data/`; everything downstream is sport-blind.

| group | column | type | notes |
|---|---|---|---|
| keys | `sport` | str | `mlb`/`nba`/`nfl` — the parameter |
| keys | `game_id` | str | sport-native unique id |
| keys | `season` | int | season year |
| keys | `date` | date | game date |
| keys | `is_playoff` | bool | regular vs post (needed for placebo) |
| keys | `home_team`, `away_team` | str | standardized codes |
| outcome | `home_score`, `away_score` | int | |
| outcome | `home_margin` | int | derived: home − away |
| outcome | `home_win` | bool? | derived; nullable (NFL ties) |
| treatment | `attendance` | int | actual count |
| treatment | `capacity` | int | venue full capacity |
| treatment | `crowd_pct` | float | derived `attendance/capacity` — the dose |
| treatment | `covid_era` | bool | in 2020–21 restriction window |
| quality | `home_elo`, `away_elo` | float | pre-game rating, derived from panel |
| quality | `closing_spread` | float? | home-perspective betting line (nullable; future) |
| rest/travel | `home_rest_days`, `away_rest_days` | int | |
| rest/travel | `away_travel_km` | float? | away-team travel distance |
| venue | `venue` | str | park/arena |
| venue | `is_dome` | bool | indoor → weather null |
| venue | `temp_f`, `wind_mph`, `precip` | float? | outdoor only, nullable |
| flags | `neutral_site`, `relocated_home`, `is_bubble` | bool | exclude from main model |

Checked against every analysis (main dose-response, on/off DiD, descriptive HFA,
endogenous companion, bubble decomposition, seeding placebo) — all inputs present.

## 7. Deliverables

- Per-sport descriptive HFA quantification (charts, tables, numbers).
- Main causal dose-response (TWFE) per sport + cross-sport comparison table.
- Back-pocket on/off DiD section.
- Bubble decomposition + seeding-games placebo.
- Endogenous historical attendance dose-response (labeled descriptive).
- Quarto write-up → PDF + HTML.

## 8. Implementation phasing

Small, independently-runnable phases. Because "sport is a parameter," prove the
full vertical slice on one sport first (NFL pilot), then the other two conform.
Each phase ends with a check that fails loudly if broken.

1. **Schema contract + config** — panel columns as a code validator + fill
   `config/sports.yaml` with per-sport COVID windows. Done when the validator
   accepts a correct row and rejects a malformed one.
2. **Pilot loader (NFL) → panel** — one sport emitting the validated schema
   end-to-end. NFL chosen: cleanest source (`nfl_data_py`), exercises schema edge
   cases (ties → nullable `home_win`, dome/weather, neutral sites), richest
   staggered-cap dose. Done when real games load, pass the validator, write to
   `data/interim/`.
3. **Remaining two loaders (MLB, NBA)** — conform to the proven contract. Done
   when all three produce one identical-schema panel.
4. **Sport-blind features** — Elo, `crowd_pct`, rest, travel on the unified panel.
   Done when columns populate and Elo sanity-checks (good teams rate higher).
5. **Descriptive HFA** — home win% / margin by sport & season + first figures.
   Doubles as a data sanity gate before modeling.
6a. **Causal — TWFE dose-response** (the engine):
   `home_margin ~ crowd_pct + controls + team_FE + season_FE`. Done when the
   crowd coefficient + CIs are out for all three sports + cross-sport table.
6b. **Causal — back-pocket on/off DiD**: binarize the crowd (full vs reduced),
   classic 2×2 before/after. Smaller, intuitive section + sanity check on 6a.
7. **Bubble decomposition + placebo** — decomposition table + seeding-games placebo.
8. **Quarto write-up** — assembly → PDF + HTML.

## 9. TODO / future depth (not blocking)

- **Betting lines** as an alternative/companion to Elo for team strength — add
  once the core is done *if* free historical data can be sourced for all three
  sports. Run side-by-side as a sensitivity check.
- **Crowd→referee mechanism** sub-study (fouls/penalties home vs away) — needs
  sport-specific columns added to the schema.
- Pressure-test the identifying assumption (are caps correlated with anything
  outcome-relevant by region?).

## Implementation risks — REVIEW NEXT SESSION (2026-06-29 pre-commit review)

Ranked by likelihood of actually hurting. None change a design decision; they are
things to handle during implementation. Items 1–5 are the ones that matter.

1. **Treatment variable may not exist in the data — VERIFY FIRST (pre-Phase-1 spike).**
   The entire causal claim rests on `crowd_pct`, but sources record *actual
   attendance*, not the *policy cap*, and several reported 0/null attendance for
   COVID games or didn't populate the field. If `nfl_data_py` lacks per-game 2020
   attendance, the treatment variable is missing and Phase 2 stalls. **Action: a
   ~30-min spike — pull one 2020 NFL game, confirm attendance + capacity are
   actually present — before building the Phase 1 schema.**

2. **The dose-response curve really only lives in NFL.** Tracing a *curve* (does
   50% give half?) needs a team observed at several *intermediate* crowd levels.
   NFL 2020 has that (staggered caps). NBA/MLB went ~0% (2020) → ~100% (2021) =
   two points = on/off only, not a curve. Don't over-promise a dose-response for
   all three sports; NFL carries the curve, NBA/MLB degenerate to on/off. State
   this plainly in the results.

3. **Cross-sport comparison needs a common unit.** Margin scales differ wildly
   (NBA tens of pts, NFL ~7–14, MLB ~2–3 runs), so raw margin coefficients are not
   comparable across sports. Convert every effect to a common currency — almost
   certainly **Δ home-win-probability** — for the cross-sport table. Unspecified
   in §3; decide in Phase 6a.

4. **Elo can absorb the home advantage we're measuring.** Elo is built from the
   same results we model; if the update treats home/away wins symmetrically, the
   rating soaks up home advantage and *attenuates* the crowd coefficient toward 0.
   Build Elo as a *pure strength* prior (explicit home-field term in the update,
   or otherwise neutralized), not naively. Surfaces in Phase 4 / 6a.

5. **The causal half may be underpowered — set expectations.** After excluding
   bubble/neutral games, the clean treated set is a few hundred games per sport;
   with margin noise, per-sport crowd CIs may be wide ("suggestive, not
   significant"). The descriptive half always delivers; the causal half may come
   back inconclusive per-sport (pooling across sports helps). Wide CIs are a
   finding, not a failure.

### Smaller gotchas (not blocking)

- **Travel distance needs venue coordinates** — not in any source; Phase 4 needs
  a small static venue→lat/long lookup file.
- **Rest-days undefined for each team's first game of the season** — needs a
  null/sentinel rule.
- **NFL season spans into Jan/Feb** — align the `season` int with the `covid_era`
  date-window logic or January playoff games get mis-tagged.
- **Dependency pin friction** — `numpy<2` / `pandas<2.3` (pinned for the sport
  libs) may conflict with recent `linearmodels`/`statsmodels`; confirm the env
  resolves during Phase 1 setup before building on it.
- **`closing_spread` column** is in the schema but unpopulated until the betting-
  lines TODO; the Phase 1 validator must allow it null/absent.

### Still to confirm at build time

- Per-game attendance + capacity coverage for all three sports across the full
  window (MLB via Retrosheet/pybaseball; NBA via Basketball-Ref; NFL via
  PFR/nflverse). See risk #1.
- Exact COVID restriction window boundaries per sport/season.
