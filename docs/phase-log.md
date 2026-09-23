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
| Reopening-zeros fix | 2026-09-16/17 | Inserted mid Phase 8 (B.G5, between fix round 1 and fix round 2). Fix 1's zero rule only covered zeros *outside* a restriction window; this closes the gap for zeros *inside* one that fall after a team had already readmitted fans. `config/sports.yaml` gains `fans_from`/`reclosures` per sport, sourced from an exhaustive 44-team audit (`.superpowers/sdd/reopening-zeros-fix/team_audit.csv`, 20 `no_fans` / 15 `data_only` / 9 `fans_from`, zero unverified); `build.null_reporting_zeros` extended (`fans_from=`, `reclosures=` params); `sensitivity.reopen_zero_sensitivity` → `reopen_zero_sensitivity.csv`; pre-fix tables archived in `results/tables/pre_reopen_fix/`; baseline hashes refreshed (old at `.superpowers/sdd/phase8-polish/baseline/tables.pre_reopen_fix.sha256`). 179 tests. 172 games newly nulled (nfl 6 · mlb 0 · nba 77 · nhl 89). Headline win% nfl +0.044→**+0.050** · nba +0.016→**+0.006** · nhl +0.007→**+0.011** · mlb −0.021 (unchanged). Not outcome-blind (surfaced via a Ganz & Allsop literature comparison, not the audit); disclosed as such, with both the scratch and final numbers shipped side by side. Full detail: `docs/results.md` "Reopening-zeros correction", `docs/data-pipeline.md` "Reopening zeros", `docs/design-decisions.md` "Reopening-zeros rule". |
| Docs number sweep | 2026-09-18 | Task 0 after the reopening-zeros fix. Every number in README, CLAUDE and `docs/*.md` mapped to its exact CSV cell or recomputed from `data/processed/` (dose means, σ, spread sensitivity, correlations). 43 fixes across 8 files. README was a pre-zero-fix snapshot: "seven of eight" → all eight, headline, NHL 6a/6b agreement, dose overlap, LOSO. Also fixed: design-decisions/CLAUDE "NHL inflates ~12×" → ~8×; the "every team was sourced" forking-path sentence → 29 sourced / 15 data-only / none unverified; stale treated dose means, LOSO 0.55→0.58 SE, NBA MDE 7.19→7.50, MLB MDE 4.37→4.36. Not re-verified (no CSV, not recomputed): NYI dual-arena ±0.003, two-way-clustered SE 0.44–0.77×, bubble placebo figures, Elo accuracies. No code or table changed. |
| B.G5 fix round 2 | 2026-09-18 | N1 re-evaluated on post-reopening-fix data: the Ganz presence mapping is +2.61 (nulled games dropped) / +2.42 (counted as fans-present), 90–95% up our NBA interval; live clause + assert band on both variants. M5: NHL within-2021 margin CI [−3.20, −0.09], p = .039, disclosed as the only within-season fit below .05, assert-guarded; it is team-clustered (the "game-clustered" label was wrong in docs). Minors m1–m5 + reviewer new-m3/xref fixed. Re-review CLOSED (0 C/0 I). Gate: render clean on `hfa` kernel, paper 8/8, tests 179, tables 23/23, drift fully traced. Docs: Ganz raw-mean framing corrected in literature-review/paper-writing-guide/results/README. |
| B.G6 | 2026-09-18 | Claim audit of sec-limits + conclusion: 36 rows, 13 not supported — the conclusion restated claims G1–G5 had corrected in the body. User approved all 5 escalations: "all centred near zero / none able to exclude NFL-sized" replaced (MLB win CI excludes it; NFL ≈96% of its HFA per unit, +0.013 without 2018); ceiling stated under RI with the two team-clustered exceptions; season-level floor sentence added; "one declared exception" (reopening-zeros correction) to the post-hoc classes; NHL/MLB sign-reversal demoted from durable contribution to a one-league illustration (MLB shows none; 4 of 8 cells). Verifier CLOSED. Gate green. |
| B.S (Stage B close) | 2026-09-21 | Whole-paper sweeps + content checklist, 2 verifier rounds. Game→team-clustered; RI "no trend" → linear trend; British spellings → 0; within-2021 NHL no longer "exogenous" (E1). NYI 2020–21 ESPN venue mislabel (28 games on Barclays capacity, dose ≈0.88 of true) disclosed, not fixed (E2). tbl-within shows all four leagues (was NHL+MLB while prose counted eight). tbl-main gains (b) CIs; caption no longer calls (b) per-unit. **Units error fixed:** (a)/(b) coherence now compares (b) with (a) × dose gap — NFL close (−7.6%/+5.7%), NBA/MLB far apart; old "(b) smaller in NFL, as expected from raw vs adjusted" was false. Audit trail `.superpowers/sdd/phase8-polish/stage-b-S-*.md`. |
| 8 — Quarto write-up | 2026-09-22 | First draft (`paper/draft/hfa-draft.qmd`, frozen, hash-pinned), then polish stages A–E on the working copy `paper/hfa.qmd` → `hfa.pdf` / `hfa.html`. Both gitignored until the user publishes. Stage sections below; wrap-up at the end of this file. |

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

