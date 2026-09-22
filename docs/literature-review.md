# Literature positioning: where this study's null sits relative to published work

Workstream B of the pre-write-up consolidation phase (Phase 7). Written 2026-07-27.
Sections 1–5 below are structured so Phase 8 can lift them into the paper directly.
Numbers re-verified 2026-09-18 against `results/tables/*.csv` (and panel-derived ones — dose means,
σ, one-goal share — against `data/processed/`) post the reopening-zeros fix. Published-study numbers are
as transcribed from the sources in §0, not re-derived.

**The result being positioned.** Four sports, TWFE pooled, win-probability LPM
(`results/tables/twfe_cross_sport.csv`):

| sport | crowd coef (Δ win prob) | SE | 95% CI |
|---|---|---|---|
| nfl | +0.0501 | 0.0378 | [−0.0241, +0.1242] |
| mlb | −0.0208 | 0.0156 | [−0.0513, +0.0097] |
| nba | +0.0064 | 0.0268 | [−0.0461, +0.0589] |
| nhl | +0.0107 | 0.0253 | [−0.0389, +0.0603] |

Every interval crosses zero. The published ghost-game literature points, on balance,
the other way. **Section 3 is the section that matters**: where a published effect exists
in a comparable unit, our interval for that sport is wide enough to contain it. That is a
statement about what this design can resolve, not a finding about the size of the crowd
effect — and it is only directly testable for one sport (NBA). NFL has no comparable
published ghost-game estimate; NHL has no published *outcome* effect to compare against
(§4); MLB's only comparable published result is itself a null.

---

## 0. Retrieval log — what was actually read, and what was not

Retrieved and read in full or in substantial part:

| source | what was retrieved |
|---|---|
| `systematicreview_ghostgames` | PMC full text, **PMC8724651** (open access) |
| `wang2023crowdreview` | PLOS ONE full text (open access) |
| `higgs2021nba` | *Scientific Reports* full text (open access) |
| `ganz2024nbafans` | *Journal of Sports Economics* article page, findings + method + sample |
| `plosone_nhl_penalties` | PMC full text (open access) |
| `leitner2021referees` | PMC full text (open access) |
| `gong2022nbafouls` | PMC full text (open access) |
| `schank2024bundesliga` | arXiv abstract page + HTML full text |
| `paine_nhl_elo` | Substack post, full text |
| `espn_data` | live endpoints re-verified 2026-07-27 (HTTP 200; `gameInfo.attendance` present) |
| `nhl2020realignment` | NHL.com article, full text |
| ~~`wikipedia2020stanleycup`~~ | removed C1 2026-09-21; replaced by NHL.com sources below |
| `flannagan2024umpire` · `chiu2022mlb` | publisher full text (open access) |
| `saiegh2026umpire` | published version, UCSD eScholarship (CC BY) |
| `losak2021baseball` | published version, Syracuse SURFACE repository |
| `nhl2020seasonplan` · `nhl2020hubratify` · `nba2020virtualfans` | NHL.com / NBA.com, full text |
| `farnell2023nflpenalties` | published version, Maynooth University repository (C2 2026-09-21) |
| `mcmahon2024cfb` | **accepted manuscript** (Oct 2023), WCUPA repository via Wayback snapshot; published version not read (C2) |

C1 (2026-09-21) re-verified every entry above (C2 added the last two); the row-by-row audit is
`.superpowers/sdd/phase8-polish/citation-ledger.md` + `citation-spotcheck.md`.

Nothing on the reference list is unretrieved. The publisher's copy of
`systematicreview_ghostgames` is paywalled (Springer and ResearchGate both refuse automated
requests), but the **full text is open access at PubMed Central, PMC8724651**, and both
load-bearing claims were confirmed there verbatim:

> "six studies conclude 'no change in home advantage', two studies conclude a 'slightly
> reduced home advantage', eight studies conclude a 'reduced home advantage' and ten studies
> conclude a 'strongly reduced home advantage'"

> "There is not a single study that found an *increased* home advantage in ghost games"

