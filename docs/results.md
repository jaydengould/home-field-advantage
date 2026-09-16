# Results and findings

**⚠️ `results/tables/*.csv` is authoritative over this file.** Any number the paper cites comes
from a CSV or a `.qmd` chunk, never from prose. Where the two disagree, the prose is what's stale.
This file is a narrative index of *what was found and what it means*.

## Headline — crowd effect on home win probability (pooled LPM, the cross-sport unit)

| | nfl | nba | nhl | mlb |
|---|---|---|---|---|
| Δ win prob | **+0.044** | **+0.016** | **+0.007** | **−0.021** |

Every per-sport CI crosses zero. NFL is the only appreciable point estimate (+4.4pp, p=.23) —
but see A1 below before writing that sentence standalone.

## Descriptive HFA (Phase 5) — the data-sanity gate

`results/tables/descriptive_hfa.csv`, `results/figures/hfa_by_season.png`. Clean regular-season
home games only (playoffs excluded — playoff home teams are the better seed, so HFA blends with
quality asymmetry, and samples are tiny). The 2020 NBA/NHL bubble playoffs are neutral-site; the
2021 NBA/NHL playoffs were ordinary home games (mean dose .73/.50). SEs are naive
iid guards against over-reading a noisy season, **not** causal CIs.

| | pooled full-crowd win% | margin | gate |
|---|---|---|---|
| nfl | .552 | 1.75 | PASS (2020 dips) |
| mlb | .528 | **0.04** | CHECK (no dip) |
| nba | .570 | 2.26 | PASS (2021 dips) |
| nhl | .538 | 0.254 | CHECK (no dip) |

**MLB scoring-margin HFA is noise-dominated.** +0.04 (SE .05) pooled, per-season SE ~.09, 2019
even negative. The design's "margin = more power" premise **fails for baseball** — report win%
as MLB's primary descriptive signal. The COVID *dose* is still strong in MLB; it's the *outcome*
that lacks power.

The gate is data-driven off `covid_era`, never a hardcoded 2020 — treated seasons differ per
sport, and a hardcoded check gave NBA a false PASS off a coincidental gap.

## Causal estimates — 6a (adjusted) vs 6b (raw before/after)

`twfe_{sport}.csv`, `did_{sport}.csv`, `results/figures/{twfe_crowd_effect,did_hfa_shrink}.png`.

| | 6a margin | 6a win% | 6b margin | 6b win% |
|---|---|---|---|---|
| nfl | **+1.71** [−0.54, 3.96] | +0.044 | +1.62 [−0.73, 3.96] | +0.048 |
| nba | **+1.07** [−0.68, 2.83] | +0.016 | +1.34 [−0.72, 3.39] | +0.024 |
| nhl | **+0.003** [−0.23, +0.24] | +0.007 | −0.008 [−0.23, +0.21] | +0.006 |
| mlb | −0.18 | −0.021 | −0.11 | −0.013 |

The two estimators cohere within ~10–25%; 6b running slightly larger is expected (raw vs
Elo/rest/travel-adjusted). They share the same confound — 6b is not cleaner identification.

**Three honesty corrections that survived review:**
1. **There is NO within-season dose curve for ANY sport.** Within-2020 NFL dose↔margin
   correlation ≈ −0.03. All four sports are effectively **on/off**; +1.71 is a level shift, not
   a curve. That absence is *why* two-way FE degenerates.
2. **`closing_spread` is a POST-TREATMENT bad control.** The spread is set knowing the stadium
   is empty and prices in reduced HFA, so the 1.71 → 0.81 attenuation is mechanical absorption
   of the crowd effect, not evidence of fragility.
3. The identifying assumption (see `docs/design-decisions.md`) admits no in-model separation.

## NHL — centred near zero, underpowered, and the strongest treatment

NHL's win% SE is .0234 → MDE ≈ 6.6pp, and its CI [−0.039, +0.053] **contains both** NFL's +0.044
and NBA's +0.016. It cannot distinguish zero from an NFL-sized effect.

- **NHL HFA drifts downward across the window independent of COVID** — win% .563 → .536 → .531 →
  **.532 (treated)** → .537 → .523. ⚠️ **Not monotonic** (2 of 5 steps are up, and 2018→2019 alone
  is larger than the rest combined). The verified claim: a linear trend through the five control
  seasons predicts 2021 win% .5348 vs actual **.5323 — a gap of 0.15 SE.** The empty-arena season
  sits *on* the trend, not below it.