## Phase 8 stage B — claim audit (closed 2026-09-21)

Every top-level section gets an independent claim audit (opus), a controller triage that
re-verifies each load-bearing number from the current CSVs, one batched user escalation, a fixer,
and a fresh-agent verifier. Closed so far: **G1** (front/intro), **G2** (data/descriptive/
strategy), **G3** (`sec-results`, 15 fixes), **G4** (`sec-leagues`, 12 fixes + a 5-finding fix
round). What it is actually catching, across ~150 audited claims:

- **Invented multipliers.** "0.14–0.76×" (true 0.44–0.77, imported from a different sensitivity),
  "roughly fifty times" (true 38), "four times larger" (true 12.5). None reproduced from any
  artifact; all three read plausibly in context.
- **Comparisons that are backwards.** NFL `sd_true` 1.73 described as "larger than" its own 1.75
  HFA; the same sentence had propagated into `docs/results.md` and `src/models/sensitivity.py`.
- **Counts that disagree with their own table.** "the same count as @tbl-mde" (7 vs 8), "three of
  them need their own discussion" above four subsections, "we report all three definitions" where
  only one estimated definition exists.
- **Unbounded superlatives.** "largest … anywhere in the study" was falsifiable from CSV rows no
  table prints — twice in one section.
- **Facts true of three leagues stated as common to four.** "the same compressed schedules" (the
  NFL played 256 games in 2018, 2019 and 2020).

Discipline that made it work: the CSVs are authoritative, the controller re-derives every
load-bearing number before escalating, and fixes are wired as live expressions rather than typed.
Captions are the one place that cannot be — see `docs/agent-pitfalls.md`.

## Phase 8 stage C1 — citation verification (2026-09-21, closed)

All 12 original bib entries verified against primary sources (3 sequential agents + new-source batch +
fresh spot-check). Shipped: 3 author-name fixes (Wang/Qin, Higgs, Guérette), ESPN url → live endpoint,
all `urldate` → 2026-09-21; Gong reworded accuracy → **home bias**; Schank "published" → unrefereed,
null scoped to 2020/21; realignment rationale now league-stated (`nhl2020seasonplan`); Wikipedia
replaced and its limitations paragraph deleted; bubble-"home" sentence cut to what NBA.com supports;
sec-mlb officiating sentence rewritten — **Saiegh & Wong (2026) find MLB umpire bias rises with
occupancy** (small), which contradicted the planned "not crowd-dependent" wording. Bib 12 → 18 entries.
Ledger number-rows: Ganz page refs corrected. Gates: render 0, no citeproc warnings, paper 8, suite 179,
tables 23/23.

## Phase 8 stage C2 — NFL crowd noise / communication (2026-09-21, closed; Stage C closed)

Search agent (25 queries, 21 candidates) → controller re-read every cited quote → user approved
recommendations → fresh reviewer (no blocking; 2 minor overstatements fixed). **Finding against the
planned mechanism:** Farnell (2023, JSE, NFL 2018–2020) finds crowds do NOT affect offensive pre-snap
penalties for either side; the crowd effect is fewer home-*defense* pre-snap penalties. Intro keeps
the channel as "widely believed" (snap-count clause added, uncited); sec-lit gains Farnell +
McMahon & Quintanar (2024, NCAA; their "noise" inference is a loss of significance with a larger
2020 point estimate — stated) + Saiegh & Wong (C1 carry item). Hsu (2024) dropped: no readable copy.
Bib 18 → 20. Gates: render 0, citeproc 0, paper 8, suite 179, tables 23/23, drift 19 traced.

## Deferred minors (non-blocking, logged in the phase ledgers)

