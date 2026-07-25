# Phase 7 — pre-write-up consolidation — design

**Date:** 2026-07-25
**Status:** approved (brainstorm complete, awaiting implementation plan)
**Replaces:** the cancelled "Phase 7 — bubble decomposition + placebo"

---

## 1. Why this phase exists

Two problems block a defensible Phase 8 write-up.

**Problem 1 — five numbers destined for the paper exist only as prose.** The pooled
meta-analysis, the trend sensitivity, the season-FE sensitivity, the NHL within-2021
dose curve, and the MLB treated-season split were all computed ad hoc during the NHL
final review and recorded in `CLAUDE.md`. None is produced by code; none is in
`results/tables/`. A research paper whose numbers are hand-copied out of a markdown
file is not reproducible, and a transcription slip goes straight into the paper. Two of
these (the wrong-signed within-2021 dose, the +0.076 season-FE coefficient) are the
numbers a referee will interrogate hardest, so they are the worst possible candidates
for living in prose.

**Problem 2 — the study's null has never been positioned against the literature.** A
systematic review of COVID "ghost game" studies in football found **not one study
reporting increased home advantage**: 6 no change, 2 slightly reduced, 8 reduced, 10
strongly reduced. Higgs & Stavness (2021) report NBA home teams winning by 2.13 points
with fans versus 0.44 without. A PLOS One study finds the absence of fans removes the
home advantage in NHL penalty calls. Our study reports point estimates near zero with
CIs that cross zero in all four sports. **That tension is the single most important
thing the paper must address**, and it cannot be addressed without reading the
literature first.

**Scope decision (settled):** paper-facing and correctness fixes only. The ~20 latent
and cosmetic Minors accumulated across eight phases are catalogued as known-and-accepted
rather than churned through estimator code that is now producing final, byte-verified
numbers. Tidiness is a bad trade against regression risk at this stage.

---

## 2. Framing correction that shaped this design

An earlier framing — "numbers in prose are unreproducible, so everything must move into
modules" — was too coarse. **Quarto `.qmd` files execute code**, so a number computed in
a `.qmd` chunk *is* generated from source. Only `CLAUDE.md` prose is the defect.

The operative distinction is therefore:

- **Analysis** — an alternative model specification whose result could change a
  conclusion, deserving tests, review, and a CSV artifact → **module**.
- **Presentation** — reformatting an existing panel into a display table → **`.qmd`
  chunk**.

All five items in §3 are analysis: they are refits of the causal estimator under
different specifications, or the study's top-line aggregation. The bubble regime table
and similar summaries remain Phase 8 chunks.

---

## 3. Workstream A — `src/models/sensitivity.py`

One new module. Reuses `twfe.fit` throughout; **no new estimator**. Each function
returns a DataFrame and writes one CSV to `results/tables/`.

| Function | Output CSV | Content |
|---|---|---|
| `meta_cross_sport()` | `meta_cross_sport.csv` | Fixed-effect (inverse-variance) **and** random-effects (DerSimonian–Laird) pooled win% estimates, with Q, df, p, I², τ². Two rows per method: the **4-sport** set and the **3-sport set excluding NHL** (the pre-NHL baseline, so the precision gain from adding a sport is visible rather than asserted) |
| `trend_sensitivity()` | `trend_sensitivity.csv` | Per sport × outcome, crowd coefficient under no trend / linear trend (shipped) / quadratic trend |
| `season_fe_sensitivity()` | `season_fe_sensitivity.csv` | Per sport × outcome, crowd coefficient under full season FE, plus R² of `crowd_pct ~ C(season)+C(home_team)` as the collinearity diagnostic |
| `within_season_dose()` | `within_season_dose.csv` | **All four sports.** Refit restricted to that sport's `treated_seasons` (team FE, same controls, clustered by home team), plus raw empty-vs-with-fans means and the fitted `crowd_pct` support range. MLB has **two** treated seasons (2020, 2021) — pool them and add a season dummy; the other three sports have one treated season and take no dummy |
| `mlb_treated_split()` | `mlb_treated_split.csv` | MLB 2020 and 2021 as separate treatment indicators — tests whether MLB's faint wrong sign is a 2020 rule-change artifact |

