# Results and findings

**⚠️ `results/tables/*.csv` is authoritative over this file.** Any number the paper cites comes
from a CSV or a `.qmd` chunk, never from prose. Where the two disagree, the prose is what's stale.
This file is a narrative index of *what was found and what it means*.

## Headline — crowd effect on home win probability (pooled LPM, the cross-sport unit)

| | nfl | nba | nhl | mlb |
|---|---|---|---|---|
| Δ win prob | **+0.050** | **+0.006** | **+0.011** | **−0.021** |

Every per-sport CI crosses zero. NFL is the only appreciable point estimate (+5.0pp, p=.19) —
but see A1 below before writing that sentence standalone. (Post reopening-zeros fix, 2026-09-16;
was +0.044 / +0.016 / +0.007 / −0.021 — see "Reopening-zeros correction" below.)

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
| nfl | **+1.93** [−0.36, 4.21] | +0.050 | +1.62 [−0.73, 3.96] | +0.048 |
| nba | **+0.91** [−0.98, 2.80] | +0.006 | +1.34 [−0.72, 3.39] | +0.024 |
| nhl | **+0.04** [−0.22, +0.30] | +0.011 | −0.008 [−0.23, +0.21] | +0.006 |
| mlb | −0.18 | −0.021 | −0.11 | −0.013 |

(6a post reopening-zeros fix, 2026-09-16; 6b is unaffected — it never reads `crowd_pct`.)

**Units: 6a is per unit of `crowd_pct`; 6b is a level (HFA_full − HFA_reduced).** Compare 6b with
6a × dose gap (`dose_overlap.csv` all_treated control_mean − treated_mean: nfl 0.907 · mlb 0.334 ·
nba 0.843 · nhl 0.852). (Corrected 2026-09-21, B.S O-1: earlier text compared them unscaled, giving
"4.1%–268.3%" and "6b smaller on both NFL cells, the direction expected from raw vs adjusted" — false.)
They agree in sign in 7 of 8 cells (NHL margin disagrees, +0.039 per unit vs −0.008, both
indistinguishable from zero). |6b| / |6a × gap| − 1 on the other seven: nfl margin −7.6%, win +5.7%;
nhl win −34.7%; nba margin +74.8%, win +336.9%; mlb margin +90.2%, win +84.1% (range 5.7%–337%).
Close only in the NFL. Agreement is not corroboration of identification: both read the same
between-season contrast and carry the same confound; in the NFL 6b matching scaled 6a is consistent
with the adjustments (controls, team FE, trend) doing little net work there. In the NBA and MLB the two are not interchangeable.

**Three honesty corrections that survived review:**
1. **There is NO within-season dose curve for ANY sport.** Within-2020 NFL dose↔margin
   correlation ≈ −0.02 (post reopening-zeros fix, 2026-09-16; was ≈ −0.03). All four sports are
   effectively **on/off**; +1.93 is a level shift, not a curve. That absence is *why* two-way FE
   degenerates.
2. **`closing_spread` is a POST-TREATMENT bad control.** The spread is set knowing the stadium
   is empty and prices in reduced HFA, so the +1.93 → +1.06 margin attenuation (win% +0.050 →
   +0.021) is mechanical absorption of the crowd effect, not evidence of fragility.
3. The identifying assumption (see `docs/design-decisions.md`) admits no in-model separation.

## NHL — centred near zero, underpowered, and the strongest treatment

NHL's win% SE is .0253 → MDE ≈ 7.1pp, and its CI [−0.039, +0.060] **contains both** NFL's +0.050
and NBA's +0.006. It cannot distinguish zero from an NFL-sized effect.

- **NHL HFA drifts downward across the window independent of COVID** — win% .563 → .536 → .531 →
  **.532 (treated)** → .537 → .523. ⚠️ **Not monotonic** (2 of 5 steps are up, and 2018→2019 alone
  is larger than the rest combined). The verified claim: a linear trend through the five control
  seasons predicts 2021 win% .5348 vs actual **.5323 — a gap of 0.15 SE.** The empty-arena season
  sits *on* the trend, not below it.