The review's final analysis covers **26 primary studies, 20 of them peer-reviewed**. Phase 8
may cite the 6 / 2 / 8 / 10 breakdown and the no-increase statement as primary-verified, with
no hedge.

**Note on the `wang2023crowdreview` split.** `CLAUDE.md` currently attributes the
6 / 2 / 8 / 10 split to "a systematic review of football ghost-game studies". That split
belongs to `systematicreview_ghostgames` (26 studies). The *other* systematic review,
Wang & Qin (2023), covers 28 articles and reports a different, **outcome-type** split:
8 match outcome · 6 technical/tactical · 4 physical performance · 10 referee bias. Do not
merge the two — they are different papers counting different things.

> ### ⚠️ Attribution correction for `CLAUDE.md`
> `CLAUDE.md` states: *"Higgs & Stavness (2021) report NBA 2.13 → 0.44 pts."*
> **This is a misattribution.** Higgs & Stavness (2021) is a Bayesian negative-binomial
> multilevel model reporting home-advantage parameters **on the log scale**; it reports no
> such point-margin pair. The **2.13 → 0.44** figures are from **Ganz & Allsop (2024)**,
> *A Mere Fan Effect on Home-Court Advantage*, *Journal of Sports Economics* 25(1), 30–53
> (`ganz2024nbafans`). Phase 8 must cite Ganz & Allsop for that number. Both papers are in
> `references.bib`; both are relevant, but they are not interchangeable.

---

## 1. What prior work found

Split by **outcome type**. Conflating match results with referee behaviour is the main
way this literature gets misread: a study can find a large, real shift in *how officials
call fouls* while saying nothing about who won.

### 1a. Match-result outcomes

| study | sport / league | outcome | effect with fans | effect without fans | n | direction |
|---|---|---|---|---|---|---|
| `ganz2024nbafans` | NBA (2020-21) | points margin | **+2.13 pts** (raw mean) | **+0.44 pts** (raw mean; gap p = .09) | 2020-21 regular season; regressions: +4.53 pts fans allowed vs none (FE, SE 2.07), +1.74 pts per 1,000 fans (IV on max allowable capacity, SE 0.69) | reduced |
| `leitner2021referees` | 8 European football leagues | home win rate | 63.5% | 52.5% | 1,286 matches (645 with fans, 641 ghost) | strongly reduced |
| `leitner2021referees` | same | league points/game | +0.61 | +0.11 | as above | strongly reduced |
| `schank2024bundesliga` | Bundesliga, last 9 matches of 2019/20 | home win prob | baseline | **−13 pp**; home goals −0.45 | 9 matchdays | strongly reduced |
| `schank2024bundesliga` | Bundesliga **2020/21** (ban for most matches) | home advantage | — | **"very close to the pre-COVID season 2018/19"** | full season | **no change** |
| `schank2024bundesliga` | Bundesliga 2021/22 (varying caps) | home win prob | — | **U-shaped** in utilisation; +12–13 pp at *medium* utilisation | full season | non-monotone |
| `higgs2021nba` | NBA / NHL / MLB / NFL, 2016–2020 | log-scale HA parameter (Bayesian NB) | NBA ≈ 0.05, NHL ≈ 0.081 | NHL bubble Pr(β<0) = 0.95; NBA bubble declined; **MLB no meaningful change**; NFL confounded by a pre-existing downward trend | 5 seasons × 4 leagues | mixed; reduced in NBA/NHL bubble, null in MLB |
| `systematicreview_ghostgames` | football, 26 primary studies | vote count, not effect sizes | — | 6 no change · 2 slightly reduced · 8 reduced · 10 strongly reduced; **"not a single study that found an increased home advantage in ghost games"** | 26 studies (20 peer-reviewed) | mostly reduced |
| `wang2023crowdreview` | football, 28 articles | vote count by outcome type | — | 8 match-outcome studies, "most" supporting reduction, several null (notably lower leagues, and a Brazilian analysis finding **fewer** home wins in 2019 than in the spectator-free 2020) | 28 studies | mostly reduced, with dissent |

