# Phase 6a — Causal TWFE dose-response — design

**Date:** 2026-07-20
**Status:** Approved design (brainstormed with the user 2026-07-20).
**Phase:** 6a of the home-field-advantage study (the causal engine).
**Depends on:** `data/processed/{nfl,mlb,nba}.parquet` (Phase 4 feature-complete panels),
`src/schema.py`, `src/viz/descriptive.py` (pattern to mirror).

## Goal

Estimate the **crowd-attributable slice of home-field advantage** per sport with a
two-way fixed-effects (TWFE) panel, identified off the COVID 2020–21 capacity caps.
This is the study's causal engine; Phase 6b (on/off DiD) and Phase 7 (bubble
decomposition) sit around it.

Headline sentence the phase must let the paper write: *"A full crowd is worth ~X points
of scoring margin / ~Y percentage points of home-win probability, per sport."*

## Model

One sport-blind specification, estimated **per sport separately** (the design's rule:
sport is a parameter; each sport analyzed alone, then compared).

```
outcome ~ crowd_pct + elo_diff + rest_diff + away_travel_km + season_trend
          + EntityEffects(home_team)
```

- **Engine:** `linearmodels.PanelOLS` with `entity_effects=True` (home_team) and
  `time_effects=False`. Panel index = `(home_team, season)`.
- **⚠️ Correction adopted at build time (2026-07-20) — team FE ONLY, not two-way FE.**
  The spec originally called for full season fixed effects (`TimeEffects(season)`). The
  first real-data run showed **all 12 crowd coefficients came back negative** (NFL margin
  −8.75), the opposite sign to the Phase 5 descriptive dip. Root cause: the COVID crowd
  shock is *~a pure season-level treatment* — `crowd_pct` is ~0.97 every normal season and
  ~0.07 in the treated one — so full season dummies are **near-collinear with `crowd_pct`**
  and absorb the between-season contrast that *is* the natural experiment, leaving the coef
  identified off tiny within-season residual noise (→ meaningless large negative). Diagnostic
  (NFL margin): team+season FE −8.75 · team FE only **+1.92** · no FE +2.19 · season-level
  corr(crowd,margin) +0.63. **Fix:** team (entity) FE only, plus a **linear `season_trend`**
  (`season − min(season)`) that nets out secular league drift *without* absorbing the sharp
  COVID contrast. `season_trend` is a nuisance control (not reported in the `coef_*` output).
  This is the honest identification: a time-clustered treatment is a within-team before/
  during/after comparison, which full time FE would erase. It also means **Phase 6b's 2×2
  on/off DiD is the natural co-primary estimator, not a back-pocket** — recorded for 6b/8.
- **Estimated for two outcomes, identical RHS:**
  - `home_margin` — the power narrative (primary for NFL & NBA).
  - `home_win` as a **linear probability model** (0/1 outcome, same PanelOLS engine). Its
    `crowd_pct` coefficient *is* Δ home-win-probability — the cross-sport common unit, the
    intuitive number, and MLB's real HFA signal (Phase 5: MLB margin is noise-dominated).
- **No logit.** Two-way FE + logit hits the incidental-parameters problem and breaks the
  one-estimator rule. LPM with two-way FE is the standard, honest choice. Add logit only if
  a reviewer later demands curvature at the 0/1 boundary. (`ponytail:` LPM reuses PanelOLS —
  no second machinery.)

### Controls (sport-blind — only columns populated for all three sports)

| control | definition | rationale |
|---|---|---|
| `crowd_pct` | the treatment dose (0–1) | the estimand |
| `elo_diff` | `home_elo − away_elo` | team-quality gap in one HFA-free term (Phase 4 Elo stores pre-game, HFA only inside the win-prob expectation, so `elo_diff` is quality, not HFA) |
| `rest_diff` | `home_rest_days − away_rest_days` | schedule advantage in one term |
| `away_travel_km` | away-team travel distance | home travel ≈ 0, so this is the whole travel signal |

**Excluded as core controls:** `closing_spread` and weather (`temp_f`/`wind_mph`/`precip`)
are NFL-only, so including them would break the "written once" sport-blind model (drop
MLB/NBA rows or force per-sport branching). They become a **separate NFL-only sensitivity
check** (§ NFL sensitivity), not part of the main spec.

### Fixed effects

- **Entity FE = `home_team`** — absorbs franchise/venue/era level. Away-team quality enters
  via `elo_diff`, not away-team FE (keeps the model parsimonious; away FE would add ~30
  parameters for signal Elo already carries).