- **The `season_trend` is not absorbing the treatment** (`trend_sensitivity.csv`): no trend at all
  gives margin +0.061 (se .134) / win% +0.016; linear (shipped) +0.039 (se .131) / +0.011;
  quadratic +0.062 (se .144) / +0.007. Removing the trend moves win% by about a fifth of an SE.
- **Travel diagnostic** (pre-committed, reported either way): `corr(crowd_pct, away_travel_km |
  2021) = −0.143`. Dropping the control moves the coef +0.0095 (margin, +0.039→+0.049) / +0.0039
  (win) with `n_obs` identical at 6854. Travel is not masking an effect.
- **Undisclosed specification sensitivity — state it WITH its rebuttal.** NHL is where the
  "season FE are collinear with treatment" argument is weakest: R² of
  `crowd_pct ~ C(season)+C(home_team)` is nfl .979, nba .921, **nhl .877**, mlb .637. Under full
  season FE, NHL win% is **+0.084 (se .054)** — the largest positive win% estimate in the season-FE
  sensitivity table (p=.12, CI still spans zero [−0.022, +0.190]). The shipped spec is still
  right: within-*normal*-season crowd variation is demand-driven (good teams draw crowds *and*
  win). The decomposition confirms it — within-2022 dose is **+0.056** while within-2021 (the
  policy-driven slice, confounded with calendar time) is **−0.29**.
  (R², full-FE and within-2021 numbers post reopening-zeros fix, 2026-09-16; within-2022 is
  unaffected — 2022 is not a treated season.)

## Within-season dose — wrong-signed everywhere, and that IS the lesson

`within_season_dose.csv`. NHL 2021, team FE, same controls:

| outcome | coef | 95% CI | p | n |
|---|---|---|---|---|
| `home_margin` | **−1.645** (se .794) | [−3.204, −0.086] | .039 | 761 |
| `home_win` | **−0.289** (se .181) | [−0.645, +0.067] | .111 | 761 |

(Post reopening-zeros fix, 2026-09-16 — n fell from 849 as 88 NHL 2021 games lost their dose.
**The margin CI now excludes zero, wrong-signed** — it did not before (was [−3.099, +0.271],
p=.100). Resolved in B.G5 fix round 2 (2026-09-18, "M5"): @sec-nhl now states the CI, notes it is the
only one of eight within-season fits below .05, and does not read it as evidence; an assert breaks
the wording if the CI stops excluding zero.)

Wrong-signed, but NOT the largest within-season magnitudes: NFL (+5.30) and NBA (+5.55) margin fits are larger, with huge SEs. **NHL raw means go
the other way** (empty +0.156 vs with-fans +0.446). **Only the NHL shows an instructive reversal**
(corrected 2026-09-18, G6-32): MLB's raw margin gap is +0.003 runs, indistinguishable from zero, and
its raw win means run the same direction as its coefficient; across all 8 `within_season_dose.csv`
cells the raw-vs-FE opposition holds in 4 and fails in 4. One league on a calendar-confounded fit is
an illustration of the endogeneity argument, not a reproduced finding — the paper demotes it from
"durable contribution" accordingly.

Two caveats always travel with it: (1) within-team fan access in 2021 is confounded with calendar
time (reopening was progressive, so "more fans" ≈ "later in season"); (2) the fitted range is
0–0.40, so a per-unit `crowd_pct` coefficient **extrapolates 2.5× beyond support.** Report this
as *the within-season design being uninformative and endogenous*, which is why the headline is
identified between-season.

## Power — the real finding

`meta_cross_sport.csv` (`mde_80 = 2.8·SE`), denominators from `descriptive_hfa.csv`.

| MDE ÷ total HFA (per unit `crowd_pct`) | margin | win% |
|---|---|---|
| nfl | 1.86× | 2.04× |
| mlb | 10.15× | 1.53× |
| nba | 1.19× | **1.06×** |
| nhl | 1.44× | 1.85× |

(Post reopening-zeros fix, 2026-09-16; mlb unaffected — 0 games nulled. Was nfl 1.83×/1.99×,
nba 1.11×/1.02×, nhl 1.33×/1.71×.)

