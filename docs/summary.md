# Empty stadiums, and what they can't tell us

*A short summary of [the paper](../paper/hfa.pdf). About a five-minute read.*

## The question

Home teams tend to win. In the full-crowd regular seasons of 2018–2023, the home side took 55.2% of
NFL games, 57.0% of NBA games, 53.8% of NHL games and 52.8% of MLB games. That the advantage exists
is not in doubt. Where it comes from is, because the crowd, the absence of travel and familiarity
with the building always arrive together.

The 2020–21 COVID restrictions pulled one of those apart. For one season (two in baseball), games
were played in empty or capacity-capped buildings while home teams still slept at home and played
on their own field. If the crowd is worth a real share of home advantage, that share should have
gone missing.

## What was built

- **One panel.** 30,146 games across all four leagues, sourced from ESPN's public endpoints and
  normalized into a single game-level schema. League-specific code lives only in the loaders;
  everything downstream is written once.
- **A per-game crowd dose.** Announced attendance divided by the venue's highest announced
  attendance that season. A typical normal-season game sits at 0.92–0.97 in football, basketball
  and hockey, and at 0.65 in baseball. Restricted seasons averaged 0.065–0.079 outside baseball.
- **Two estimators, side by side.** A team fixed-effects dose-response regression with a linear
  season trend and controls for team strength (Elo), rest and travel; and a raw comparison of home
  advantage in normal versus restricted seasons, with the away team as the implicit control.

## What came back

Estimated effect on home win probability of going from an empty stadium to a full one (95% CI):

| NFL | NBA | NHL | MLB |
|---|---|---|---|
| +0.050 [−0.024, +0.124] | +0.006 [−0.046, +0.059] | +0.011 [−0.039, +0.060] | −0.021 [−0.051, +0.010] |

![Crowd effect on home advantage by league, with 95% confidence intervals](../results/figures/twfe_crowd_effect.png)

Every interval crosses zero. The NFL's, the only large point estimate, falls to +0.013 when the
2018 season is left out.

## The finding is a ceiling, not a null

The useful question is not whether these estimates are significant. It is whether this design could
have seen a crowd effect if one were there, and mostly it could not. In all eight league × outcome
cells (win probability and scoring margin), the smallest effect detectable at 80% power, per unit of
crowd dose, is larger than that league's *entire* home advantage. The closest cell, NBA win
probability, is over by 6%. Rescaled to each league's normal-season dose, three cells come down to
roughly one or below, so the claim is about order of magnitude: the design's resolution is about as
coarse as the whole quantity it is trying to decompose.

The reason is that the treatment hit seasons, not games. Between 1,452 and 12,768 games per league
make the standard errors look small, but the pandemic arrived league-wide, once. Two things follow.

- **Randomization inference has a hard floor.** Re-running the model with each season in turn
  labeled as the treated one cannot produce a p-value below 0.167 with six seasons (0.200 for MLB).
  No result from this design could reach conventional significance on that basis.
- **Ordinary seasons move as much as the pandemic did.** NFL home margin deviated +3.70 points from
  trend in 2018 and −1.80 in 2020. Genuine season-to-season variation in NFL home margin is 1.73
  points, essentially the whole 1.75-point advantage. More control seasons would not fix this: on a
  season-level basis, the detectable effect stays above the whole home advantage in seven of eight
  cells. The one exception, MLB win probability (0.88×), is a lower bound.

## Baseball ran a different experiment

In the NFL, NBA and NHL, under 0.6% of normal-season games had a crowd dose resembling a restricted
game. In MLB, 74.6% did, all of it from 2021, when parks partially reopened. 2020 is clean on dose
but brought the extra-innings ghost runner, the universal designated hitter and seven-inning
doubleheaders. No definition of baseball's treatment is clean on both counts, so MLB is an
identification problem before it is a power problem. The claim that holds is "no detectable MLB
crowd effect", not "crowds don't matter in baseball".

## Against the published literature

The one published causal estimate that can be mapped into these units, Ganz and Allsop's (2024) NBA
fan-presence effect, maps to +2.61 points, at the upper edge of our NBA margin interval (−0.98 to
+2.80). Our point estimate is about a third of theirs. That is a statement about our precision, not
a confirmation of their finding.

## What the design cannot do

The estimate is the crowd effect plus anything else home-specific that changed in 2020–21:
compressed schedules, testing protocols, altered travel and, in baseball, rule changes. Nothing
inside the model separates them. The NBA bubble looked like a way out and is not one; its placebo
interval contains both zero and the NBA's full home advantage. The study was not pre-registered. The
one change to the main specification, and every analysis added after the results were known, are
disclosed in the paper.

## The general lesson

For anyone using the pandemic as a natural experiment: when the treatment is one season-level shock,
a clustered p-value over thousands of games is computed over the wrong denominator. Check the
season-level noise floor first.

[Full paper (PDF, 28 pages)](../paper/hfa.pdf) · [Code and reproduction steps](../README.md)