### 1b. Referee-behaviour outcomes

| study | sport / league | outcome | effect with fans | effect without fans | n | direction |
|---|---|---|---|---|---|---|
| `plosone_nhl_penalties` | NHL playoffs 2015–2020 | penalties called | away team penalised significantly more (Z = 4.02, p < .001) | **no difference** (Z = −0.43, n.s.); Home×Crowd **b = .186, p = .024** | 547 games (438 with crowd + 109 without) | home bias removed |
| `plosone_nhl_penalties` | NHL regular season 2019–2021 | penalties called | away penalised more (Z = 3.73, p = .001) | **no difference**; Home×Crowd **b = .101, p = .010** | 1,639 games (1,082 with + 557 without) | home bias removed |
| `plosone_nhl_penalties` | CHL regular season 2019–2021 | penalties called | same pattern | Home×Crowd **b = .095, p = .018** | 1,709 games (1,264 with + 445 without) | home bias removed |
| `leitner2021referees` | 8 European football leagues | yellow cards for fouls | baseline | **home teams +238 cards (+26.2%)**; away +28 (+2.8%); r = .309 | 1,286 matches | home bias removed |
| `gong2022nbafouls` | NBA 2017–2021, clutch time | correctness of foul calls (L2M reports) | — | **no significant difference** in referee treatment of home vs away between games with and without fans; only loose-ball fouls show any home bias (2.4%) | 1,679 games / 30,695 plays | **null** |

**Two things this table establishes that a one-line summary of the literature hides.**

1. **The literature is not unanimous.** `schank2024bundesliga` — the longest-horizon
   ghost-game study available, covering *all three* regulated Bundesliga seasons — finds
   home advantage in the full spectator-ban season 2020/21 "very close to" the pre-COVID
   season, i.e. a **null over a full empty-stadium season**, and a **non-monotone** (U-shaped)
   dose relationship in 2021/22. `wang2023crowdreview` records dissenting match-outcome
   studies. `gong2022nbafouls` is a **null on the referee-bias mechanism in the NBA**, in
   direct tension with `plosone_nhl_penalties` and `leitner2021referees`.
2. **The strongest reductions are concentrated in the first, short, dramatic window**
   (the last nine Bundesliga matchdays of 2019/20; European ghost games of spring 2020).
   The longer-window results are weaker. `schank2024bundesliga` reads this as teams
   becoming accustomed to empty stadiums. Our estimation window is a *full* restricted
   season per sport, which is the longer-window case.

### 1c. Methodological source: the NHL Elo specification (`paine_nhl_elo`)

Not a ghost-game study — this is the source that justifies two of our own modelling choices.
Neil Paine, *How My NHL Elo Ratings and Forecast Works* (October 2021), retrieved in full.

**Elo parameters**, adopted verbatim into `config/sports.yaml`:

| parameter | Paine | ours | note |
|---|---|---|---|
| K-factor | **6** | 6 | transfers directly; our `ln(\|MOV\|+1)` multiplier runs 86–95% of Paine's `0.6686·ln(MOV)+0.8048` over 1–5 goals |
| home-ice advantage | **50 Elo points** | 50 | used only inside the win-probability expectation, never fan-adjusted |
| season-to-season carryover | **70% retained**, 30% reverted | 0.70 | — |
| reversion target | **1505** | 1500 | **documented deviation** — we use a sport-blind 1500 across all four sports; worth ≈ 0.7 pp of win probability |

**The overtime/shootout finding**, which is the published justification for keeping ESPN's
final score unchanged on OT and shootout games rather than zeroing them or reverting to a
regulation-time outcome. Quoted exactly:

> "despite the prevailing wisdom that hockey becomes random as it progresses toward a
> shootout, our research found, for the purposes of Elo, no predictive power in
> differentiating between one-goal results in regulation versus overtime/shootouts — so a
> one-goal win in regulation gets a team the same number of Elo points as a win in overtime
> or a shootout."