**A crowd effect accounting for 100% of home-field advantage would go undetected at 80% power in
all eight cells; the smallest ratio (NBA win%) is 1.06×.**

⚠️ **This is not robust to rescaling, and saying so is mandatory.** The coefficient is per unit
`crowd_pct` and no sport's data spans a full unit. Control-season mean dose is nfl **.97** ·
mlb **.65** · nba **.92** · nhl **.92** (treated: .065 / .320 / .079 / .069). Rescaling each MDE
to its own sport's realised contrast:

| rescaled MDE ÷ HFA | margin | win% |
|---|---|---|
| nfl | 1.81× | 1.98× |
| mlb | 6.64× | **1.00×** |
| nba | **1.10×** | **0.98×** |
| nhl | 1.33× | 1.70× |

(Post reopening-zeros fix, 2026-09-16; mlb unaffected. Was nfl 1.78×/1.94×, nba 1.02×/0.94×,
nhl 1.22×/1.58×.)

**Three cells land at ≈1.0 or below** (nba win% .98, mlb win% 1.00, nba margin 1.10 — the same
three cells as before the fix; NBA win moved from just above 1 to just below it, NBA margin moved
away from ≈1). A third consequence: **MLB's headline coefficient extrapolates ~1.5× beyond the
dose MLB typically attains** (it reads a 0→1 contrast off an empty→typical-full contrast of
0→.65) — a support-range caveat on a *headline*, not a sensitivity.

## Pooling does not buy what earlier phases claimed

`meta_cross_sport.csv`:

| | FE (inverse-variance) | RE (DerSimonian–Laird) | τ² | I² |
|---|---|---|---|---|
| 3 sports (ex-NHL) | −0.0067 (SE .0127) | +0.0005 (SE .0185) | .000424 | 39.6% |
| 4 sports | −0.0032 (SE .0113) | −0.0002 (SE .0132) | .000139 | 18.7% |

(Post reopening-zeros fix, 2026-09-16; was 3-sport −0.0046 (SE .0125)/+0.0028 (SE .0185)/.000442/
41.9%, 4-sport −0.0021 (SE .0110)/+0.0003 (SE .0126)/.000116/17.2%.)

1. **The four estimates share a BIAS, not just independent noise** — each is *crowd effect + that
   league's 2020–21 non-crowd home-specific shift*. Inverse-variance pooling shrinks *sampling*
   error as 1/√k and does nothing to a bias common across leagues (same pandemic, same empty
   buildings, same schedule compression). **The pooled SE is a lower bound on real uncertainty.**
2. **The heterogeneity test has no power at k=4** (needs Q > 7.81; observed 3.69), and I² fell
   mechanically (39.6% → 18.7%) because NHL landed near the pooled mean.
3. **The gain is specification-dependent**: −10.6% CI width FE-vs-FE, −28.6% RE-vs-RE. The FE
   point estimate "moving" −0.0067 → −0.0032 is noise theatre; both are far smaller than their SE.

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
per-unit MDE ratios stay > 1. Residual (superseded below): 37 model-sample treated-season zeros
fall after the home team had already hosted fans (nfl 17 · nba 17 · nhl 3) — that diagnostic was
defined relative to each team's first non-zero game, so it was blind to teams reporting zero for
their *entire* treated season (see `docs/agent-pitfalls.md`). The reopening-zeros fix below is the
full, exhaustive version of this residual.

## Reopening-zeros correction (2026-09-16) — every headline number moves, none flips a conclusion

`reopen_zero_sensitivity.csv`; archived pre-fix tables in `results/tables/pre_reopen_fix/`. Fix 1
(above) only nulled zeros *outside* a restriction window. Inside a window, ESPN also reports zero
for games played *after* a team had already readmitted fans — ESPN's `attendance == 0` was still
being read as a real empty stadium for those games. Rule: a zero on or after a home team's
`fans_from` date (earlier of its first non-zero home game that season and a sourced public-fans
date) is now also a reporting artifact and gets nulled, unless a sourced re-closure covers it.
Config: `config/sports.yaml` `fans_from`/`reclosures` per sport; helper:
`src.features.build.null_reporting_zeros`.

