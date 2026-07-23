# Phase 6b — on/off 2×2 DiD (design)

**Date:** 2026-07-22
**Status:** approved, ready for plan
**Depends on:** Phase 6a (`src/models/twfe.py`), processed panels in `data/processed/{sport}.parquet`

## Purpose

The intuitive, co-primary companion to 6a's controlled TWFE engine. Report the
raw before/after change in home-field advantage across the crowd shock:
"home teams won X% / by Y points **with** fans, dropped to X'% / Y' **without** —
a Z swing." One number a human can hold, one chart that shows the shrink.

6a is the controlled estimate (Elo/rest/travel/team-FE/season-trend). 6b is the
**raw, unadjusted** counterpart. It deliberately does **not** rebuild 6a.

## What the "2×2 DiD" is here (and isn't)

A textbook DiD needs a treated group and a contemporaneous **control group**.
The COVID crowd shock hit every team at once, so there is no untreated team to
be the control group. What rescues the design: the outcome `home_margin` is
already a `home − away` difference, which supplies a within-game control group
for free.

| | Full-crowd seasons | Treated (empty) seasons |
|-----------------|--------------------|--------------------------|
| **Home** (treated unit) | home pts | home pts |
| **Away** (control unit) | away pts | away pts |

DiD = `(home−away)_full − (home−away)_treated` = `HFA_full − HFA_treated` =
the crowd effect on HFA. The **away team is the control group**; other seasons
are the **control period** (the before/after axis), not the control group.

**What differences out:** any *symmetric* league-wide 2020–21 shift (general
scoring changes lift home and away equally → cancel in `home_margin`).
**What does NOT:** any *home-specific* non-crowd 2020–21 change (referee
behavior with no crowd, disrupted travel routines, etc.). So 6b carries the
**same confound as 6a** — "crowd + other home-specific pandemic shifts" — and is
**not** cleaner identification. Phase 7's bubble decomposition remains the only
disentangler.

**Naming honesty (for Phase 8):** strictly this is a comparative interrupted
time series / within-unit before-after with an implicit away-team control.
"2×2 DiD" is the intuitive label; keep the precise naming in the write-up.

## Settled decisions

1. **Crowd binary = season-level, off `treated_seasons`.** `reduced = season ∈
   treated_seasons` (NFL [2020], MLB [2020,2021], NBA [2021]). Full = every other
   season, pooling pre- and post-COVID. Rejected the game-level `crowd_pct <
   threshold` binary: it reintroduces the endogeneity we avoided (a normal-season
   low-attendance game — bad team, small crowd, loses — would be mislabeled
   "reduced"). Season-level is exogenous (policy caps) and matches 6a's sample logic.
2. **Raw means, not adjusted.** No controls, no team FE in the headline. That is
   the point — the intuitive number. "Does it survive controls?" is answered by
   6a; that's the division of labor.
3. **Clustered SE.** Inference via a one-line `outcome ~ reduced` OLS with SE
   **clustered by `home_team`** — honest error bars, not `descriptive.py`'s naive
   iid SE.
4. **Sign convention matches 6a.** Report `crowd_effect = HFA_full − HFA_reduced`;
   positive = crowd helps the home team (empty→full), identical meaning to 6a's
   `crowd_pct` coef, so the two tables sit side by side.
5. **Two outcomes, two samples — mirror 6a.** Outcomes `home_margin` + `home_win`
   (LPM). Samples `pooled` + `restricted` (`treated ± 1` adjacent season).

## Module: `src/models/did.py`

Sport-blind, no branching. Mirrors `twfe.py`'s shape.

### `fit(panel, outcome, sample="pooled", treated_seasons=None) -> dict`

Pure (no disk/net). Steps:

1. **Exclude** `neutral_site | relocated_home | is_bubble | is_playoff` (fillna
   False). Reuse 6a's exclusion logic — do not re-derive a second copy. (6a's
   `_prep` also builds `elo_diff`/`rest_diff`; 6b needs neither, so factor the
   exclusion mask into something both can call, or call a shared helper. A 4-line
   inline mask with a `ponytail:` note is acceptable if factoring is more churn
   than it saves — implementer's call, but there must be ONE definition of the
   exclusion set across 6a/6b, not two that can drift.)
2. If `sample == "restricted"`: keep `season ∈ _restricted_seasons(treated_seasons)`
   (reuse `twfe._restricted_seasons`, = `set(treated) ∪ {min−1, max+1}`).
3. `reduced = season ∈ treated_seasons` (bool).
4. Select `[outcome, reduced, home_team]`; `astype(float)` the outcome
   (bool/Int64 → float, LPM-safe); `dropna()` (drops null `home_win` ties).
   Record `n_full`, `n_reduced` from the two `reduced` groups post-dropna.
5. OLS `outcome ~ reduced` (intercept + one dummy), statsmodels,
   `cov_type="cluster"`, `cov_kwds={"groups": home_team}`.
   - `hfa_full = intercept`; `hfa_reduced = intercept + coef_reduced`.
   - `crowd_effect = hfa_full − hfa_reduced = −coef_reduced`.
   - SE/CI/p of `crowd_effect` = those of `coef_reduced` with the CI bounds
     swapped-and-negated (a linear sign flip; the SE and p-value are unchanged).

**Returns** a flat dict:
`sport, outcome, sample, hfa_full, hfa_reduced, crowd_effect, se, ci_low,
ci_high, pvalue, n_full, n_reduced, n_obs, n_entities`
(`n_entities` = distinct `home_team`; `n_obs` = `n_full + n_reduced`).

### `plot_slope(results) -> Figure`

Dumbbell / slope chart. One panel per outcome (`home_margin`, `home_win`), one
row per sport, two dots per row — `hfa_reduced` (empty) → `hfa_full` (with fans)
— connected by a line so the **shrink** is the subject. Sport colors reuse
`twfe.SPORT_COLORS`. Use the **pooled** rows for the figure (restricted is a
table-only robustness check). A near-flat MLB line is expected and tells the
Phase-5 "baseball HFA is noise" story for free.

### `main() -> None`

Load the three `data/processed/{sport}.parquet`, read `treated_seasons` from
`config/sports.yaml`. Loop sports × {`home_margin`,`home_win`} × {`pooled`,
`restricted`}. Write:
- `results/tables/did_{nfl,mlb,nba}.csv`
- `results/tables/did_cross_sport.csv` — `home_win` rows only (margin isn't
  cross-sport comparable, same rule as 6a's `twfe_cross_sport.csv`).
- `results/figures/did_hfa_shrink.png`.
Print a one-line-per-row summary (mirror `twfe.main`'s print).

## Tests: `tests/test_did.py`

Synthetic panel (no disk/net), a handful of asserts:
1. **Recovery + sign:** bake a known HFA into full vs treated seasons (e.g.
   full home_margin ≈ +3, treated ≈ +1) → `crowd_effect ≈ +2`, positive.
2. **Exclusions:** rows flagged `is_bubble`/`neutral_site`/`is_playoff` are
   dropped (assert `n_obs` excludes them).
3. **Restricted sample:** `sample="restricted"` keeps only `treated ± 1` seasons
   (assert a far-away full season is excluded from `n_full`).
4. **LPM outcome:** `home_win` runs and returns a `crowd_effect` in a sane range;
   null ties are dropped.

No frameworks/fixtures beyond a small DataFrame builder.

## Non-goals / carried forward

- **Not** an adjusted model (that's 6a). No Elo/rest/travel/FE in the headline.
- **Not** a new identification strategy — same confound as 6a; Phase 7
  disentangles.
- **Phase 8 honesty:** MLB slope near-flat (Phase-5 noise); per-sport CIs wide
  and likely zero-crossing (underpowered — a finding, not a failure); keep the
  "comparative interrupted time series" naming caveat.
