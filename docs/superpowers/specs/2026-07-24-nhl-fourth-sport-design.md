# NHL as a 4th sport — design

**Date:** 2026-07-24
**Status:** approved (brainstorm complete, awaiting implementation plan)
**Supersedes:** the "Maybe-later: Add NHL as a 4th sport" note in `CLAUDE.md`

---

## 1. Why NHL, and why now

The study's main weakness is **wide, zero-crossing per-sport confidence intervals**
(Phase 6a/6b: NFL margin +1.71 [−0.53, 3.95]; NBA +1.06 [−0.70, 2.81]; MLB null).
More *seasons* cannot fix this — the treated games are fixed by history. The only
lever is **more independent replications of the same natural experiment**, which
tightens the pooled cross-sport estimate.

NHL fits the existing architecture almost for free: 31 stable teams (32 from season
2022, when Seattle enters — team FE + Elo hold either way), indoor like NBA (weather
null), a clean empty→partial 2020–21 shock, and the
same ESPN scoreboard + summary endpoints `_espn.py` is already parameterised for.

**What this buys:** precision and generalisability. **What it does NOT buy:**
cleaner identification. The crowd-vs-other-2020–21-shifts confound is the same
pandemic hitting every league; a fourth sport does not disentangle it.

**NHL is the last structurally cheap sport.** The remaining candidates fail on
*ex ante structural* grounds, not on their results:

| Sport | Why excluded |
|---|---|
| Soccer / MLS | Draws break the binary outcome; promotion/relegation breaks the team panel |
| WNBA | 2020 was *entirely* a bubble (Bradenton) — the empty-with-travel regime does not exist; ~12 teams × ~32 games |
| NCAA FB/BB | Hundreds of unstable rosters break team FE + Elo; different data source; a separate study |

Recording these here matters: sport selection must be defensible as
outcome-independent (see §2).

---

## 2. Pre-commitments (fixed BEFORE the data pull runs)

Written down in advance so sport selection and specification cannot be
outcome-dependent:

1. **NHL appears in the cross-sport table and the pooled estimate regardless of
   sign, magnitude, or significance.**
2. **No sport is dropped post hoc.** MLB's null result stays in the paper; so will
   NHL's, whatever it is.
3. **The Phase 6a specification is frozen.** NHL gets no bespoke tuning, no
   alternative FE structure, no per-sport control set.
4. **The travel diagnostic in §7 is reported either way** — small movement and
   large movement are both publishable findings.

Rationale: the project's real bias exposure is not sport selection but
**specification search**. Phase 6a changed the FE specification after seeing all
twelve coefficients come back negative. That change was justified on collinearity
grounds and is documented — but it is exactly what a skeptical reader flags. A
pre-registered commitment for the new sport is cheap insurance.

---

## 3. Spike results (verified 2026-07-24, not assumed)

ESPN `hockey/nhl` was spiked before any design work, mirroring the NFL/MLB/NBA
spikes. **PASS on every requirement.**