**Audit.** Every zero-bearing home team in every treated season of nfl 2020, nba 2021 and nhl 2021
was audited with a logged source search (mlb 2020 is a league-wide closed-door season, not audited; mlb 2021 zeros were already
null under fix 1) — 44 teams, **zero unverified**: 20 `no_fans` (real empty stadium all season),
15 `data_only` (first non-zero game in the data is the only evidence, no independent source needed
or found), 9 `fans_from` (a public source pins an earlier or confirming date: nfl GB/PHI, nba
IND/MIA/SAC, nhl BUF/DET/NSH/STL). 8 re-closures were sourced and kept their zeros real (nfl
ARI/BAL/DEN/PHI/PIT/WAS, nba MIN/MEM) — re-closures null nothing.

**Newly nulled: 172 games** — nfl 6 (CLE 1, GB 2, PHI 3) · mlb 0 · nba 77 (ATL 2, BOS 4, CLE 5,
IND 27, MEM 1, MIA 28, SAC 8, UTAH 2) · nhl 89 (BUF 14, DET 16, FLA 1, NJ 1, NSH 28, NYI 1, STL 28).
154 of the 172 are dated from a sourced `fans_from` entry; 18 are dated from the data alone (teams
with no sourced date: nfl CLE 1; nba ATL 2, BOS 4, CLE 5, MEM 1, UTAH 2; nhl FLA 1, NJ 1, NYI 1).

**Headline shift** (pooled win-probability LPM): nfl +0.044→**+0.050** · nba +0.016→**+0.006** ·
nhl +0.007→**+0.011** · mlb −0.021 (unchanged, 0 nulled). Largest single shift: NBA win
probability, 0.35 SE. **Two cells now exclude a full-HFA effect (MLB win, NBA win)**, not three —
NHL margin's CI (`within_season_dose.csv` is a different, within-season table; this is the pooled
6a CI in `twfe_cross_sport.csv`) moved from [−0.233, +0.239] to [−0.217, +0.296], which now sits
*above* both NHL's HFA (0.254) and its rescaled HFA (0.276), so it no longer excludes a full-HFA
effect. All eight per-unit MDE-at-80%-power ratios stay above 1 (tightest now NBA win% at 1.06×,
was 1.02×); the separate rescaled-ratio claim (three cells at ≈1.0 or below) also still holds —
these are two different claims on two different scalings, don't conflate them.

**Legitimacy — not outcome-blind, and the paper says so.** The problem was found through a
literature comparison (Ganz & Allsop; Phase 8 stage B.G5 finding "N1"), not through the audit. A
scratch version of the rule was run and its estimates seen *before* the spec was written, and the
"who counts as fans" definition was then amended (public spectators, ticketed or invited; not
family/staff/media/on-duty) after the Task 1 source review. Both the scratch and the final numbers
ship in `reopen_zero_sensitivity.csv`. What keeps this from being a forking path: the audit is
**exhaustive and mechanical** — every all-zero and late-zero team in every treated season was
searched for a source whichever way the estimate moved — 29 of 44 verdicts rest on a public source,
15 on the data alone (the team's first non-zero ESPN game, set by the rule with no discretion; 6 of
those found no source either way) (it moved NBA toward zero and NHL away from zero; both
ship as found).

**Disclosed, not fixed:**
- NSH and STL's `fans_from` dates each rest on a handful of invited guests (frontline
  workers/first responders seated as spectators), which reclassifies all 28 of each team's
  treated-season home games from real-empty to artifact-or-fans. No post-hoc crowd-size threshold
  was added to guard against this — a spectator's size is carried by the dose itself, and a
  size cutoff chosen after seeing the estimates would be exactly the forking path this fix is
  trying to avoid.
- **NHL DET's `fans_from` is kept at 2021-03-10** despite a conflicting source (a season-ticket
  holder quoted saying his family had been attending "back in January"); no source pins that
  claim to a specific game or contradicts the January 250-person friends/staff-only policy for any
  specific game before March 10, so the never-round-backward rule kept the later, better-sourced
  date. 12 games are at stake if a source later resolves the conflict the other way.