Elo does not update on ties (NFL-rare). Doubleheaders give rest 0. The coords-coverage test
FileNotFounds on a cold checkout (no parquets). NFL-side `derive_capacity`/`check_coverage` tests
now duplicate `test_espn.py`. `fetch_summary` would AttributeError if ESPN emitted
`"gameInfo": null` (it doesn't). `plot_slope`'s legend swatches inherit the first-sorted sport's
colour instead of neutral gray — the hollow/filled shape still reads; fix only if that figure is
touched. `load()` lacks type annotations in a couple of loaders.

### Phase 8 stage D — humanize (2026-09-22)

D0 wrote `paper/voice-profile.md` (gitignored): spec §8 rules verbatim + the user's own intro rewrite,
extracted from the PDF, with a stale-facts note extended past the plan's two items ("centred near zero",
"seven of eight", "comfortably contains it") so rewriters take voice from the sample and never claims.

D.G1–D.G6 each ran rewriter → controller gates → fresh meaning reviewer → controller fixes → user checkpoint.
Claims compared across the six groups: G1 front+intro, G2 111, G3 46, G4 110, G5 (21 changed line-pairs,
10 sources), G6 51 — every one `kept`, none added, dropped or re-weighted. Em dashes went to zero in prose
paper-wide (the survivors are chunk captions, Python strings and comments). Every ratio kept its basis word,
so the units trap stayed shut. Blocking rows fixed: G1 an abstract "then" that implied a false inference;
G2 the deleted "and the distinction is not cosmetic". Zero attribution drift on all ten cited sources.

User-approved content fixes taken alongside the voice pass: travel dropped from the intro's "largely
persisted" list (it contradicted "travel … changed too"); the abstract's duplicate RI-floor sentence merged;
the doubleheader definition moved from a chunk comment into prose; MLB playoff hosting corrected for the
post-2022 Wild Card round (web-verified, higher seed hosts all three); the crowd-dose mega-paragraph split;
`# Results` given a bridging line; the sec-ri heading's hardcoded "six" made computed; a dead variable dropped;
the NFL headline estimate given an `@sec-power` pointer; `assert lg_bubble_seed_n == 88` added behind a typed
caption; Schank named as the unrefereed null; Saiegh & Wong's own 2SLS disclaimer carried; and the conclusion
reordered so it ends on "the pandemic happened once" instead of the demoted NHL illustration.

### Phase 8 stage E1 — whole-paper review (2026-09-22, closed)

Two fresh reviewers (hiring reader, methodologist: 2 blocking, 7 major, 20 minor); controller verified every serious
claim against the spec files and CSVs before triage (`.superpowers/sdd/phase8-polish/e-triage.md`). Batch 1
(controller, wording user-approved verbatim): M1 spec-change disclosure in §1/§4.2/§9; M2 MLB win probability admitted
as the one cell leaning against a full-advantage effect, NBA's exclusion discounted by the noise floor, the unsupported
RI dismissal removed from abstract/intro/conclusion; abstract gains the plain-words why (treatment assigned to seasons;
an untreated season beats the treated one in every cell) and the 52.8–57.0% descriptive range; six-of-eight power count
paired with four-of-eight rescaled; "RI worse / do not extend" corrected; NHL "four pre-committed diagnostics",
"confirms", "this is the lesson" corrected. Figure titles fixed ("HFA shrinks…", "TWFE") and redrawn from CSVs. Batch 2
(fixer agent): M10–M29 + hiring items, three headings reworded (IDs kept), and the user's request to cut half the
"not X, it's Y" contrasts (90 found, 40 protected, 22 claim-bearing kept, 28 cut). Fresh meaning reviewer: one blocking
row ("design we chose before seeing results" contradicted M1 → "we adopted"), plus a body home for the MLB/NBA claim in
sec-floor with the clamped-floor lower-bound caveat. Nine new asserts. Gates: suite 179, paper tests 8, tables 23 OK,
draft untouched, drift CLEAN with `stage-e-B1-allow.txt` / `stage-e-B2-allow.txt`.

### Phase 8 stage E2 — final mechanical gates (2026-09-22, closed)

Suite 179, paper tests 8, tables 23/23, draft hash OK, PDF/HTML/plain render exit 0 with only known noise. Margin check
by ink extent on all 28 pages (poppler `-bbox` crashes on this PDF): every page inside 1 in, so no table overflows.
Whole-paper drift, first draft → final (`e-drift.txt`, 1100 un-allowed): the 725 number/cite tokens were split across
the 58-snapshot chain and each attributed to the stage hop that moved it, 0 unattributed, with a hop → trace-record map
(`e-drift-annotated.txt`). Rendered numbers in the B/ZA/RZ hops come from pinned CSVs and were never token-ledgered by
design; typed prose digits are gated by `check_paper.py::test_no_unledgered_numbers`. User sign-off: a skim confirming
rendering; content sign-off is the cumulative D-group checkpoints and E1 approvals.