`main()` runs all five and prints a summary.

**Design notes:**
- **`within_season_dose` runs for all four sports** (approved). NHL alone would be an
  anecdote; four sports makes it a comparison, and the endogeneity sign-flip found in
  NHL (raw means positive, team-FE estimate negative) is worth testing for reproduction
  elsewhere. Each row must carry the fitted support range, because NHL's is 0–0.40 and a
  `crowd_pct` coefficient extrapolates 2.5× beyond it — a caveat that is meaningless
  without the range alongside.
- **`meta_cross_sport` must emit both FE and RE.** The FE-only presentation previously
  led to an unsupportable precision claim (see §6). Reporting both makes the
  specification-dependence visible rather than a footnote.
- **`season_fe_sensitivity` must emit the collinearity R² next to the coefficient.**
  The coefficient alone looks like a damning omitted result; the R² is the rebuttal, and
  separating them invites misreading.

**Tests (`tests/test_sensitivity.py`):**
- Sample integrity: each refit uses the rows it claims (`n_obs` reconciles against a
  directly-computed expectation), the property that makes coefficient comparisons
  interpretable at all.
- Meta arithmetic: FE and RE against a small hand-worked example with known answers,
  including the τ²=0 case where RE must collapse to FE.
- Not vacuous: any test asserting an equality must be able to fail. (An earlier version
  of the NHL travel test asserted `n_obs` equality on a fixture with no NaNs, so it held
  under every possible implementation.)

---

## 4. Workstream B — literature positioning

**Deliverables:** `docs/literature-review.md` (standalone working document) and a
populated `paper/references.bib` (currently a single comment line, zero entries).

Standalone rather than draft paper prose: the paper will cite a subset, its framing is
not yet settled, and the review remains useful as project memory regardless of Phase 8's
editorial choices. It should be structured so Phase 8 can lift sections directly.

**Four questions the review must answer:**

1. **What did prior work find**, split by sport and — critically — by *outcome type*:
   match results versus referee behaviour. These are different findings and conflating
   them is the main way this literature gets misread.
2. **Where do our estimates sit against theirs?** The sharpest available comparison is
   Higgs & Stavness's NBA 2.13 → 0.44 against our descriptive 2.26 → 0.92.
3. **Are we underpowered relative to studies that found effects?** Football has more
   matches and a larger baseline home advantage. This may be the entire explanation for
   the divergence. **Testable:** compare our per-sport minimum detectable effects (NHL's
   is ~6.3pp of win probability) against the effect sizes prior studies report. Gets its
   own table — this is the question that could change the paper's conclusion.
4. **Does mechanism-vs-outcome reconcile the NHL case?** A PLOS One study finds fan
   absence removes home advantage in NHL *penalty calls*; we find no change in NHL
   *outcomes*. These are compatible — referee bias can shift without moving win
   probability — and stating that precisely is the difference between "our null
   contradicts published work" and "our null is consistent with it at the outcome level
   while their mechanism finding stands."

**`references.bib`** gets: the systematic review, Higgs & Stavness, the PLOS One NHL
penalties paper, the ghost-matches referee-bias paper, 538/Neil Paine for the Elo
parameters and the OT/shootout finding, ESPN as data source, plus whatever the review
surfaces. Every entry must correspond to a source actually read, not a search-result
title.

---

## 5. Workstream C — paper-facing and correctness fixes

**C1 — `summarize(panel, playoffs=False)`.** `src/viz/descriptive.py:33,57` hardcode
`~is_playoff`, so the playoff-HFA subsection promised for Phase 8 **cannot currently be
written**. Add the parameter; keep the default so existing behaviour and all shipped
numbers are unchanged.

