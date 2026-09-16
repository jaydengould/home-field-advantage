# Phase log

What was built when, and what each phase left behind. Specs and plans live in
`docs/superpowers/{specs,plans}/`; per-phase ledgers in `.superpowers/sdd/`. Decisions moved to
`docs/design-decisions.md`; numbers to `docs/results.md`; data traps to `docs/data-pipeline.md`.

**How this project builds:** one small spec → plan → build loop **per phase**. The umbrella
design spec is not a build script; do not plan the whole project at once.

| Phase | Done | Shipped |
|---|---|---|
| Attendance spikes | 2026-06-29, 07-07 | Proved ESPN carries `gameInfo.attendance` for all sports and that the native packages don't. Confirmed the ESPN event id removes the cross-source join worry. |
| 1 — schema + config | 2026-06-29 | `src/schema.py` (29-column contract + `validate()`), `config/sports.yaml`, `pyproject.toml` (`pythonpath = ["."]`; `src/` is a namespace package, no `__init__.py`). |
| 2 — NFL pilot loader | 2026-07-02 | `src/data/nfl.py` → `data/interim/nfl.parquet`, 1657 games, 0 dropped. Empirical-capacity ("Option A") decided here. |
| 3 — MLB + shared ESPN layer | 2026-07-07 | `src/data/_espn.py` extracted (2nd/3rd consumer arrived), `src/data/mlb.py`, retry/backoff robustness learned from the real pull. |
| 3 — NBA loader | 2026-07-15 | `src/data/nba.py`; continuous scoreboard walk, bubble flag, `derive_capacity` `max()` fix (affects all sports). |
| 4 — sport-blind features | 2026-07-15 | `src/features/build.py` (`add_travel`, `add_rest`, `add_elo`) + `config/venue_coords.yaml` → `data/processed/{sport}.parquet`. |
| 5 — descriptive HFA | 2026-07-17 | `src/viz/descriptive.py`, `descriptive_hfa.csv`, `hfa_by_season.png`, and the data-sanity gate. |
| 6a — TWFE dose-response | 2026-07-20 | `src/models/twfe.py`; mid-build design correction to team FE + linear trend. |
| 6b — on/off before-after | 2026-07-22 | `src/models/did.py`; `_exclusion_mask` extracted from `twfe._prep` so 6a/6b share one exclusion definition. Promoted to co-primary. |
| NHL — 4th sport | 2026-07-25 | `src/data/nhl.py` + `"nhl"` threaded through schema values, config, coords, the four downstream sport lists and `SPORT_COLORS`. `twfe.fit(..., drop_controls=())`. |
| 7 — pre-write-up consolidation | 2026-07-28 | `src/models/sensitivity.py` (5 prose-only numbers → 5 CSVs), `docs/literature-review.md`, `paper/references.bib` (12 entries), `summarize(playoffs=)`, palette + marker work. |
| Pre-write-up audit | 2026-08-17 | 4 more tables: `dose_overlap`, `leave_one_season_out`, `season_effects`, `noise_floor`. |
| Zero-attendance fix | 2026-09-15 | Inserted mid Phase 8 (B.G2→B.G3). `zero_attendance_windows` in config; `build.null_reporting_zeros` nulls `crowd_pct` for 119 ESPN zero-attendance artifacts; `crowd_pct` nullable; `walk_scoreboard` dedupe + `validate()` unique `game_id` removed 23 duplicate MLB rows (panel 30,146); original tables in `results/tables/pre_dedup/`; `sensitivity.zero_attendance_sensitivity` → `zero_attendance_sensitivity.csv` (22 CSVs); pre-fix tables archived in `results/tables/pre_zero_fix/`. 170 tests. Headline win% nfl +0.044 · nba +0.016 · nhl +0.007 · mlb −0.021. |

**⬅ Next: Phase 8 — Quarto write-up → PDF + HTML.** See `docs/paper-writing-guide.md`.

## Phase 7 extras worth knowing

- `twfe.fit()` gained `trend={"linear","quadratic","none"}`, `season_fe=`, `report=`,
  `sample="treated"`, and `extra_controls` de-duplication. Bad `trend`/`report` raise named
  `ValueError`s.
- `descriptive.summarize(panel, playoffs=False)` — `~is_playoff` was hardcoded; the playoff
  subsection is now unblocked.
- `scipy` promoted from a transitive dependency to a declared one in `requirements.txt`.
- **The collinearity R² is approximate by construction** — it runs on 1–6% more rows than the fit
  (exclusions only vs exclusions + control listwise-drop), moving R² by ≤ 0.0023. It cannot be
  made exact: NFL's two outcomes have different fit samples (1463 vs 1459), so one R² per sport
  is necessarily approximate. Invisible at 2dp; does not disturb the ordering that carries the
  argument.
- **MLB treated-split puts both year indicators in one model** — each absorbs the other if
  omitted (dropping 2021 moves the 2020 coefficient .0595 → .0358). The two `report=` calls are
  two views of one regression, not two regressions.

## Figure palette (Phase 7 C2) — a documented trade, not a free win

Shipped: nfl `#2a78d6` (4.42) · mlb `#008300` (4.95) · nba `#a4036f` (7.44) · nhl `#e42800`
(4.56), all clearing the 3:1 contrast floor. **The trade:** deuteranopia separation on the
green/red (mlb–nhl) pair regressed 19.62 → 8.4 ΔE — still above the 6.0 floor and 8.0 target, but
now the tightest pair in the figure. **No non-red alternative exists**: a sweep of ~1500 warm
hexes plus an independent reviewer sweep showed every amber/brown collapses onto green under
protan/deutan simulation (Okabe-Ito `#d55e00` scores 1.6 — deep FAIL). The all-pairs ceiling given
fixed blue/green/magenta is 13.25 and is set by the *existing* mlb–nba pair, not slot 4.

Mitigations shipped with it: per-sport `MARKERS` (`nfl "o"`, `mlb "s"`, `nba "^"`, `nhl "D"`) in
both `descriptive.py` and `twfe.py` so sport is not encoded by colour alone; a parametrized
contrast test (**the earlier `for`-loop test short-circuited at nba and hid a second failure**);
a CVD floor regression guard over all 6 pairs; and a cross-module equality test guarding both
`SPORT_COLORS` and `MARKERS`. `_delta_e_cvd`'s Machado-2009 matrices are copied verbatim from the
dataviz skill's bundled validator — the skill lives outside the repo, so they stay in lockstep by hand.

## Deferred minors (non-blocking, logged in the phase ledgers)

Elo does not update on ties (NFL-rare). Doubleheaders give rest 0. The coords-coverage test
FileNotFounds on a cold checkout (no parquets). NFL-side `derive_capacity`/`check_coverage` tests
now duplicate `test_espn.py`. `fetch_summary` would AttributeError if ESPN emitted
`"gameInfo": null` (it doesn't). `plot_slope`'s legend swatches inherit the first-sorted sport's
colour instead of neutral gray — the hollow/filled shape still reads; fix only if that figure is
touched. `load()` lacks type annotations in a couple of loaders.