## Phase 8 wrap-up

- **Draft** (2026-09-14): one session → `paper/draft/hfa-draft.qmd`, frozen as the drift baseline.
- **A — numbers wired live.** Typed numbers → inline `{python}` expressions over the CSVs (159 by A's close);
  `paper/check_paper.py` (unledgered-number, abstract and literature-citation tests), `paper/drift.py`,
  `paper/number-ledger.md`; render kernel pinned to the venv (`jupyter: hfa`). Two typed digits were wrong
  (.048 → .047, −0.70 → −0.69) and four spelled counts ("seven" → "eight" of eight cells).
- **B — claim audit**, G1–G6 + B.S (above). Two data fixes were inserted mid-stage: zero-attendance (2026-09-15) and
  reopening-zeros (2026-09-16/17), which moved the headline to nfl +0.050 · nba +0.006 · nhl +0.011 · mlb −0.021.
- **C — citations** primary-verified; bib 12 → 20; Wikipedia gone; Farnell's NFL null carried.
- **D — voice**: six rewrite groups, every claim kept, zero attribution drift.
- **E1 — whole-paper review**: spec-change disclosure, MLB win admitted as the one cell against a full effect.
- **E2 — gates** (above). Next: the user's publish decision, then ESPN cache deletion.
- **E3 — docs** (2026-09-22): this wrap-up, CLAUDE.md Status, paper-writing-guide tools section, pitfalls, and a
  targeted README sweep (the 2026-09-18 sweep's unverified items + post-sweep paper fixes). README's "un-flagging the 39
  NYI dual-arena games moves [NHL win%] by 0.003" was wrong twice: 31 regular-season games, and the move is **0.0003**
  (margin 0.003; both ≤ 0.02 SE) once travel is filled in. Un-flagging alone moves nothing, because `add_travel` nulls
  travel on relocated rows and the fit drops them listwise. Also "game-clustered" → team-clustered (p = .039), Status,
  the Phase 8 row, 22 → 23 tables. "482 of 952 empty" re-verified (all 2021 games incl. playoffs).
- **README rewrite** (2026-09-22): 367 → ~100 lines, written for portfolio readers. Build history, the roadmap and
  phase jargon were cut (this log already holds them). Numbers now come from `twfe_cross_sport.csv` and
  `descriptive_hfa.csv`, and the ceiling wording follows the paper abstract (per-unit basis named, with the rescaled
  caveat). The NFL leave-2018-out caveat is kept. `.gitignore` now un-ignores `results/figures/twfe_crowd_effect.png`
  so the README can embed it.
- **Publish prep** (2026-09-22): final skim found one render typo (`empty-`/newline → "empty- stadium", §6.2), the
  RI "six assignments" line now names MLB's five, and the NHL "smallest relative" claim says "in magnitude" (it is an
  |coef| comparison; MLB's is −4× its HFA). Internal review tags (`E1 Mxx`, `B.S`, fix-round refs) stripped from qmd
  comments. `.gitignore`: `paper/` whitelists `hfa.qmd`/`hfa.pdf`/`references.bib` (the global `*.pdf` rule had
  blocked the README's PDF link); `results/` is no longer ignored, because the paper cites its CSVs by name and reads
  `pre_zero_fix/`/`pre_reopen_fix/` snapshots nothing regenerates. README: register the `hfa` kernel (`--sys-prefix`)
  and render with `QUARTO_PYTHON` (plain `quarto render` failed: kernel not found). Re-rendered; 8/8 paper checks, 179/179
  repo tests.
- **Summary for outside readers** (2026-09-22): `docs/summary.md` (~900 words), linked from the README. Numbers copied
  from the rendered paper; spot-checked against `twfe_cross_sport.csv` and `noise_floor.csv`. No number gate: re-sweep it
  after any table regeneration.
- **Raw-cache archive** (2026-09-22): re-ran descriptive/twfe/did/sensitivity from the parquets; `results/` byte-identical
  to `65d0b4d`. ESPN caches (19.0 GiB, 36,855 files) compressed to `~/hfa-espn-cache.tar.zst` (726 MiB, `zstd -t` OK,
  file count matched), then the user deleted `data/raw/*/espn`. Compressed rather than deleted because the endpoints are
  unofficial: a re-pull may not reproduce the published numbers.