This matters for Phase 8 because **41.5% of NHL games in our panel are one-goal games**
(`one_goal_share = 0.415`), so a referee will reasonably ask whether the ±1 censoring of
OT/shootout results distorts the NHL margin outcome. The honest answer has two parts: Paine's
finding is that the distinction carries no *predictive* information for team strength, which
supports leaving the scores alone; but it is evidence about prediction, not about whether
`home_margin` is the right outcome scale, so it is corroboration rather than proof. The
deferred shootout-zeroed sensitivity re-run recorded in `CLAUDE.md` remains the direct check
if anyone presses.

---

## 2. Where our estimates sit

The sharpest available like-for-like comparison is NBA points margin.

| quantity | with fans | without / reduced fans | drop |
|---|---|---|---|
| `ganz2024nbafans` (NBA, published raw means) | **+2.13** | **+0.44** | **−1.69** |
| **This study** (NBA, descriptive) | **+2.26** (pooled full-crowd seasons, SE 0.19) | **+0.92** (2021, the restricted season, SE 0.47) | **−1.34** |

Source for our numbers: `results/tables/descriptive_hfa.csv`, rows `nba / pooled_fullcrowd`
and `nba / 2021`, clean regular-season home games only.

**Both rows are raw descriptive means, not causal estimates** (corrected 2026-09-16 from the
primary source, Phase 8 finding Q9; an earlier version of this file called theirs an FE-IV
estimate). Ganz & Allsop's 2.13/0.44 are raw 2020–21 averages with and without fans, and they
call the gap only marginally significant (p = .09). Their causal estimates are +4.53 points for
fans allowed against none (FE, SE 2.07) and +1.74 per additional 1,000 fans (IV, SE 0.69); similar
effects for 1–3,000 and 3,000+ allowances point to presence rather than size. Their two rows both
come from 2020–21; ours compare normal seasons against a restricted one, so the drops are not
like-for-like, but our raw drop (1.34) and baseline (2.26) are not in conflict with theirs.