- **NO time FE.** Full season FE are near-collinear with the time-clustered crowd shock and
  invert the estimate (see ⚠️ correction above). A **linear `season_trend`** replaces them:
  it removes gradual league drift but preserves the between-season COVID contrast that
  identifies `crowd_pct`.

### Standard errors

- **Clustered by `home_team`** (`cov_type="clustered"`, `cluster_entity=True`) — robust to
  within-team serial correlation across the panel.
- **Caveat carried to results:** 30–32 clusters is on the low side for cluster-robust
  inference. Acceptable, but if a `crowd_pct` coefficient lands near the significance edge,
  re-check it with a wild-cluster bootstrap before making a claim. Not built by default.

## Sample

Two samples, both through the identical spec:

1. **Headline = pooled** — all loaded seasons (2018–2023). Maximum power. `crowd_pct` is
   still identified predominantly off the COVID swing (normal-season `crowd_pct` barely
   moves, ~0.95–0.98, so it contributes little identifying variation once FE are in).
2. **Robustness = restricted** — treated seasons + one adjacent season each side, dropping
   the endogenous normal-season within-year variation. Concretely, the kept season set is
   `treated_seasons ∪ {min(treated)−1, max(treated)+1}` (per-sport, from
   `config/sports.yaml`): NFL `{2019, 2020, 2021}`, MLB `{2019, 2020, 2021, 2022}`, NBA
   `{2020, 2021, 2022}` — the pre-COVID baseline and post-COVID reversion anchor bracketing
   the treated window. If restricted ≈ pooled,
   that **demonstrates** endogenous normal-season variation isn't driving the estimate — a
   stronger claim than asserting it. Divergence is itself a finding.

**Both samples exclude** (rows dropped before fitting):
- `neutral_site == True`
- `relocated_home == True`
- `is_bubble == True`
- `is_playoff == True` (regular season only — consistent with Phase 5 descriptive; the cap
  variation we identify off is a regular-season phenomenon; COVID-era playoffs are largely
  the neutral/bubble games already dropped).

Rows with a null in any model column (e.g. first-game-of-season `rest_days` → NA, or a
neutral/relocated-game `away_travel_km` → NaN) are dropped by the estimator's listwise
deletion; the drop count is reported so silent sample loss is visible.

## Sport-specific identification honesty (stated plainly in results)

With team FE only (+ linear trend), `crowd_pct` is identified off the **within-team before/
during/after crowd regime change** (the natural experiment) — the between-season contrast
full season FE would have erased.