- **The `season_trend` is not absorbing the treatment** (`trend_sensitivity.csv`): no trend at all
  gives margin +0.0243 (se .124) / win% +0.0119; linear (shipped) +0.0030 / +0.0067; quadratic
  +0.0256 / +0.0027. Removing the trend moves win% by a fifth of an SE.
- **Travel diagnostic** (pre-committed, reported either way): `corr(crowd_pct, away_travel_km |
  2021) = −0.138`. Dropping the control moves the coef +0.0053 (margin) / +0.0029 (win) with
  `n_obs` identical at 6942. Travel is not masking an effect.
- **Undisclosed specification sensitivity — state it WITH its rebuttal.** NHL is where the
  "season FE are collinear with treatment" argument is weakest: R² of
  `crowd_pct ~ C(season)+C(home_team)` is nfl .980, nba .926, **nhl .887**, mlb .637. Under full
  season FE, NHL win% is **+0.084 (se .053)** — the largest point estimate in the study. The
  shipped spec is still right: within-*normal*-season crowd variation is demand-driven (good teams
  draw crowds *and* win). The decomposition confirms it — within-2022 dose is **+0.056** while
  within-2021 (the exogenous slice) is **−0.28**.

## Within-season dose — wrong-signed everywhere, and that IS the lesson

`within_season_dose.csv`. NHL 2021, team FE, same controls:

| outcome | coef | 95% CI | p | n |
|---|---|---|---|---|
| `home_margin` | **−1.414** (se .858) | [−3.099, +0.271] | .100 | 849 |
| `home_win` | **−0.281** (se .183) | [−0.639, +0.078] | .125 | 849 |

Largest within-season magnitudes anywhere in the study, pointing the wrong way. **Raw means go
the other way** (NHL empty +0.149 vs with-fans +0.446; MLB raw +0.003 vs coef −0.435). **The
raw-vs-team-FE sign opposition reproduces in BOTH NHL and MLB** — that is the endogeneity lesson
reproducing across sports, not two anomalies.

Two caveats always travel with it: (1) within-team fan access in 2021 is confounded with calendar
time (reopening was progressive, so "more fans" ≈ "later in season"); (2) the fitted range is
0–0.40, so a per-unit `crowd_pct` coefficient **extrapolates 2.5× beyond support.** Report this
as *the within-season design being uninformative and endogenous*, which is why the headline is
identified between-season.

## Power — the real finding

`meta_cross_sport.csv` (`mde_80 = 2.8·SE`), denominators from `descriptive_hfa.csv`.

| MDE ÷ total HFA (per unit `crowd_pct`) | margin | win% |
|---|---|---|
| nfl | 1.83× | 1.99× |
| mlb | 10.15× | 1.53× |
| nba | 1.11× | **1.02×** |
| nhl | 1.33× | 1.71× |

**A crowd effect accounting for 100% of home-field advantage would go undetected at 80% power in
all eight cells; the smallest ratio (NBA win%) is 1.02×.**

⚠️ **This is not robust to rescaling, and saying so is mandatory.** The coefficient is per unit
`crowd_pct` and no sport's data spans a full unit. Control-season mean dose is nfl **.97** ·
mlb **.65** · nba **.92** · nhl **.92** (treated: .064 / .320 / .073 / .062). Rescaling each MDE
to its own sport's realised contrast:

| rescaled MDE ÷ HFA | margin | win% |
|---|---|---|
| nfl | 1.78× | 1.94× |
| mlb | 6.64× | **1.00×** |
| nba | **1.02×** | **0.94×** |
| nhl | 1.22× | 1.58× |

**Three cells land at ≈1.0 or below.** A third consequence: **MLB's headline coefficient
extrapolates ~1.5× beyond the dose MLB typically attains** (it reads a 0→1 contrast off an
empty→typical-full contrast of 0→.65) — a support-range caveat on a *headline*, not a sensitivity.

## Pooling does not buy what earlier phases claimed

`meta_cross_sport.csv`:

| | FE (inverse-variance) | RE (DerSimonian–Laird) | τ² | I² |
|---|---|---|---|---|
| 3 sports | −0.0046 (SE .0125) | +0.0028 (SE .0185) | .000442 | 41.9% |
| 4 sports | −0.0021 (SE .0110) | +0.0003 (SE .0126) | .000116 | 17.2% |