What differs is the **modelled** number: our TWFE NBA margin coefficient is **+0.91 (SE 0.96)**,
95% CI **[−0.98, +2.80]**. Mapping their +4.53 presence estimate into our per-unit-dose units
through presence shares (the paper's `lit-nba-vars` chunk, live) gives **+2.61**, or +2.42 if the
77 NBA 2021 games whose zero attendance we null as reporting artifacts are counted as
fans-present. Either sits at the upper edge of our interval; our point estimate is about a third
of it (35%), and our power against +2.61 is 77%. Two assumptions carry the mapping: a presence
rather than size effect, and generalization from sparse 2020–21 crowds to full-crowd seasons.

The same holds for the other sports' descriptive series (`results/tables/descriptive_hfa.csv`):
NFL 1.75 → 0.14 in 2020, NHL 0.254 → 0.262 in 2021, MLB 0.044 → 0.189 (2020) / 0.148 (2021). NFL's raw
drop is large; NHL's and MLB's are absent.

---

## 3. Are we underpowered relative to studies that found effects?

**Yes. Decisively, and in every sport.** This is the honest reading, and it is the finding
that should govern how Phase 8 states the conclusion.

Minimum detectable effect at 80% power, two-sided α = .05, is `MDE ≈ 2.8 × SE`.

### 3a. Win-probability outcome (the cross-sport comparable unit)

| sport | our pooled win% coef | SE | MDE at 80% power | prior effect size, same unit | can we detect theirs? |
|---|---|---|---|---|---|
| nfl | +0.0501 | 0.0378 | **10.59 pp** | `higgs2021nba` reports little-to-no NFL change, confounded by a pre-existing downward trend (it notes home advantage was *lower* in 2019 than in the COVID-adjusted 2020 season); log-scale, not convertible to pp | no convertible published effect to test against; 10.6 pp is 2× total NFL HFA |
| mlb | −0.0208 | 0.0156 | **4.36 pp** | `higgs2021nba` reports **no meaningful MLB change** | our null agrees with the only comparable published result |
| nba | +0.0064 | 0.0268 | **7.50 pp** | `ganz2024nbafans` +4.53 fans-allowed FE → **+2.61 pts** in our margin units (presence mapping, §2); no win-probability conversion | **Barely, in margin units:** at the upper edge of our margin CI [−0.98, +2.80], power 77% |
| nhl | +0.0107 | 0.0253 | **7.08 pp** | `plosone_nhl_penalties` reports **no outcome effect at all** (see §4) | no outcome effect published to compare against |

**No win-probability conversion.** An earlier version converted 2.13 → 0.44 into ≈4.65 pp via
Φ(μ/σ) with σ = 14.42. It is retired: that pair is a raw mean gap, not a causal estimate, so the
conversion compared unlike things. The only published NBA estimate mapped into our units is the
margin presence mapping in §2. Conversion is also **not** defensible for the football (soccer)
studies — draws break the binary outcome and the 3-1-0 points system is not a win
probability — so `leitner2021referees`' 0.61 → 0.11 *points per game* and
`schank2024bundesliga`'s effects are **left unconverted**; no conversion is invented for them.
`higgs2021nba` reports log-scale Bayesian parameters with no published point-margin or
win-probability translation, so it too is left unconverted.

### 3b. Points/goals-margin outcome — the more damning table

| sport | our pooled margin coef | SE | MDE at 80% power | our **total** measured HFA (pooled full-crowd) | MDE as multiple of total HFA |
|---|---|---|---|---|---|
| nfl | +1.928 | 1.165 | **3.26 pts** | 1.754 pts | **1.86×** |
| mlb | −0.180 | 0.160 | **0.449 runs** | 0.044 runs | **10.15×** |
| nba | +0.907 | 0.964 | **2.70 pts** | 2.261 pts | **1.19×** |
| nhl | +0.039 | 0.131 | **0.366 goals** | 0.254 goals | **1.44×** |

And on the win-probability side: nfl 2.04× · mlb 1.53× · nba 1.06× · nhl 1.85×.

**Denominators, so the ratios are reproducible.** "Total measured HFA" is the
`pooled_fullcrowd` row of `results/tables/descriptive_hfa.csv` for that sport: for the margin
outcome it is `mean_home_margin` directly; for the win-probability outcome it is
`home_win_pct − 0.5` (nfl .0520 · mlb .0284 · nba .0705 · nhl .0383). The ratio in each cell is
`(2.8 × se) / total_HFA`.

> **In all eight sport × outcome cells, the minimum effect this study could reliably detect is
> larger than the entire home advantage that exists in that sport — the smallest margin (NBA win
> probability) by 6%.** At per-unit scaling, a crowd effect accounting for **100% of home-field
> advantage** would sit at or beyond the 80%-power detection threshold in every cell — but the
> rescaling caveat immediately below moves three of them to ≈1.0 or below (one strictly inside
> the threshold, two sitting on it).

Two reasons the claim is stated with its basis rather than as a clean sweep. First, the narrowest
cell — NBA win% at **1.06×** — clears one by 6%, well inside the precision of these estimates.

Second, and more seriously: **the coefficient is scaled per unit of `crowd_pct`, and no sport's
data spans a full unit.** Measured on the exclusion-filtered estimation panel, control-season mean
`crowd_pct` is nfl **.97** · mlb **.65** · nba **.92** · nhl **.92**, against treated-season means
of .069 · **.322** · .080 · .069. MLB is the outlier in both columns: under this study's Option-A
empirical-capacity definition, announced MLB attendance never approaches the stadium-season
maximum, so a normal MLB season averages .64–.69 dose and only 17% of its games exceed 0.9.
Rescaling each MDE to its own sport's realised contrast (a crowd effect explaining 100% of HFA
implies β = HFA ÷ control-crowd level) gives:

| rescaled MDE ÷ total HFA | margin | win% |
|---|---|---|
| nfl | 1.81× | 1.98× |
| mlb | 6.64× | **1.00×** |
| nba | **1.10×** | **0.98×** |
| nhl | 1.33× | 1.70× |