**All three sports are effectively on/off — there is NO within-season dose curve, not even
for NFL** (corrected after final review, 2026-07-20). The Phase-2 spike suggested NFL's 2020
staggered caps might trace a dose-response curve, but the data does not bear it out:
within-2020 NFL cross-team dose↔margin correlation is ≈ **−0.03** (essentially zero). The
+1.71 estimate is entirely a before/during/after *level shift*, not a within-season
dose-response — which is exactly why the two-way FE degenerates (the within-season dose
signal it would need is near-absent). MLB/NBA are likewise on/off (empty → 2021 partial →
full). **Do not claim NFL delivers a dose curve** in the write-up (spec Risk #2, now
sharpened: the curve doesn't exist for any sport at this N).

**Load-bearing identifying assumption (state plainly, do not soft-pedal):** because the crowd
shock hit every team at once, the estimate = crowd effect **+ any other 2020–21 league-wide
home-margin shift** (rule changes, schedule compression, empty-stadium effects on players/
officials). The linear `season_trend` removes only *smooth* drift, NOT the discrete pandemic
shock; a treated-season dummy cannot be added alongside `crowd_pct` (collinear), so there is
**no in-model separation** of crowd from other coincident pandemic changes. This is inherent
to a treatment that hit everyone simultaneously. **Phase 7's bubble decomposition is the
disentangler** (normal − empty ≈ crowd; empty − bubble ≈ travel + home-park).

**Corrected-run results (2026-07-20, team FE + linear trend):** NFL margin **+1.71**
[−0.53, 3.95] (pooled), win% +0.046; NBA margin **+1.06** [−0.70, 2.81], win% +0.015; MLB
margin −0.14 (noise), win% −0.019. Signs match the descriptive dip; per-sport CIs are wide
and cross zero (underpowered — Risk #5, a finding not a failure).

**NFL `closing_spread` sensitivity — read as a BAD CONTROL, not fragility.** Adding the
closing spread pulls the crowd coef 1.71 → 0.81, but the spread is **post-treatment**: it is
set pre-game *knowing* the stadium is empty and already prices in the reduced HFA, so the
attenuation is mechanical absorption of the crowd effect itself, not evidence Elo misses
quality. The write-up must present this as a bad-control caveat, NOT as "the crowd estimate
is fragile."

## Outputs

New module `src/models/twfe.py`, mirroring the `src/viz/descriptive.py` pattern
(pure/tested core function + `main()` that writes artifacts):

- **`fit(panel, outcome, sample) -> dict`** — pure function (no disk/net). Filters
  exclusions, builds `elo_diff`/`rest_diff`, fits PanelOLS, returns `{coef, se, ci_low,
  ci_high, n_obs, n_entities, ...}` for `crowd_pct` (and the other coefficients for the full
  table). `outcome ∈ {"home_margin", "home_win"}`, `sample ∈ {"pooled", "restricted"}`.
- **`main()`** — for each sport, runs the 2 outcomes × 2 samples, writes:
  - `results/tables/twfe_<sport>.csv` — one row per (outcome, sample): `crowd_pct` coef,
    cluster-robust SE, 95% CI, N obs, N entities, plus the control coefficients.
  - `results/tables/twfe_cross_sport.csv` — the LPM (`home_win`) `crowd_pct` Δwin-prob
    coefficient + CI per sport, side by side (the cross-sport comparison; margin coefficients
    are NOT cross-sport comparable so they do not go here).
  - A coefficient / forest-plot figure at `results/figures/twfe_crowd_effect.png` — the
    `crowd_pct` effect with CIs, per sport × outcome, pooled vs restricted.

### NFL sensitivity check (small, NFL-only)

Re-fit the NFL `home_margin` pooled model adding `closing_spread` (and optionally weather)
as extra controls; report whether the `crowd_pct` coefficient is stable. One extra row/panel,
NFL only. Confirms the Elo-based quality control isn't hiding a market-information gap.

## Testing

Mirror Phase 5's approach — `tests/test_twfe.py`, pure-function tests on synthetic panels:

1. **Planted-effect recovery:** build a synthetic panel where `home_margin = β·crowd_pct +
   team_effect + season_effect + noise` with a known `β`; assert `fit()` recovers it within
   tolerance. The core correctness gate.
2. **Exclusion filtering:** rows flagged `is_bubble`/`neutral_site`/`relocated_home`/
   `is_playoff` are dropped before fitting (assert `n_obs`).
3. **Restricted-sample selection:** `sample="restricted"` keeps only treated + adjacent
   seasons (assert the season set).
4. **LPM outcome:** `fit(..., outcome="home_win")` runs and returns a coefficient on a 0/1
   outcome.

No new heavy fixtures; synthetic DataFrames built inline, as in `test_descriptive.py`.

## Non-goals (parked, recorded so they aren't lost)

- **Descriptive playoff-HFA subsection** — "is HFA bigger in the playoffs?" Cheap (reuse
  `descriptive.summarize()` with `is_playoff==True`), interesting, but blended with seeding
  quality → a descriptive number with an asterisk. **Build in Phase 8, not 6a.**
- **Playoffs inside the causal model** — revisit only if it demonstrably strengthens the
  paper; default is regular-season only.
- **Causal crowd effect in playoffs** — dropped. Confounded (playoff home = better seed,
  only partly netted by Elo, no exogenous cap variation) and underpowered (COVID-era playoff
  games with crowd dose variation are a tiny, mostly-neutral set already excluded). Phase 7's
  bubble seeding-games placebo is the better-designed neutral-home test.
- **Wild-cluster bootstrap** — only if a coefficient lands on the significance edge.
- **Logit / nonlinear win model** — only if a reviewer demands 0/1-boundary curvature.

## Done when

- `src/models/twfe.py` + `tests/test_twfe.py` written; planted-effect test passes.
- `results/tables/twfe_<sport>.csv` (×3), `results/tables/twfe_cross_sport.csv`, and
  `results/figures/twfe_crowd_effect.png` generated from real processed panels.
- The `crowd_pct` coefficient + cluster-robust CIs are out for all three sports, both
  outcomes, both samples, and the cross-sport Δwin-prob table is populated.
- Sport-specific identification caveat (NFL curve vs MLB/NBA on/off) noted for the write-up.