1. **The four estimates share a BIAS, not just independent noise** — each is *crowd effect + that
   league's 2020–21 non-crowd home-specific shift*. Inverse-variance pooling shrinks *sampling*
   error as 1/√k and does nothing to a bias common across leagues (same pandemic, same empty
   buildings, same schedule compression). **The pooled SE is a lower bound on real uncertainty.**
2. **The heterogeneity test has no power at k=4** (needs Q > 7.81; observed 3.62), and I² fell
   mechanically because NHL landed near the pooled mean.
3. **The gain is specification-dependent**: −11.8% CI width FE-vs-FE, −31.7% RE-vs-RE. The FE
   point estimate "moving" −0.0046 → −0.0021 is noise theatre; both are far smaller than their SE.

## Zero-attendance correction (2026-09-15) — data fix, estimates barely move

`zero_attendance_sensitivity.csv`; archived pre-fix tables in `results/tables/pre_zero_fix/`.
ESPN reports `attendance == 0` for 119 games outside any restriction window (nfl 1 · mlb 103 ·
nba 8 · nhl 7; 96 of the MLB games have another same-home-team game within 12 h). The same fix
removed 23 duplicated MLB rows (suspended games re-listed on resumption day, plus one game under
two ESPN ids): the panel is 30,146 games, not 30,169, and original tables are in
`results/tables/pre_dedup/`. Deduplication alone moves MLB 6a ≤ 0.03 SE. Their `crowd_pct` is now null, so 6a drops
them. 6b, descriptive HFA, season effects, RI and the noise floor are unchanged. The largest pooled
6a move is MLB margin −0.145 → −0.180 (0.22 SE); MLB win −0.019 → −0.021. The same three
cells exclude a full-HFA effect before and after (MLB win, NBA win, NHL margin), and all eight
per-unit MDE ratios stay > 1. Residual: 37 model-sample treated-season zeros fall after the home
team had already hosted fans (nfl 17 · nba 17 · nhl 3). They stay at 0 by the pre-committed rule and
are disclosed in Limitations.

## Pre-write-up audit (2026-08-17) — three findings, all additions

None re-specifies the frozen 6a model.

**A2 — MLB is not running the same experiment as the other three.** `dose_overlap.csv`. Share of
CONTROL-season games inside the treated 5–95% dose range: **nfl .00% · nba .22% · nhl .42% ·
MLB 74.6%.** For three sports the treatment is a near-disjoint empty-vs-full contrast; for MLB
three-quarters of *normal* games sit inside the treated range, so its coefficient rides on
ordinary demand variation. **The contamination is entirely 2021** (MLB 2020 overlaps 0.00%,
level with NFL; 2021 overlaps 78.4% at mean dose .436). ⚠️ **The trade must travel with it:**
2020 buys dose cleanliness and pays in confounding — ghost runner, universal DH, 7-inning
doubleheaders, 60-game regional schedule. No MLB definition is clean on both; report all three
rows, don't promote 2020-only. **Root cause worth a limitations paragraph:** the design specifies
the treatment as *policy capacity caps*, the code uses *realised attendance ÷ empirical capacity*.
Those coincide where caps bound (nfl/nba/nhl) and diverge where they don't (mlb).

**A1 — the NFL headline rests on one control season.** `leave_one_season_out.csv`, frozen spec,
each *untreated* season dropped once:

| nfl | −2018 | −2019 | −2021 | −2022 | −2023 | base |
|---|---|---|---|---|---|---|
| margin | **+0.674** | +2.359 | +1.799 | +1.730 | +1.619 | +1.705 |
| win% | **+0.0072** | +0.0643 | +0.0564 | +0.0407 | +0.0388 | +0.0441 |

Dropping 2018 moves win% by −1.00 SE; no other season moves either outcome by more than 0.57 SE.
mlb/nhl stable (largest 0.65 SE, MLB −2023 win%); nba's largest is −0.68 SE. Read with both halves: **partly genuine fragility,
partly the mechanical fact that dropping an endpoint of a 6-season panel tilts the linear trend.**
It removes the basis for calling NFL "suggestive evidence"; it does not make the result fake.