- The data-only arm of `fans_from` (first non-zero ESPN attendance) is not itself source-checked:
  a wrong *non-zero* ESPN count from a family/staff-only game could set a `fans_from` date earlier
  than the team's true first public-fans game. This is a residual limitation of the rule, not of
  the audit.

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
| margin | **+0.888** | +2.601 | +2.033 | +1.959 | +1.820 | +1.928 |
| win% | **+0.0129** | +0.0707 | +0.0626 | +0.0465 | +0.0451 | +0.0501 |

(Post reopening-zeros fix, 2026-09-16 — base shifts with the twfe headline; was margin
+0.674/+2.359/+1.799/+1.730/+1.619/+1.705, win% +0.0072/+0.0643/+0.0564/+0.0407/+0.0388/+0.0441.)

Dropping 2018 moves win% by −0.98 SE; no other season moves either outcome by more than 0.58 SE (−2019 margin).
mlb/nhl stable (largest 0.65 SE, MLB −2023 win%, unaffected by this fix); nba's largest is −0.66 SE.
Read with both halves: **partly genuine fragility, partly the mechanical fact that dropping an
endpoint of a 6-season panel tilts the linear trend.** It removes the basis for calling NFL
"suggestive evidence"; it does not make the result fake.

**B1 — the treatment is season-level, so inference on 1,500–13,000 games is wrong.**
`season_effects.csv`, `noise_floor.csv`. Effective independent treatment draws = **6 seasons**.
Clustering by season is not the fix (6 clusters ≪ the ~40 cluster-robust variance needs; the
two-way attempt returns SEs 0.44–0.77× the size of the shipped ones — the estimator breaking, not
a correction).

- **Randomization inference:** each season wears the treatment dummy in turn. **No RI p-value
  below .333**, and the floor `1/(1+n_placebo)` is **.167** (mlb .200). *No result this design can
  produce can reach p<.05 under RI.* **NFL 2018 deviates +3.697 margin vs treated 2020's −1.802 —
  ordinary season-to-season noise in home advantage exceeds the COVID signal.** Consequence:
  report intervals and magnitudes, not p-values against a bar they cannot clear.
- **Noise floor.** Two components bind and neither shrinks with more control seasons: the treated
  season's own sampling noise (2020 happened once) and `sd_true`, genuine between-season variation
  in HFA. **NFL's `sd_true` is 1.73 margin points — essentially the whole of its 1.75 HFA.**
  `ratio_floor = 2.8·hypot(both) ÷ HFA` is ≥ 1.0 in 7 of 8 cells (nfl 3.23×/3.77× · mlb
  5.96×/**0.88×** · nba 1.29×/1.29× · nhl 1.13×/1.46×). **Would more seasons buy significance? No**
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
> than the entire home-field advantage of that sport, the smallest (NBA win probability) by 6%.
> (That ratio is **per unit `crowd_pct`**; rescaled to each sport's realised contrast, three cells
> fall to ≈1.0 or below. Say which scaling you are quoting.) Four estimates, each individually
> underpowered and none distinguishable from zero — not the same as near zero: NFL's is ~96% of its
> win-probability HFA per unit, and +0.013 without 2018. (The old "all centred near zero, none able
> to exclude an NFL-sized effect" was false — MLB win's CI excludes it; corrected 2026-09-18, G6-23/24.) In the one sport where a published estimate can be mapped into our units (**NBA**),
> it sits at the upper edge of our interval. A shared, unmeasured 2020–21 home-specific confound remains, and
> **pooling does not reduce it.** The claim this study can defend is that it cannot distinguish
> zero from a crowd effect accounting for all of HFA under randomization inference (floor .167; the
> team-clustered CIs exclude it for MLB and NBA win); it is *not* evidence that crowds don't matter.

**This study was NOT pre-registered.** The internal pre-commitment discipline is not a public
timestamp. Complete disclosure is what substitutes for it — say so plainly.
