# Phase 4 — Sport-blind features (design)

**Date:** 2026-07-15
**Phase:** 4 of 8 (see `CLAUDE.md` / master spec §8)
**Depends on:** Phase 3 complete — `data/interim/{nfl,mlb,nba}.parquet` exist and pass `schema.validate()`.

## Goal

Populate the feature columns the loaders left as placeholders, on the unified
29-column panel, with **one sport-blind module** parameterized per sport. The
sport is a parameter; no sport-specific branching lives in `src/features/`.

Columns filled this phase:

| Column | Currently | This phase |
|---|---|---|
| `home_elo`, `away_elo` | `1500.0` placeholder | real pre-game Elo ratings |
| `home_rest_days`, `away_rest_days` | null | days since each team's prior game |
| `away_travel_km` | null | haversine, away-team city → game city |
| `crowd_pct` | **already built** | untouched |

## Pipeline / IO

- Read `data/interim/{sport}.parquet` → apply features → `schema.validate()` →
  write `data/processed/{sport}.parquet`.
- Interim = loader output; processed = feature-complete, model-ready. Distinct
  stages. Phase 4 is re-runnable with **no ESPN re-fetch** (it reads interim,
  never raw).
- Module `src/features/build.py`:
  - `add_elo(panel, params)` — pure, sport-agnostic
  - `add_rest(panel)` — pure, sport-agnostic
  - `add_travel(panel, coords)` — pure, sport-agnostic
  - `build(sport)` — read interim → apply three → validate → write processed
  - `main()` — loop all three sports
- Static lookup `config/venue_coords.yaml` keyed `(sport, team)` → home-city
  `lat`/`lon`. ~90 rows, hand-filled, **committed** (small curated reference,
  not downloaded data — unlike the gitignored ESPN caches).

## Elo — "middle" design

One engine, per-sport params from `config/sports.yaml`:

```yaml
<sport>:
  elo:
    k: <float>          # update rate
    hfa: <float>        # home-field advantage, in Elo points
    carryover: <float>  # season-to-season retention toward 1500
```

Values, grounded in FiveThirtyEight's published methodology (verified 2026-07-15;
see sources at end):

| sport | k | hfa | carryover |
|---|---|---|---|
| nfl | 20 | 48 | 0.667 |
| nba | ~10 | 100 | 0.75 |
| mlb | 4 | 24 | 0.667 |

- **`hfa` and `carryover` are taken verbatim from 538** — they are additive /
  reversion params, independent of the MOV formula, so they transfer directly.
  538 reverts ⅓ toward mean for NFL & MLB (`carryover = 0.667`) and ¼ for NBA
  (`0.75`).
- **`k` does NOT transfer verbatim — it is the one gate-calibrated param.** 538's
  `k` lives *inside* a per-sport MOV formula (NBA: `20·(MOV+3)^0.8/(7.5+0.006·ED)`,
  effective per-game `k≈20`). Our simpler `ln(|margin|+1)` multiplier averages
  ~2.4 for NBA margins, so a flat `k=20` would run ~2.4× too hot. `k` must be
  **scale-matched to our multiplier**: the values above are starting guesses; if
  a sport's accuracy lands outside its benchmark band, `k` is the knob to adjust
  (calibrating a scale param to sane behavior — NOT the vanity grid-search ruled
  out below).
- **Mean = 1500** (538 uses 1505 for NFL/NBA, 1500 for MLB). We keep a single
  1500 across sports — the 5-point difference is inconsequential and it matches
  the loaders' existing 1500 initialization.

**Do NOT bake rest or travel into Elo.** 538 folds both into their rating (rest
2.3 pts/day, travel `miles^(1/3)·−0.31`). We deliberately keep Elo as pure
team-quality and carry `rest_days` / `away_travel_km` as **separate regression
controls** — baking them into Elo would double-count them against their own
columns.

**Use a CONSTANT `hfa`, never a fan-adjusted one.** 538's own MLB methodology
uses `hfa = 24` with fans but **`9.6` for games without fans** — i.e. 538
empirically found home advantage fell ~60% in empty stadiums. That is precisely
the crowd effect this study estimates. Baking a fan-adjusted HFA into our control
would **absorb the effect we are trying to measure**. (It is also independent
corroboration of the thesis and a citable one for the paper.)

Algorithm, per sport independently:

1. Sort that sport's games in **date order** (stable tiebreak on `game_id` so
   MLB doubleheaders are deterministic).
2. Every team starts at **1500** on its first appearance.
3. Between seasons: `new = carryover·old + (1 − carryover)·1500`.
4. Expected home score `E = 1 / (1 + 10^(-(elo_home + hfa − elo_away)/400))`.
5. MOV multiplier `m = ln(|home_margin| + 1)`.
6. Update after the game: `elo_home += k·m·(S − E)`, `elo_away −= k·m·(S − E)`,
   where `S = 1` home win, `0` home loss, `0.5` tie (NFL only).