**Three cells land at ≈1.0 or below** — nba win% 0.98, mlb win% 1.00, nba margin 1.10 — and nhl
margin falls 1.44 → 1.33. The all-eight statement is therefore correct **at per-unit scaling**
and is **not** robust to rescaling; five cells survive comfortably, three do not. Phase 8 must
state which scaling the ratio uses and must not assert that the conclusion is unchanged by it.

It follows that **MLB's headline `crowd_pct` coefficient extrapolates about 1.5× beyond the dose
MLB typically attains** — it reads a 0→1 contrast off an empty→typical-full contrast of 0→.65.
This is the same support-range caveat already carried for the NHL within-2021 dose regression
(§3c), and until now it had never been applied to MLB's *headline* estimate, where it belongs.

The power statement in the blockquote above — under either scaling — is the correct reading of
what these nulls mean. It is not a hedge; it is the arithmetic. It also explains why our NBA CI reaches the mapped Ganz & Allsop
estimate: their design has both a larger effective sample for the treatment contrast
(within-season, game-level attendance variation across venues in 2020-21) and an IV strategy
targeting exactly that variation, while ours identifies off a **between-season** contrast
with **team-clustered** standard errors over 30 clusters.

### 3c. Why the published designs have more power than ours

- **Ganz & Allsop use within-2020-21 attendance variation** with an instrument. Our design
  deliberately does **not** lean on within-season dose, because within-normal-season crowd
  size is demand-driven (good teams draw crowds *and* win) — the endogeneity the whole
  design exists to dodge. We paid for that identification choice in power. The NHL
  within-2021 dose regression documented in `CLAUDE.md` (coefficient wrong-signed,
  p = .04–.11, fitted support 0–0.40) is exactly why we did not take that route.
- **Clustering.** Our SEs cluster by home team (30–33 clusters). Several published studies
  use unclustered or match-level inference, which produces much smaller SEs for the same data.
- **The football studies pool many leagues.** `leitner2021referees` has 1,286 matches across
  8 leagues in one estimate; the reviews aggregate 26–28 studies. Our unit of analysis is a
  single league.

### 3d. What this does *not* license

- It does **not** license "our data contradict the published literature". They do not; our
  per-sport intervals are wide enough to contain the published effect sizes.
- It does **not** license any statement of the form "the pooled CI rules out effects larger
  than X". The four sports share a **bias** — each estimate is *crowd effect + that league's
  2020–21 non-crowd home-specific shift* — not merely independent noise. Inverse-variance
  pooling shrinks sampling error and does nothing to a bias common to all four (same
  pandemic, same schedule compression, same empty buildings). Any pooled SE is a **lower
  bound** on real uncertainty.
- It does **not** license reading the low cross-sport heterogeneity as evidence of a common
  effect. At k = 4 the heterogeneity test has no power. And there are substantive reasons
  (see the MLB discussion in `CLAUDE.md`) to expect the true effects to differ by sport.
- No sport's result should be described as a "clean null". Each is **underpowered and
  indistinguishable from zero**, which is not "near zero": NFL's estimate is ~96% of its own
  win-probability HFA per unit of `crowd_pct`.

---

## 4. Mechanism vs outcome — the NHL case

`plosone_nhl_penalties` (Guérette, Blais & Fiset 2021) is the closest published work to our
NHL result, and it is often summarised as "fan absence removes NHL home advantage". Read
precisely, that is not what it measures.

**What they found.** In three independent samples — NHL playoffs 2015–2020 (547 games: 438
with crowd, 109 without), NHL regular season 2019–2021 (1,639 games: 1,082 with, 557 without),
CHL regular season 2019–2021 (1,709 games: 1,264 with, 445 without) — away teams received
significantly more penalties than home teams **when crowds were present**, and **no
significant difference when they were absent**. The Home × Crowd interaction is significant in
all three (**b = .186, p = .024** / **b = .101, p = .010** / **b = .095, p = .018**). Model
variance explained is 8–11%.