| Check | Result |
|---|---|
| `gameInfo.attendance` present | ✅ 2019 full (~16–19k), 2022 normal |
| Empty games are REAL `0`, not null | ✅ (the failure mode that disqualified `pybaseball`) |
| `venue.capacity` | `None` — same as all three sports → Option A empirical capacity applies unchanged |
| Bubble detection | ✅ ESPN sets `neutralSite=True` for the 2020 Toronto/Edmonton bubble (MLB behaviour, not NBA's) |
| Per-event season year | ✅ `ev["season"]["year"]`, already read by `walk_scoreboard` (`_espn.py:146`) |
| OT vs shootout distinguishable | ✅ `status.period` = 3 / 4 / 5 and `status.type.detail` = `Final` / `Final/OT` / `Final/SO` |

**Within-season dose variation exists.** Season 2021 shows 0, 2,554 (ARI), 3,882
(PHI), 5,040 (FLA) — genuine staggered state-policy caps. Tempering note: NFL 2020
also had staggered caps and its within-season dose↔margin correlation came out
≈ −0.03, so the *variation* existing does not imply *signal*. Treat a within-season
dose curve as a question the data may answer, not an expectation.

**Season labelling — end year, same as NBA:**

| `season_year` | Real season | Crowd state |
|---|---|---|
| 2020 | 2019–20 | full through Mar 2020, then Aug–Sep bubble playoffs (`type=3`, `neutralSite=True`) |
| **2021** | **2020–21** | **Jan–Jul 2021, empty/capped — the treatment** |
| 2023 | 2022–23 | normal |

---

## 4. Settled design decisions

### 4.1 Outcome handling: final scores as-is

NHL has no ties. Tied games go to 3-on-3 overtime, then a shootout; the winner is
credited one goal. Consequences: `home_margin` is **censored at ±1** for all OT/SO
games, and `home_win` counts shootout wins as wins.

**Decision: use ESPN final scores unchanged.** No adjustment, no exclusion, no
schema change.

Rationale:

- The unit of analysis is "did the home team win the game," which is what the
  league records.
- Shootout dilution is **symmetric** — it attenuates toward zero, it does not bias
  the sign. That is a power cost we report, not a distortion.
- Excluding shootouts is **dominated**: if shootouts are coin flips, including them
  costs only mild attenuation; if the crowd *does* help at home in a shootout,
  excluding them discards real signal *and* the shootout share of N. Including
  cannot lose on that axis.
- Zeroing shootout margins would improve the margin outcome only marginally
  (swapping a coin-flip ±1 for a 0 in ~1 game in 10, a few percent off the margin
  SE) while costing the same share of the *strong* outcome — trading down.

⚠️ The "~10%" shootout share is an estimate, not a verified figure — 3-on-3
overtime (introduced 2015–16) cut shootout frequency substantially from its earlier
level. **Measure the actual share from the pull** (`status.period == 5`) before any
number goes in the write-up.

**Citable corroboration.** FiveThirtyEight's NHL Elo model tested exactly this and
found **"no predictive power in differentiating between one-goal results in
regulation versus overtime/shootouts"** — their model credits an OT/SO win
identically to a regulation one-goal win.
Source: [Neil Paine — how my NHL Elo ratings and forecast work](https://neilpaine.substack.com/p/how-my-nhl-elo-ratings-and-forecast).
Cite this in Phase 8 as the justification.

**Accepted cost, documented not engineered around:** NHL `home_margin` will be the
weakest outcome in the study — small integer scale *and* ±1 censoring. Expect NHL
to behave like MLB: **win% is the real signal, margin is noise.**

### 4.2 Season 2021 is INCLUDED (it is not a bubble)

The 2020–21 season is the treatment, not a second bubble. The distinction is home
park:

| Regime | Crowd | Travel | Home park |
|---|---|---|---|
| Normal seasons | yes | yes | yes |
| **NHL 2021** | **no/reduced** | **reduced** | **yes — intact** |
| Bubble | no | none | neutral |

Teams played in their own arenas — own ice, own locker room, own bed, own routine,
last change. The bubble removes all three ingredients; NHL 2021 removes crowd,
reduces travel, and keeps home park. It is row 2 of the spec's own three-regime
table: the treatment the study exists to exploit.

**The modelling consequence:** in the bubble, travel is exactly **zero for every
game** — no variation, nothing to control with, exclusion is the only option. In
NHL 2021 travel **varies game to game**, so it is a *controllable* confound rather
than an excludable one. That is the difference between a constant and a variable.

### 4.3 The 2021 travel confound is real and gets measured, not assumed

The 2020–21 season ran realigned regional divisions including an all-Canadian
division with no cross-border travel, so crowds and travel fell together. This is
the most severe instance in the study — but not a new *class* of problem: **MLB
2020 ran a regional 60-game schedule** for the same reason and is already logged as
an MLB confound. Every league's COVID season reduced travel somewhat.

Handling: control for `away_travel_km` (already sport-blind) **plus an explicit
diagnostic** (§7). ⚠️ The four-division realignment and the all-Canadian division
need a real citation in Phase 8, not recollection.

### 4.4 Elo parameters — web-verified

538's own NHL methodology page is dead (301s to ABC News). Parameters recovered
from Neil Paine, who built that model:

| Param | 538 value | Our config |
|---|---|---|
| K | 6 | `k: 6` |
| Home ice | 50 Elo points | `hfa: 50` |
| Carryover | retain 70%, revert 30% toward 1505 | `carryover: 0.70` |

**K needs no rescaling.** 538's NHL MOV multiplier is `0.6686·ln(MOV) + 0.8048`;
ours is `ln(|margin|+1)`. Across the realistic 1–5 goal range ours runs 86–95% of
theirs — close enough to transfer K directly. This is the NFL/MLB case, not the NBA
case where 538's normalised formula forced halving K.

**Documented deviation:** 538 reverts NHL toward **1505**; our implementation uses a
sport-blind **1500**. The gap is 5 Elo points ≈ 0.7pp of win probability. Keeping
1500 preserves sport-blindness; the deviation is noted rather than special-cased.

### 4.5 Downstream integration: add `"nhl"` to the four hardcoded lists

```
src/features/build.py:156   for sport in ("nfl", "mlb", "nba")
src/viz/descriptive.py:17   SPORTS = ["nfl", "mlb", "nba"]
src/models/twfe.py:28       SPORTS = ["nfl", "mlb", "nba"]
src/models/did.py:25        SPORTS = ["nfl", "mlb", "nba"]
```

Four one-word edits plus a fourth `SPORT_COLORS` entry — the new colour must stay
distinguishable from the existing three under colour-vision deficiency, since both
figures encode sport by line colour. **Rejected:** deriving the
list from `config/sports.yaml` keys — speculative DRY for a list that changes
roughly never (NHL is the last sport, §1), and it silently changes behaviour if a
non-sport top-level key is ever added to the config.

---

## 5. File inventory

**New**
- `src/data/nhl.py`
- `tests/test_nhl_loader.py`

**Modified**
- `src/data/_espn.py` — one entry: `SPORT_PATH["nhl"] = "hockey/nhl"`
- `config/sports.yaml` — nhl block
- `config/venue_coords.yaml` — 32 NHL team entries
- `src/features/build.py`, `src/viz/descriptive.py`, `src/models/twfe.py`,
  `src/models/did.py` — sport list + colour + the §7 diagnostic

**Regenerated**
- `data/interim/nhl.parquet`, `data/processed/nhl.parquet`
- All of `results/tables/` and both `results/figures/` PNGs
- CLAUDE.md headline numbers (the existing three-sport figures become four-sport)

⚠️ **NHL is not additive to existing results — it invalidates them.**
`twfe_cross_sport.csv`, `did_cross_sport.csv`, `descriptive_hfa.csv`, both figures,
and the pooled win-probability estimate all change.

---

## 6. The loader (`src/data/nhl.py`)

Mirrors `nba.py`. Structure: `_select_games` → `_build_panel` → `load` / `main`
with `--smoke`.

### 6.1 Scoreboard walk

Continuous walk (NHL seasons span two calendar years), filtered by ESPN
`season_year`. Window must be generous at **both** ends:

```
[date(min_season - 1, 9, 1), date(max_season, 9, 30)]
```

Season 2020's playoffs ran into late September 2020 (the bubble); season 2021 ran
January–July 2021. A November cutoff (NBA's) would silently truncate both.

### 6.2 `_select_games`

Keep `season_type ∈ {2, 3}`, `status == STATUS_FINAL`, non-null scores.

⚠️ **Known trap — All-Star leak.** Phase 4 found ESPN types All-Star games as
`season_type=2`, so they slipped the `{2,3}` filter in *both* MLB and NBA with fake
team abbreviations, requiring both parquets to be regenerated. NHL runs an All-Star
tournament with divisional rosters. The exclusion goes in from the start, with a
test.

### 6.3 `relocated_home` — modal-venue rule (the only novel logic)

```
relocated_home = venue_id != (modal venue_id for that (home_team, season))
```

Modal venue = `value_counts().idxmax()` within each `(home_team, season)` group —
deterministic on ties, and a tie cannot occur in practice (an NHL team plays ~41
home games in its own arena versus at most a handful elsewhere).

Three lines. Catches, automatically and without maintenance:

- **Outdoor games** — Winter Classic, Stadium Series, Heritage Classic (~2–4 per
  season). The designated home team is in a football or baseball stadium, so
  home-park advantage is broken exactly as in MLB's Buffalo relocation.
- **NHL Global Series** — regular-season games in Sweden, Finland, and Czechia in
  several of our seasons.
- Any arena relocation or renovation displacement we have not enumerated.

**Rejected: dropping these games at load.** Detection is required either way (you
cannot drop what you cannot detect), so dropping saves no code — it only replaces
`relocated_home = True` with a filter. Flagging matches how MLB `(TOR, 2020)` and
NBA `(TOR, 2021)` are already handled, keeps `load() -> (panel, dropped)` meaning
"unusable rows" rather than "usable rows we chose to exclude," and preserves an
auditable count. `relocated_home` is already in `_exclusion_mask`, so flagged games
are excluded from every model regardless. **Flag and drop produce identical model
results**; flagging preserves information.

**Rejected: a hardcoded list of outdoor games** — ~20 entries to research and
maintain, error-prone, and it misses the Global Series and anything unenumerated.

Capacity is unaffected: `derive_capacity` keys on `(venue_id, season)`, so a
68,000-seat stadium gets its own capacity row instead of corrupting the home
arena's.

### 6.4 `is_bubble`

```
is_bubble = (season == 2020) & (date >= 2020-08-01)
```

Every season-2020 game after 1 August 2020 was a bubble game. One line.

The 2020 bubble was real and strict: **1 Aug – 28 Sep 2020**, two sealed hub cities
(Toronto for the Eastern Conference, Edmonton for the Western), 24 teams entering
straight into playoffs after a four-month pause.

These games are *already* excluded via ESPN's `neutralSite=True` flag, so
`is_bubble` is **purely optional bookkeeping** — one free line that preserves the
option of using them later.

⚠️ **Honest limit — NHL's bubble does NOT strengthen the Phase 8 subsection.**
Every NHL bubble game is typed `season_type=3` (playoffs), which rules out both
existing uses:

- **Not the seeding placebo** — that requires `is_playoff == False`, games where
  "home" is a schedule label uncorrelated with quality. NHL has none. The nearest
  analog (a three-game round robin among the top four seeds per conference, ~12
  games) is both tiny and typed as playoffs. The placebo stays **NBA-only at n=88**,
  CI ≈ [−1.0, +4.3].
- **Not the decomposition table** — its other rows are regular-season. Phase 5
  excluded playoffs from descriptive HFA precisely because playoff home teams are
  the better seed, so HFA blends with quality asymmetry. A playoff-only bubble row
  beside regular-season rows is apples to oranges.

**The one legitimate use, if Phase 8 wants it:** a playoff-vs-playoff contrast
within NHL — normal playoffs (2018, 2019, 2022, 2023) vs 2021's partial-crowd
playoffs vs the 2020 bubble — holding playoff-ness and seeding structure constant
across all three rows. Better constructed than the NBA comparison, but a *different*
analysis and strictly optional. Not planned here.

⚠️ Also not fully neutral: Toronto and Edmonton played their qualifying-round games
**in their own arenas** (Scotiabank Arena, Rogers Place). Both were eliminated in
that round, so it is ~9 games — but verify before any "neutral venue" claim reaches
the paper.

See the Phase 7 cancellation decision: the bubble is a hedged write-up subsection,
not an identification strategy.

### 6.5 Other columns

- `is_dome = True` unconditionally, weather null. Outdoor games are a documented
  approximation, inert because they are flagged `relocated_home` and excluded, and
  because the schema's dome rule (`is_dome ⇒ weather null`) is forward-only.
- `closing_spread = null` — the puck line is a fixed ±1.5 and carries no team-quality
  signal. Same reasoning as MLB's moneyline decision.
- `home_rest_days`, `away_rest_days`, `away_travel_km`, `elo_*` — null / 1500.0
  placeholders filled by `src/features/build.py`, exactly as all three existing
  sports.

---

## 7. The travel diagnostic

Follows the existing NFL `closing_spread` sensitivity pattern at `twfe.py:151-153`
— same shape, same output table, **no new module**.

1. Report `corr(crowd_pct, away_travel_km)` within NHL's treated season (2021).
2. Refit NHL dropping `away_travel_km`; report how far the crowd coefficient moves.

**Interpretation fixed in advance (§2.4):** small movement earns the right to state
the confound is empirically minor. Large movement is reported as "NHL's crowd
estimate is not separable from the 2021 travel shock." Both are findings.

---

## 8. Testing and gates

`tests/test_nhl_loader.py`, mirroring the MLB/NBA suites:

- `_select_games` filters season type, non-final status, null scores
- **All-Star exclusion** (regression test for the Phase 4 bug class)
- `_build_panel` output passes `validate()`
- Shootout games retain their ESPN final score (guards §4.1 against future drift)
- Modal-venue rule flags an off-venue game and leaves normal games alone
- `is_bubble` date boundary

`test_coords_cover_every_panel_team` picks up NHL automatically once the parquet
exists.

**Elo accuracy gate — expectation stated up front to prevent a false alarm:** NHL is
*expected* to land near **0.57–0.58**, below NFL (0.627) and NBA (0.639), because
hockey is the least predictable of the four sports. This band is an a-priori
estimate, not a verified benchmark — anything in it (or moderately below) **is a
PASS**, and the band is not a target to tune toward. The bug threshold is
`< 0.52`. **No K-tuning** — Elo is a control variable, and tuning it to hit a target
is forbidden by the Phase 4 decision.

---

## 9. Runtime and storage

- ~1,300 games/season × 6 seasons ≈ **7,900 summary fetches** plus ~1,500 scoreboard
  days.
- **Hours of wall clock**, likely requiring a cache-warming re-run. `_cached_get`
  already handles ESPN's soft rate limiting with retry, capped backoff, and jitter;
  the cache is immutable and write-once, so a pull is self-completing across re-runs.
- **~8 GB** additional immutable cache in `data/raw/nhl/espn/` — relevant to the
  standing decision to delete ESPN caches near project end (gitignored, local-only,
  so a fresh clone re-fetches).

---

## 10. Deferred (explicitly not load-bearing)

- **Shootout-zeroed margin sensitivity** — re-run NHL margin with `period == 5`
  games set to 0. A few lines against the built panel; available if anyone
  questions the ±1 censoring.
- **Regulation-time outcomes** — the fuller alternative (OT/SO games become margin
  0, `home_win` null). Rejected as primary in §4.1.

---

## 11. Open risks

1. **NHL may replicate MLB's null.** Then the pooled estimate becomes *more precise
   but not more conclusive*. That is a legitimate outcome — a fourth independent
   replication reporting "small and uncertain" is information — and §2 commits us to
   publishing it either way. Worth knowing we are buying precision, not an answer.
2. **The modal-venue rule reclassifies silently.** Mitigated by the count being
   reported at load and a unit test; a count materially above ~20–30 across six
   seasons signals a data problem rather than a real relocation.
3. **Seattle enters in season 2022** (post-treatment) at the default 1500 Elo.
   Harmless — team FE absorb it — but it means one team contributes no pre-treatment
   observations.
4. **Season 2020 is truncated** (regular season stopped 11 March 2020), so it
   carries fewer games than a normal season. Expected, not a bug.