**C2 — palette contrast.** Phase 5 logged NBA's colour contrast at **2.62, below the
3:1 threshold**, on figures headed for print where sport is encoded by line colour.
Replace NBA's `#e87ba4` with a darker alternative measuring **≥3:1 against white**, kept
distinguishable from the other three under deuteranopia and protanopia; verify the
measured ratio and record it in the implementation report rather than asserting it.
Update `SPORT_COLORS` **identically** in `twfe.py` and `descriptive.py` (they are
separate dicts that must agree), then regenerate all three figures. Delete the `descriptive.py:19` reference to
`scripts/validate_palette.js`, which has never existed — either build the check or stop
citing it; do not leave a phantom reference in code that ships with a paper.

**C3 — verify three claims currently stated as fact:** the NHL 2021 four-division
realignment including the all-Canadian division (the entire justification for the travel
diagnostic), whether Toronto and Edmonton played bubble qualifying-round games in their
own arenas, and the bubble hub dates (1 Aug – 28 Sep 2020). Each either gets a citation
in `references.bib` or is removed from the write-up.

**C4 — two correctness Minors with paper exposure:**
- `twfe.py:77` — `extra_controls` naming an entry already in `CONTROLS` and not in
  `drop_controls` produces a duplicate column and breaks `d[controls]`. Currently latent
  with no live caller, but **this phase adds callers**, so it stops being latent. One-line
  fix (`dict.fromkeys` de-dupe) plus a test.
- `tests/test_config.py:9` — `test_config_has_three_sports_with_treated_seasons` asserts
  four. Rename.

**Explicitly out of scope** (catalogued, not fixed): `fetch_summary` AttributeError on a
`gameInfo: null` ESPN never emits; unknown-sport bare `KeyError`; `stadium_id` null →
`"nan"`; `walk_scoreboard` `["team"]` fragility; doubleheader rest=0; Elo no-update on
ties; coords-coverage test FileNotFound on cold checkout; NFL-side tests duplicating
`test_espn.py`; the `value_counts().idxmax()` tie-break; assorted unused test fixtures.

---

## 6. What this phase must NOT do

**Do not restate the pooled estimate as a precision claim.** The four sports share a
*bias* — each estimate is "crowd effect + that league's 2020–21 non-crowd home-specific
shift" — not merely independent noise. Inverse-variance pooling shrinks sampling error
as 1/√k and does nothing to a common bias, so the pooled SE is a **lower bound**. Any
sentence of the form "the pooled CI rules out effects larger than X" is unsupportable.

**Do not treat absence of heterogeneity as evidence of homogeneity.** At k=4, rejecting
homogeneity requires Q > 7.81; observed Q = 3.48. The test has no power. I² fell from
40.4% to 13.8% *mechanically* when NHL landed near the pooled mean.

**Do not re-specify the main model.** The 6a specification is frozen by pre-commitment.
This phase reports sensitivities; it does not adopt them.

**Do not describe any sport's result as a "clean null."** Every per-sport CI is wide
enough to contain the other sports' point estimates. The correct framing is
underpowered-and-centred-near-zero.

---

## 7. Order and rationale

**B → A → C.**

Literature first: if prior work uses a standard specification or a power comparison we
should report, that requirement lands in the sensitivity module rather than forcing a
second pass. Fixes last, because C2 regenerates all three figures and should happen
after any other change that touches them.

---

## 8. Done when

- `src/models/sensitivity.py` exists with five functions, five CSVs in
  `results/tables/`, and `tests/test_sensitivity.py` passing.
- `docs/literature-review.md` answers all four questions in §4, including the
  power-comparison table.
- `paper/references.bib` has real entries for every source cited, each actually read.
- `summarize()` takes `playoffs`; the palette meets 3:1; the phantom
  `validate_palette.js` reference is gone; three claims verified or removed; two
  correctness Minors fixed.
- Full suite green. Every number Phase 8 will cite is either a CSV in `results/tables/`
  or computable in a `.qmd` chunk from a built panel — **none in `CLAUDE.md` prose**.