*Transcription note.* The playoffs interaction is reported **inconsistently within the paper
itself**, not between renderings: the prose says **b = .17**, while the paper's own regression
table gives **b = .186, SE .083, z = 2.254, p = .024**. Both values appear in both the PMC
(PMC8378689) and PLOS ONE renderings, so this is an internal inconsistency in the source, not
a transcription or hosting artifact. **The regression table is authoritative**, so `b = .186`
is the value used here and the one Phase 8 should quote. Note also that for this row `.17` is
not a rounding of `.186` (which rounds to `.19`) — unlike the two sibling rows, where the
prose value ".10" does round correctly from `.101` and `.095`.

**What they explicitly did not measure.** The paper analyses **penalty calls only**. It does
not analyse goals, margins, or wins, and it makes no claim that the penalty differential
translated into home victories.

**Therefore the two results are compatible, not contradictory.** Their finding is at the
*mechanism* level (referee behaviour); ours is at the *outcome* level (goal margin, win
probability). A referee-bias channel can switch off without moving win probability
detectably, for two reasons that both apply here:

1. **The channel is small relative to outcome noise.** NHL total home advantage in our data
   is **0.254 goals per game** (SE 0.033) against a per-game margin SD of 2.56 goals. Our
   NHL margin MDE is 0.366 goals — larger than the entire home advantage (§3b). A penalty
   differential would have to be worth more than the whole of NHL HFA before our design
   could see it.
2. **Penalties are one of several channels**, and the others (travel, familiarity, last
   change / line matching, rest) survive an empty arena unchanged.

**The precise Phase 8 wording**, which should be used more or less verbatim:

> Our NHL outcome null is consistent with Guérette et al. (2021) at the level each study
> measures. Their mechanism finding — that home-favouring penalty calls disappear without
> a crowd — stands, and we do not test it. Our estimate is of the crowd's effect on the
> *result*, where the minimum effect we could detect (0.37 goals) exceeds the entire NHL
> home advantage (0.25 goals). We are unable to distinguish a zero crowd effect on results
> from one large enough to account for all of NHL home advantage.

The same mechanism-vs-outcome distinction cuts the other way in basketball: `gong2022nbafouls`
finds **no** crowd effect on NBA referee accuracy in clutch time (1,679 games, 30,695 plays),
while `ganz2024nbafans` finds a large crowd effect on NBA *outcomes*. Mechanism and outcome
findings do not track each other reliably in this literature, in either direction. Phase 8
should say so, and should be careful not to present the referee-bias channel as the
established explanation.

---

## 5. Claim verification (Workstream C3)

Three claims currently asserted as fact in `CLAUDE.md`, each checked against a source.

### 5.1 NHL 2020-21 four-division realignment with an all-Canadian North Division — **VERIFIED**

Cite `nhl2020realignment` (NHL.com, 21 December 2020). The NHL realigned its 31 teams into
four divisions for 2020-21: **East** (BOS, BUF, NJD, NYI, NYR, PHI, PIT, WSH), **Central**
(CAR, CHI, CBJ, DAL, DET, FLA, NSH, TBL), **West** (ANA, ARI, COL, LAK, MIN, SJS, STL, VGK),
and **North** — **Montreal, Calgary, Edmonton, Ottawa, Toronto, Vancouver, Winnipeg**, i.e.
**all seven Canadian teams**. Teams played 56 games, in-division only, starting 13 January 2021.

**One caveat to word carefully.** The NHL.com article confirms the *structure* but does not
itself state cross-border travel restrictions as the *reason*; it says only that the season
was delayed over coronavirus concerns. The all-Canadian grouping-to-avoid-border-crossings
rationale is universally reported but was not confirmed in this primary source. Phase 8
should state the structure as fact (cited) and the rationale as the widely-reported motive,
or find a source in which the league states the reason. Either way the **travel diagnostic's
justification survives**: a division-only 56-game schedule with all Canadian teams in one
division mechanically changes the travel distribution in 2021, which is exactly what the
diagnostic was built to check — and the diagnostic came back showing
`corr(crowd_pct, away_travel_km | 2021) = −0.143`, i.e. weak.

