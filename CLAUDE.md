# home-field-advantage

Two-part study across MLB, NBA, NFL, NHL: (1) **quantify** home-field advantage descriptively
(home win %, scoring margin), (2) estimate the **causal crowd-attributable slice** of it, using
the COVID empty/partial-stadium period (full 2020–21 restriction window) as a natural experiment.
Modeled outcome is scoring margin; win % reported alongside as the intuitive number. Each sport
analyzed separately, then combined. Final output: a Quarto write-up (PDF + HTML).

Python 3.11+ in `.venv`. Quarto is the system CLI, not the pip package. `pytest` (170 tests).

## Documentation map

Read a file when the work needs it — don't preload.

| File | Read it when |
|---|---|
| `docs/design-decisions.md` | Touching the schema, features, or either estimator. Every settled "why it's built this way", including the frozen 6a specification and the identifying assumption. |
| `docs/data-pipeline.md` | Touching `src/data/` or `src/features/`, or interpreting `crowd_pct`. ESPN sourcing, empirical capacity, per-sport edge cases, known data imperfections. |
| `docs/results.md` | You need a number or a finding. Narrative index over `results/tables/`. |
| `docs/paper-writing-guide.md` | Writing any prose for the paper. Language bans, framing, content checklist, citation corrections, the units trap. |
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
4. **The frozen 6a specification does not get re-specified.** It was pre-committed and every
   number in `results/tables/` is byte-verified against it. Add sensitivity columns beside it.

## Project-specific facts that are easy to get wrong

- **`crowd_pct == 0` is a REAL value inside a restriction window** (empty stadium), never coerce it
  to null. ESPN zeros *outside* `config/sports.yaml` `zero_attendance_windows` are reporting
  artifacts and are null `crowd_pct` in `data/processed` (`build.null_reporting_zeros`).
- **`capacity` is empirical, not seated** — each venue-season's max *announced* attendance.
  ESPN's `venue.capacity` is always `None` and announced attendance exceeds seated capacity.
- **`treated_seasons` differs per sport** (nfl 2020 · mlb 2020–21 · nba 2021 · nhl 2021) and lives
  in `config/sports.yaml`. Never hardcode 2020; a hardcoded gate already produced a false PASS.
- **Exclusions from every model:** `neutral_site | relocated_home | is_bubble | is_playoff`, via
  the shared `twfe._exclusion_mask`.
- **Main model is team FE + a linear `season_trend`, never two-way FE** — full season FE are
  near-collinear with the treatment outside MLB (NFL/NBA signs invert, NHL inflates ~12×).
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

**Phases 1–7 complete, plus NHL as a fourth sport and a pre-write-up audit.** 170/170 tests. All
four loaders build validated panels; features populate `data/processed/`; descriptive HFA is
quantified with a sanity gate; 6a (TWFE dose-response) and 6b (on/off before-after) both estimate
the crowd effect per sport; 22 CSVs in `results/tables/` cover every number the paper cites; the
literature positioning and `paper/references.bib` exist. Uncommitted, awaiting human commit.

**⬅ IN PROGRESS — Phase 8 polish (stages A–E).** First draft done (`paper/draft/hfa-draft.qmd`, frozen);
working copy `paper/hfa.qmd` (gitignored). Resume from the ledger's "RESUME HERE" block:
`.superpowers/sdd/phase8-polish/progress.md`. Spec/plan: `docs/superpowers/{specs,plans}/2026-09-14-phase8-paper-polish*`.
B.G1 and B.G2 done. **Zero-attendance data fix done** (2026-09-15, `docs/superpowers/{specs,plans}/2026-09-15-zero-attendance-fix*`;
119 ESPN zero artifacts → null dose; 23 duplicate MLB rows removed; originals in `results/tables/pre_dedup/`). **Next: Stage B.G3**
against the regenerated tables — see the ledger's RESUME HERE block.

**Phase 8: Quarto write-up → PDF + HTML.** Every *estimator* the paper needs exists.
**Two tables must be computed inline** (neither has a CSV): the descriptive playoff-HFA table via
`summarize(panel, playoffs=True)`, and the NBA bubble decomposition + seeding placebo. Read
`docs/paper-writing-guide.md` first — the audit changed Phase 8's framing, not its estimates.

**Headline (pooled win-probability LPM):** nfl **+0.044** · nba **+0.016** · nhl **+0.007** ·
mlb **−0.021**. Every per-sport CI crosses zero. But the finding is a **ceiling, not a null**: in
all eight sport × outcome cells the per-unit effect detectable at 80% power exceeds that sport's
entire home advantage (three fall to ≈1 or below once rescaled). Full statement and its caveats: `docs/results.md`.

**After the write-up:** delete the ESPN caches (`data/raw/*/espn`, ~23GB) once the parquets are
verified — gitignored and local-only, so only do this near project end to avoid re-pull risk.
