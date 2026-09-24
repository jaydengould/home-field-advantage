# home-field-advantage

Two-part study across MLB, NBA, NFL, NHL: (1) **quantify** home-field advantage descriptively
(home win %, scoring margin), (2) estimate the **causal crowd-attributable slice** of it, using
the COVID empty/partial-stadium period (full 2020–21 restriction window) as a natural experiment.
Modeled outcome is scoring margin; win % reported alongside as the intuitive number. Each sport
analyzed separately, then combined. Final output: a Quarto write-up (PDF + HTML).

Python 3.11+ in `.venv`. Quarto is the system CLI, not the pip package. `pytest` (179 tests).

## Documentation map

Read a file when the work needs it — don't preload.

| File | Read it when |
|---|---|
| `docs/design-decisions.md` | Touching the schema, features, or either estimator. Every settled "why it's built this way", including the frozen 6a specification and the identifying assumption. |
| `docs/data-pipeline.md` | Touching `src/data/` or `src/features/`, or interpreting `crowd_pct`. ESPN sourcing, empirical capacity, per-sport edge cases, known data imperfections. |
| `docs/results.md` | You need a number or a finding. Narrative index over `results/tables/`. |
| `docs/agent-pitfalls.md` | Before claiming a verification, quoting a coefficient, or adding a post-hoc analysis. Mistakes that actually happened here. |
| `docs/phase-log.md` | You need build history, what a phase shipped, or a deferred minor. |
| `docs/literature-review.md` | Positioning results against published work. §§1–5 are paper-ready. |
| `docs/superpowers/specs/`, `.../plans/` | The full per-phase specs and plans behind the log. |

## Core design principles

1. **The sport is just a PARAMETER.** All four sports normalize into one unified game-level panel
   schema (`src/schema.py`, 29 columns). Sport-specific logic lives **only** in `src/data/`.
   Everything downstream — features, models, plots — is sport-blind and written once. If
   something needs sport-specific handling downstream, it belongs in `src/data/` instead.
2. **`data/raw/` is never overwritten.** Downloaded source data is immutable. Loaders read from
   `data/raw/`, write to `data/interim/` (loader output) then `data/processed/` (feature-complete).
3. **`results/tables/*.csv` is authoritative over every markdown file in this repo**, including
   this one. Any number the paper cites comes from a CSV or a `.qmd` chunk. Where prose and CSV
   disagree, the CSV wins and the prose is what's stale.
4. **The frozen 6a specification does not get re-specified.** It was changed once, after its first
   real-data run (two-way FE → team FE + trend; disclosed in the paper), and frozen since; every
   number in `results/tables/` is byte-verified against it. Add sensitivity columns beside it.

## Project-specific facts that are easy to get wrong

- **`crowd_pct == 0` is a REAL value inside a restriction window** (empty stadium), never coerce it
  to null — **and only until that team first readmitted fans** (config `fans_from`/`reclosures`).
  ESPN zeros *outside* `config/sports.yaml` `zero_attendance_windows`, or *inside* one but on/after
  a team's `fans_from` date with no covering `reclosures` entry, are reporting artifacts and are
  null `crowd_pct` in `data/processed` (`build.null_reporting_zeros`).
- **`capacity` is empirical, not seated** — each venue-season's max *announced* attendance.
  ESPN's `venue.capacity` is always `None` and announced attendance exceeds seated capacity.
- **`treated_seasons` differs per sport** (nfl 2020 · mlb 2020–21 · nba 2021 · nhl 2021) and lives
  in `config/sports.yaml`. Never hardcode 2020; a hardcoded gate already produced a false PASS.
- **Exclusions from every model:** `neutral_site | relocated_home | is_bubble | is_playoff`, via
  the shared `twfe._exclusion_mask`.
- **Main model is team FE + a linear `season_trend`, never two-way FE** — full season FE are
  near-collinear with the treatment outside MLB (NFL/NBA signs invert, NHL inflates ~8×).
- **Filter the bubble on `is_bubble`, never `neutral_site`** — 58 of 130 NHL bubble games are not
  flagged neutral.
- **NFL's `closing_spread` is a post-treatment bad control**, not a main-model control.
- ESPN soft-rate-limits bulk fetching; the cache is write-once and a cold MLB pull takes hours.

## Working convention

**Be brutally honest.** This is a research project — a flattering wrong answer is worse than
useless, it corrupts the conclusion. Push back when the user is wrong, name methodological flaws
plainly, flag endogeneity/selection/sample-size problems even when unwelcome, never agree just to
be agreeable. Distinguish what the data can support from what it can't.

**Do not simply agree with me. Be my sparring partner. Identify my blind spots, structural risks,
and faulty assumptions.**

**Git is user-owned.** Never run `git commit`/`push`/`branch`; the user commits their own history.
Work sits uncommitted in the working tree until they take it.

**Build one phase at a time** — spec → plan → build per phase, not one plan for the project.

**Update the docs at the end of each working session.** Decisions → `docs/design-decisions.md`;
numbers → `docs/results.md` (and the CSV behind them); new agent traps → `docs/agent-pitfalls.md`;
what shipped → `docs/phase-log.md`; Status below. Keep this file under 200 lines — anything
longer belongs in a `docs/` file with a row in the map above.

## Status

**Phases 1–8 complete; the paper is done.** 179/179 tests. All four loaders build validated panels;
features populate `data/processed/`; descriptive HFA is quantified with a sanity gate; 6a (TWFE
dose-response) and 6b (on/off before-after) both estimate the crowd effect per sport; 23 CSVs in
`results/tables/` back every number the paper cites. Committed through Phase 8 (`77abb84`).

**The paper:** `paper/hfa.qmd` → `paper/hfa.pdf` (28 pp; `paper/references.bib`, 20 entries, all
primary-verified). Render: `cd paper && QUARTO_PYTHON=../.venv/bin/python quarto render hfa.qmd`.
Docs have no number gate: re-sweep them after any table regeneration.

**Project closed (2026-09-22).** Paper, summary (`docs/summary.md`) and `results/` are committed and pushed;
the raw caches are archived (below).

**Headline (pooled win-probability LPM):** nfl **+0.050** · nba **+0.006** · nhl **+0.011** ·
mlb **−0.021** (post reopening-zeros fix, 2026-09-16; was +0.044/+0.016/+0.007/−0.021). Every
per-sport CI crosses zero. But the finding is a **ceiling, not a null**: in all eight sport ×
outcome cells the per-unit effect detectable at 80% power exceeds that sport's entire home
advantage (three fall to ≈1 or below once rescaled). On the season-level noise floor it is 7 of 8: **MLB win is the
exception** (0.88×, a lower bound), and the paper says so. Full statement and its caveats: `docs/results.md`.

**Raw data:** the ESPN caches were compressed to `~/hfa-espn-cache.tar.zst` (726 MiB, 36,855 files, `zstd -t` passed)
and the originals in `data/raw/*/espn` deleted (2026-09-22), after a full re-run from the parquets reproduced
every committed table byte for byte. Restore from the repo root: `zstd -dc ~/hfa-espn-cache.tar.zst | tar -xf -`.
The parquets in `data/interim`/`data/processed` are now the only uncompressed copy: don't delete them.