**B1 — the treatment is season-level, so inference on 1,500–13,000 games is wrong.**
`season_effects.csv`, `noise_floor.csv`. Effective independent treatment draws = **6 seasons**.
Clustering by season is not the fix (6 clusters ≪ the ~40 cluster-robust variance needs; the
two-way attempt returns SEs 0.14–0.76× *smaller* — the estimator breaking, not a correction).

- **Randomization inference:** each season wears the treatment dummy in turn. **No RI p-value
  below .333**, and the floor `1/(1+n_placebo)` is **.167** (mlb .200). *No result this design can
  produce can reach p<.05 under RI.* **NFL 2018 deviates +3.697 margin vs treated 2020's −1.802 —
  ordinary season-to-season noise in home advantage exceeds the COVID signal.** Consequence:
  report intervals and magnitudes, not p-values against a bar they cannot clear.
- **Noise floor.** Two components bind and neither shrinks with more control seasons: the treated
  season's own sampling noise (2020 happened once) and `sd_true`, genuine between-season variation
  in HFA. **NFL's `sd_true` is 1.73 margin points — larger than its entire 1.75 HFA.**
  `ratio_floor = 2.8·hypot(both) ÷ HFA` is ≥ 1.0 in 7 of 8 cells (nfl 3.23×/3.77× · mlb
  6.12×/**0.88×** · nba 1.29×/1.29× · nhl 1.13×/1.46×). **Would more seasons buy significance? No**
  — and it likely worsens RI (more seasons lowers the 1/k floor but enlarges the reference
  distribution 2020 must beat). **Recommendation on record: do not extend the panel.**
- ⚠️ `floor_over_naive` is 1.00–2.17: admitting season-level shocks makes honest inference
  **worse** than the shipped clustered SE. `mde_floor ≥ mde_naive` always, by construction.
- `sd_true_censored` (mlb both, nhl both) marks cells where observed spread fell below average
  sampling noise and the decomposition clamped at 0. Read as "undetectably small", not "zero".

Checked and clean, no findings: Elo has no lookahead; travel and rest logic sound; no estimator bugs.

## MLB treated-season split — inconclusive, not confirmatory

`mlb_treated_split.csv`. Both treated years come out slightly *positive* on the year-indicator
level (2020 +0.0674 se .174 · 2021 +0.1204 se .115 margin; +0.0157 · +0.0101 win%, all p > .29 — the
smallest is .294, n 12871). The "is it a 2020 rule artifact?" check **does not confirm the rule-artifact story**,
and it could not separate rule changes from crowd effects in any case. ⚠️ **Sign convention here
is NOT 6b's** — this table reports the raw treated-year level unnegated, so positive means the
implied crowd effect is **negative**.

## The bubble is not a disentangler

- NBA seeding placebo: n=88, margin +1.65 (SE 1.35) → CI ≈ [−1.0, +4.3], containing both 0 and
  full normal HFA (2.26). **A test that cannot fail.**
- The decomposition's second row is wrong-signed (`empty − bubble = −0.73`).
- The bubble sits *inside* the pandemic window and swaps one bundled treatment for another;
  bubble "home" teams kept court branding, uniform choice and bench conventions, so its null
  isn't cleanly zero. TOR/EDM played NHL bubble games in their **own arenas**, with the higher
  seed designated home team and customised in-arena presentation.
- **NHL's bubble does not help** — all 130 games are playoffs, therefore quality-confounded, so
  they feed neither the placebo (needs `is_playoff==False`) nor a regular-season decomposition.

## The honest conclusion

> In all eight sport × outcome cells, the effect this design could detect at 80% power is larger
> than the entire home-field advantage of that sport, the smallest (NBA win probability) by 2%.
> (That ratio is **per unit `crowd_pct`**; rescaled to each sport's realised contrast, three cells
> fall to ≈1.0 or below. Say which scaling you are quoting.) Four replications, each individually
> underpowered, all centred near zero, none able to exclude a crowd effect of the size NFL's point
> estimate implies. In the one sport where a published estimate converts to our units (**NBA**),
> our interval contains it. A shared, unmeasured 2020–21 home-specific confound remains, and
> **pooling does not reduce it.** The claim this study can defend is that it cannot distinguish
> zero from a crowd effect accounting for all of HFA; it is *not* evidence that crowds don't matter.

**This study was NOT pre-registered.** The internal pre-commitment discipline is not a public
timestamp. Complete disclosure is what substitutes for it — say so plainly.