> **Superseded C1 (2026-09-21):** §§5.2–5.3 now cite `nhl2020hubratify` (hubs, Aug 1) instead of Wikipedia. The "presentation customised for the designated home team" detail below is NOT supported by any league source and was removed from the paper; see `docs/paper-writing-guide.md` §Citations.

### 5.2 Toronto and Edmonton played bubble games in their own arenas — **VERIFIED**

Cite `wikipedia2020stanleycup`. The 2020 Stanley Cup playoffs used two hub cities:
**Toronto (Scotiabank Arena)** for the Eastern Conference early rounds and **Edmonton
(Rogers Place)** for the Western Conference. The Toronto Maple Leafs played their qualifying
round at Scotiabank Arena — their own home building — and the Edmonton Oilers played theirs
at Rogers Place, likewise their own building.

Two further details that matter for how the bubble subsection is worded, from the same source:
the higher seed was the **designated home team** for scheduling purposes, and in-arena
presentation was **customised for the designated home team** (goal music and similar). This
corroborates the point already in `CLAUDE.md` that the bubble is not a clean zero for a
placebo: "home" designation carried real conventions even inside the hub.

*Wikipedia is a tertiary source.* It is adequate for uncontroversial scheduling facts, but if
Phase 8 leans on this claim in an argumentative way, replace it with an NHL.com or league
release citation.

### 5.3 Bubble hub dates, 1 August – 28 September 2020 — **VERIFIED**

Cite `wikipedia2020stanleycup`. Qualifying round began **1 August 2020**; the final game
(Stanley Cup Final Game 6) was **28 September 2020**. This matches the `is_bubble` date rule
in `src/data/nhl.py` (`season == 2020 & date >= 2020-08-01`) exactly at the lower bound, and
the upper bound is inside the season-2020 window, so the rule as written is correct.

Recall the correction already recorded in `CLAUDE.md`: only 72 of 130 bubble games carry
ESPN's `neutral_site = True`, so **the date rule is load-bearing** and the bubble subsection
must filter on `is_bubble`, never on `neutral_site`.

**Verdict: all three claims verified. None needs to be cut from the write-up.** The single
piece of hedging required is on the *rationale* for the North Division in §5.1.

---

## 6. Summary for Phase 8

1. The literature is predominantly, but **not** unanimously, in favour of a crowd effect on
   match results (`systematicreview_ghostgames`, `wang2023crowdreview`,
   `leitner2021referees`, `ganz2024nbafans`) — with a notable full-season null in
   `schank2024bundesliga` and an MLB null in `higgs2021nba`.
2. Our **descriptive** NBA numbers (2.26 → 0.92) are close to their published raw means
   (2.13 → 0.44, gap p = .09; not a causal estimate). Our data do not look different from theirs; our *modelled* estimate is
   less precise.
3. **Power dominates what can be concluded.** At **per-unit `crowd_pct` scaling**, in seven of
   eight sport × outcome cells our MDE at 80% power exceeds the total home advantage in that
   sport, and in the eighth it exceeds it narrowly (6%). Rescaled to each sport's realised crowd contrast three
   cells fall to ≈1.0 or below, so **state the scaling basis whenever this claim is used** and do
   not assert it is unaffected by the choice (§3b). Where a published effect exists in a
   convertible unit — NBA only — our interval
   reaches it, at its upper edge, in margin units (§2). The honest claim is that this study
   cannot distinguish a zero crowd effect from a crowd effect accounting for all of home-field
   advantage — not that it found no effect, and not that it contradicts the literature.
4. Our NHL outcome null and `plosone_nhl_penalties`' NHL penalty finding are **compatible**;
   they measure different things. `gong2022nbafouls` shows mechanism and outcome findings do
   not track each other reliably in either direction.
5. All three C3 claims verified; `references.bib` has 12 entries; `CLAUDE.md`'s "Higgs &
   Stavness 2.13 → 0.44" attribution must be corrected to Ganz & Allsop (2024).
