# Phase 5 — Descriptive HFA — design

**Date:** 2026-07-17
**Status:** Approved design.
**Phase:** 5 of the home-field-advantage build (see CLAUDE.md / §8 of the umbrella spec).

## Goal

Quantify home-field advantage **descriptively** — no model, no causal claim — as
home win % and mean scoring margin, sliced **by sport × season** plus a pooled
per-sport headline. This is the first deliverable a reader sees, and it doubles
as a **data sanity gate**: HFA must be positive in full-crowd seasons and must
visibly sag in the empty/partial COVID seasons (2020 empty, 2021 partial). A
failure here is either a real finding or a pipeline bug — either way it is caught
before any modeling begins.

The season slice is a *descriptive preview* of the natural experiment, not the
causal estimate. The causal slice is Phase 6.

## Non-goals (deliberately excluded)

- **Playoff HFA.** Excluded because (1) it collapses in exactly the COVID seasons
  that matter (NBA 2020 = 0 clean home games, all bubble; MLB 2020 postseason
  mostly neutral bubble sites), so it cannot show the dip; (2) playoff home teams
  are systematically the better seed, so playoff home win% blends HFA with quality
  asymmetry and is non-comparable to the regular-season number; (3) per-season
  playoff samples are tiny (NFL 10–12 games). The `is_playoff` exclusion is
  documented with a single caveat sentence in the Phase 8 write-up, not analyzed
  here.
- Per-team HFA, home/away splits, endogenous-attendance dose-response preview —
  later phases or out of scope. YAGNI.
- Plot theming beyond readable, accessible defaults.

## What counts as a "clean home game"

The descriptive HFA number is computed over **true home games only**:

- `is_playoff == False` (regular season only).
- Exclude any game with `neutral_site == True`, `relocated_home == True`, or
  `is_bubble == True`. These are not real home-crowd games and match what the
  Phase 6 causal model excludes downstream.

Raw game counts (pre-exclusion) stay visible in the output table so the exclusions
are auditable.

## Components

One sport-blind module, `src/viz/descriptive.py`, mirroring the
`src/features/build.py` pattern (pure compute separated from I/O and plotting).

### `summarize(panel) -> DataFrame`

Pure and testable — no disk, no network. Input is one sport's processed panel
(29-col schema). Steps:

1. Filter to clean regular-season home games (rules above).
2. Group by `season` → one row per season with:
   - `n_games` — clean-home game count for that season.
   - `n_games_raw` — regular-season game count **before** exclusions (audit).
   - `home_win_pct` — mean of `home_win` over **decided** games (ties, where
     `home_win` is null, are dropped from this mean). Ties are NFL-rare.
   - `home_win_se` — proportion SE `sqrt(p*(1-p)/n_decided)`, where `n_decided`
     is the count of non-null `home_win` clean-home games (≤ `n_games`).
   - `mean_home_margin` — mean of `home_margin` over all clean-home games
     (ties have `home_margin == 0` and are legitimately included here).
   - `home_margin_se` — `std(home_margin, ddof=1) / sqrt(n_games)`.

   `n_games` is the structural clean-home count (includes ties). The win% and its
   SE use `n_decided`; the margin and its SE use `n_games`. They differ only when
   ties exist (NFL). `n_decided` is not emitted as a column — it is derivable and
   ties are rare — but the two denominators are documented here to avoid ambiguity.
3. Append one **pooled headline row** (`season = "pooled_fullcrowd"`) computed over
   full-crowd seasons only (`covid_era == False`), same statistics. Rationale:
   pooling all seasons would fold the COVID dip into the headline and understate
   normal-condition HFA.

Output columns: `sport, season, n_games, n_games_raw, home_win_pct, home_win_se,
mean_home_margin, home_margin_se`. `season` is the integer year for per-season
rows and the string `"pooled_fullcrowd"` for the headline row.

`sport` is read from the panel's `sport` column (constant within a panel).

### `plot_hfa(summaries) -> matplotlib Figure`

Input: the per-season summaries for all three sports (pooled rows dropped for the
plot). Two stacked panels sharing the season x-axis:

- **Top:** `home_win_pct` by season, one line per sport, 50% reference line.
- **Bottom:** `mean_home_margin` by season, one line per sport, 0 reference line.

The 2020–2021 seasons are shaded (COVID band) in both panels. The visual read: all
three lines dip into the shaded band. Error bars from the SE columns are drawn so a
noisy season is not over-read. Load the `dataviz` skill before writing chart code
for palette/accessibility.

### `main()`

Loads `data/processed/{nfl,mlb,nba}.parquet`, runs `summarize` on each, concatenates,
writes:

- `results/tables/descriptive_hfa.csv` — all three sports' per-season + pooled rows.
- `results/figures/hfa_by_season.png` — the 2-panel figure.

## Data flow

```
data/processed/{sport}.parquet
        │  (read)
        ▼
   summarize(panel)  ──►  per-sport summary DataFrame
        │
        ├──► concat ──► results/tables/descriptive_hfa.csv
        └──► plot_hfa ─► results/figures/hfa_by_season.png
```

## Sanity-gate check (fails loudly if the pipeline is broken)

After `main()` runs, assert on the written table:

- Every sport's `pooled_fullcrowd` row has `home_win_pct > 0.50` and
  `mean_home_margin > 0`. (Positive HFA under normal conditions.)
- Every sport shows a **drop** in 2020 relative to its full-crowd pooled number on
  at least the margin metric. If 2020 does not dip, stop and investigate before
  modeling — it is a finding or a bug.

These are printed as a PASS/FAIL summary by `main()` (not a hard exception — a
non-dip is information, not a crash), so the gate is visible in the run log.

## Testing

One test file, `tests/test_descriptive.py`, following the project convention (no
frameworks/fixtures beyond pytest). A small hand-built panel (a handful of games
spanning 2 seasons, including one neutral-site game, one playoff game, and one tie)
asserts:

- Exclusions drop the neutral-site and playoff rows from `n_games`.
- `home_win_pct` and `mean_home_margin` match hand-computed values.
- A tie (null `home_win`) is excluded from `home_win_pct` but the game is still
  counted structurally as designed.
- The `pooled_fullcrowd` row uses only `covid_era == False` seasons.

## Notes / carry-forward

- Output stages: `data/processed/` is feature-complete input (Phase 4);
  `results/{tables,figures}/` is Phase 5 output. `results/` is generated — safe to
  regenerate.
- Standard errors are naive iid SEs (proportion SE for win%, sample-mean SE for
  margin). They are a guard against over-reading a single noisy season, **not** the
  inferential CIs of the causal model (Phase 6 does clustered/robust inference).
  Document this so the descriptive SE is not mistaken for the causal one.