7. **Store the PRE-game ratings** in `home_elo` / `away_elo`. HFA is applied
   only inside `E` (step 4), never baked into the stored rating — so Elo stays
   an outcome-uncontaminated control (the current game's result never enters its
   own stored rating).

Each sport is an independent 1500-pool; the engine runs per sport.

## Rest days

- Per team, `rest_days = (this game date − that team's previous game date)`,
  across the team's chronological sequence within a season.
- **First game of each season → null** (schema `Int64` nullable already allows
  it; there is no defined prior-game gap across the offseason).
- Playoffs continue the sequence naturally. Doubleheaders → 0.
- Computed for both the home and away team on each row (`home_rest_days`,
  `away_rest_days`).

## Travel

- `config/venue_coords.yaml`: `(sport, team) → {lat, lon}` home-city coords.
  Keyed by `(sport, team)` because abbreviations collide across sports.
- **Normal games:** `away_travel_km = haversine(away-team city, home-team city)`.
  City-level resolution is correct, not a limitation — travel fatigue operates at
  the 100s–1000s km scale; intra-city venue offset is noise. Same-city matchups
  (Yankees–Mets, Lakers–Clippers) fall out to ~0 correctly.
- **`is_bubble` → 0** — every team lived in Orlando; per-game travel really is ~0.
- **`neutral_site` / `relocated_home` → null** — the away team flew to
  Buffalo/Tampa/etc., not the home-team city; null is more honest than a
  coordinate known to be wrong. These rows are excluded from the main causal
  model anyway (flags), so no model impact.

Only `away_travel_km` is in the schema (home team is home / ~0); home travel to
neutral sites is intentionally not tracked.

## Sanity gate (phase done-when + the runnable checks)

1. **`schema.validate()` passes** on all three processed panels.
2. **Elo predictive readout, per sport** — job is **bug-detection, not tuning**.
   The win probability is the Elo expected score `E` already computed per game;
   aggregate it, no new machinery:
   - **Accuracy** = share of games the higher pre-game Elo (incl. HFA) won.
   - **Brier score** on `E` vs outcome.
   - Compare to public benchmarks: NFL ≈ 62–63%, NBA ≈ 66–68%, MLB ≈ 55–58%
     (baseball is genuinely low-predictability — a low number is the sport, not
     a bug). In-band ⇒ params fine. Near coin-flip (<~52%) ⇒ the engine is
     **broken** (date sort, MOV sign, carryover backwards) — fix the bug; do NOT
     grid-search K/HFA. For a control variable, squeezing 62→63% does not move
     the crowd coefficient.
   - **Ordinal check:** a known-dominant team (e.g. 2018 Warriors) ranks
     top-quartile at season end — "good teams rate higher."
3. **Cheap invariants:** rest days ≥ 0 or null; bubble `away_travel_km == 0`;
   travel symmetric between two cities (haversine(A,B) == haversine(B,A)).

## Known limitations (honest)

- **2018 is Elo burn-in** — ratings converge from a cold 1500 start over ~1
  season, so first-season ratings are least trustworthy. Fine: the causal window
  is 2020–21 and descriptive HFA reports later seasons.
- Elo `hfa`/`carryover` are **538-grounded**; `k` is a scale-matched starting
  value the accuracy gate calibrates (see gate #2). Neither is grid-search
  optimized — deliberate for a control variable.
- Our MOV multiplier (`ln(|margin|+1)`) is simpler than 538's per-sport formulas
  ("middle", not "full") — the accepted cost is the `k`-scaling caveat above.
- Venue coords are **city-level**, chosen (not a shortcut) for travel-fatigue
  resolution.

## Sources (Elo params, verified 2026-07-15)

- FiveThirtyEight, "How Our NFL Predictions Work" — K=20, HFA=48, revert ⅓.
  https://fivethirtyeight.com/methodology/how-our-nfl-predictions-work/
- FiveThirtyEight, "How We Calculate NBA Elo Ratings" — HFA=100, revert ¼
  (carryover 0.75), MOV-adjusted K formula.
  https://fivethirtyeight.com/features/how-we-calculate-nba-elo-ratings/
- FiveThirtyEight, "How Our MLB Predictions Work" — HFA=24 (9.6 without fans),
  revert ⅓, rest/travel baked into rating.
  https://fivethirtyeight.com/methodology/how-our-mlb-predictions-work/

## Out of scope (deferred)

- Betting-line team-strength companion (master spec §9 TODO — NFL-only
  `closing_spread` exists; not sport-blind).
- Elo win-probabilities as a published descriptive artifact (would justify
  "full" 538 Elo; YAGNI now).
- Grid-search Elo tuning.
