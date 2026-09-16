# Paper write-up guide (Phase 8)

Binding rules for the Quarto write-up. Numbers come from `results/tables/*.csv`, never from
prose. Findings and their framing live in `docs/results.md`; literature in
`docs/literature-review.md` (§§1–5 can be lifted directly — every number in it was
independently reproduced).

## Language bans — earlier drafts violated all four

1. **Never call any sport's result a "clean null" or an "independent null replication."**
   NHL's CI contains both NFL's +0.044 and NBA's +0.016. It is *consistent with* the other
   nulls, not corroboration of them.
2. **Never write "the pooled CI rules out effects larger than X."** The four sports share a
   bias, not merely independent noise. The pooled SE is a lower bound on real uncertainty.
3. **Never read absence of heterogeneity as evidence of homogeneity.** At k=4 the Q test has
   no power, and I² fell mechanically because NHL landed near the pooled mean. (The MLB
   argument in this project says the true effects are *not* common.)
4. **Never re-specify the frozen 6a model.** It was pre-committed and every number in
   `results/tables/` is byte-verified against it.

Also: **do not write "monotonic"** about the NHL HFA drift (2 of 5 steps are up), and **do not
lead with p-values** — under randomization inference the design's floor is .167, so
"not significant" is a property of the design, not a result. Report intervals and magnitudes.

## Framing

Lead with the **power ceiling**, not the null: *this design cannot distinguish zero from a crowd
effect explaining all of home advantage.* Then:

1. **Drop "NFL is the only appreciable point estimate" as a standalone claim** — it survives only
   with 2018 in the sample. State the leave-one-out beside it.
2. **MLB is an identification story, not a power story** — 74.6% dose overlap means the natural
   experiment barely applies. Its section stops being about power.
3. **Lead with randomization inference**, not the clustered p-values.

## Content checklist

- Present **6a (adjusted)** and **6b (raw before/after)** side by side. Use the precise naming
  **"comparative interrupted time series / away-team-as-control"**, not literal "2×2 DiD" (that's
  the intuitive label only). State the shared confound explicitly. `did_hfa_shrink.png` is the
  intuitive centerpiece.
- The three 6a honesty corrections: no within-season dose curve for any sport; `closing_spread`
  is a post-treatment bad control; the identifying assumption stated plainly.
- The playoff-exclusion caveat **plus** a descriptive playoff-HFA subsection via
  `descriptive.summarize(panel, playoffs=True)`. Blended with seeding quality, so it carries an
  asterisk. ⚠️ It **omits** seasons with zero clean playoff games (NBA 2020, NHL 2020) rather than
  emitting `n_games=0` rows — expect *missing* rows.
- The **NBA bubble decomposition + seeding placebo** as a short, explicitly-hedged subsection
  computed inline — **not** a disentangler. Report the regime table with SEs and draw no inference.
- The NHL sections in full: trend sensitivity, season-FE sensitivity **with its rebuttal**, the
  wrong-signed within-2021 dose curve **with both caveats**, the travel diagnostic, the 2022
  Omicron control-contamination note, and the load-bearing `is_bubble` date rule.
- **Why MLB shows no / faint-wrong-sign crowd effect**, in four parts: (1) statistically ZERO,
  not a reversal — margin CI [−0.39, +0.16] p .42, win% [−0.038, +0.013] p .33, the negative sign
  is noise; (2) baseball's total HFA is smallest in major sports and its known mechanisms are
  **crowd-independent** (batting last, park familiarity survive an empty stadium; the
  crowd→official-bias channel is weak in baseball) — **web-verify the comparative HFA numbers
  before citing**; (3) run margin is the noisiest outcome and MLB's MDE is 10.2× its own HFA;
  (4) the confound is worst in baseball (ghost runner, universal DH, 7-inning doubleheaders,
  60-game regional schedule — several pushing HFA the home team's way). The treated-split check
  came out **inconclusive**. Honest claim: "no detectable MLB crowd effect"; **not** "crowds
  don't matter in baseball".
- **Two tables have no CSV and must be computed inline:** the descriptive playoff-HFA table, and
  the NBA bubble decomposition + seeding placebo.

## Citations — corrections already made once, don't undo them

- **NBA "2.13 → 0.44 pts" is Ganz & Allsop (2024)**, *A Mere Fan Effect on Home-Court Advantage*,
  *Journal of Sports Economics* 25(1), 30–53 (FE-IV, instrumenting with 2020–21 attendance
  restrictions). It is **NOT** Higgs & Stavness (2021), which is a Bayesian negative-binomial
  model reporting log-scale parameters and contains no such pair. Both are in the bib.
- The **6/2/8/10 ghost-game split** is Leitner et al.'s 26-study review (primary-verified at
  PMC8724651). **Wang & Qin (2023)** is a *different* review of 28 articles split by outcome type
  8/6/4/10. Do not merge the two.
- **The literature is NOT near-unanimous.** Three published nulls sit on our side: Schank et al.
  (2024) (full Bundesliga spectator-ban season, U-shaped dose curve in 2021/22), Higgs & Stavness
  (2021) (no meaningful MLB change), Gong (2022) (null on the NBA referee-bias mechanism). Write
  "predominantly, but not unanimously, in favour of a crowd effect."
- **Conversion to our units exists for NBA only.** Ganz & Allsop's 2.13 → 0.44 converts to
  Δ = **4.65 pp** (Φ(μ/σ), σ = 14.42 measured on our own clean NBA panel, n = 6,925) against our
  NBA win% MDE of **7.19 pp**; our margin CI [−0.68, +2.83] contains their 1.69-pt effect. No
  conversion was invented for the football studies (draws break the binary outcome) or for Higgs
  & Stavness (log scale, no published translation).
- **`plosone_nhl_penalties` has an internal source inconsistency:** its prose says b = .17, its
  own regression table says **b = .186 (SE .083, z = 2.254, p = .024)**. The table is
  authoritative; `.17` is not even a rounding of it.
- `systematicreview_ghostgames`' published PDF was never seen (Springer 303 / ResearchGate 403).
  Quotes are primary-verified from the PMC mirror.
- Two C3 claims rest on Wikipedia (tertiary): that TOR/EDM played bubble games in their own
  arenas, and the 1 Aug – 28 Sep 2020 hub dates. Upgrade the source if either does argumentative
  work. NHL.com confirms the 2020–21 four-division realignment structure but does **not** state
  cross-border travel as the reason — hedge that rationale.

## ⚠️ The units trap

Two different power ratios appear in this project and are **not interchangeable**:

- `meta_cross_sport.csv`'s `mde_80` is **per unit `crowd_pct`**.
- `noise_floor.csv`'s ratios are on the **season-dummy / outcome-level** basis (margin points,
  win-probability points — same units as HFA).

`mde_80` gives **all eight** cells above 1.0 per unit; `noise_floor` gives **seven of eight**.
They are different claims on different bases, and they no longer even share a count.
**Always name the basis; never quote them side by side without it.**
