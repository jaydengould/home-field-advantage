# Agent pitfalls

Mistakes actually made on this project, by agents, that cost a review round or shipped a wrong
number. Update this file when a new one bites. Keep it to things that recurred or nearly escaped.

## Verification

- **"Verified / zero discrepancies" has been false twice.** A reproduction sweep reported as
  clean had one transcription error in it; a `'clean null'` grep reported as run was never run.
  Both were caught by a *later* reviewer, not by the agent that claimed the check. **Treat any
  such line in project docs as a claim to re-run, not a result.** A reported pass stops anyone
  else from looking — that is the whole hazard.
- **The strongest check is a live refit, not a re-read.** Re-reading a CSV goes stale; refitting
  and matching at `rtol=1e-10` cannot. Prefer it when confirming frozen numbers.
- **A failing test may be right and the assertion wrong.** The first `noise_floor` draft asserted
  `mde_floor <= mde_current` — backwards, and it silently compared two different scaling bases.
  The fix was deleting the mixed-basis column, not patching the assertion.

## Scaling and sign conventions

- **The units trap** (three separate confusions so far): per-unit-`crowd_pct` coefficients vs
  season-dummy/outcome-level effects are not interchangeable. See `docs/paper-writing-guide.md`.
- **`mlb_treated_split.csv` does not use 6b's sign convention.** `did.py` publishes
  `crowd_effect = −coef`; that table reports the raw treated-year level unnegated. Reading
  +0.0595 as "crowd helped home" is backwards.
- **`within_season_dose.csv` carries TWO sample bases in one row and the CSV does not say so.**
  `crowd_min/max/p99` are on the broad exclusion-only `_prep` sample ("what doses exist at all");
  `raw_empty_mean`/`raw_fans_mean`/`n_empty`/`n_fans` are on the narrow fit sample (so
  `n_empty + n_fans == n_obs`). Deliberate, documented in the docstrings — but a writer reads the
  CSV. Never describe the support range and the raw means as coming from the same rows.
- **Generalising a statistic computed on a subset of sports.** The "control-season dose is
  ~0.88–0.93 units" caveat was computed from NFL and NBA only and was wrong for MLB on both
  sides. Check every sport before writing a range.

## Statistics traps specific to this design

- **Do not add full season FE** to the main model. They are near-collinear with the treatment
  and invert every sign. See `docs/design-decisions.md`.
- **`trend="none"` is required for within-season fits** — a linear trend on a single season
  raises "exog does not have full column rank".
- **Do not quote a coefficient outside its support** without saying so. NHL's within-2021 fit
  spans 0–0.40 and extrapolates 2.5×; MLB's *headline* extrapolates ~1.5×.
- **Statistics computed on excluded games are not results.** NHL's "richest within-season dose
  variation" selling point was measured on playoff games that no model ever sees. In the actual
  estimation sample the range is 0 → 0.400 with p99 at 0.283.
- **Filter on `is_bubble`, never `neutral_site`** — 58 of 130 NHL bubble games are not flagged
  neutral.

## Post-hoc additions need a stated legitimacy class

When adding an analysis after seeing results, say why it isn't p-hacking. The three classes used
here: **outcome-blind by construction** (`dose_overlap` reads only `crowd_pct` and `season`),
**exhaustive and mechanical** (leave-one-season-out — no choice to make, so nothing to fit to),
or **against our own interest** (the finding moves against our point estimate). If none applies,
don't add it.

## Process

- **Namespace SDD artifacts per phase.** A flat `.superpowers/sdd/` directory reuses `task-N-*`
  filenames across phases; a stale read of a previous phase's report looks like a fresh one. And
  don't read a task report before the agent returns a clean DONE.
- **Test fixability before declaring a limitation.** When asked "can we fix it?", compute the
  answer. The noise-floor decomposition is what turned "we're underpowered" into "more seasons
  would not help, and here is why."
- **Verify external constants with a web search before locking them into a spec.** Elo
  parameters, published effect sizes, and citations have all been wrong from recollection once.
- **`QUARTO_PYTHON` does not choose the Jupyter kernel.** Until Phase 8 stage A, every paper render
  silently ran on a user-level kernelspec (`mlb-edge-finder`, system Python, different
  pandas/numpy, no `linearmodels`); an agent then hand-reimplemented the TWFE estimator in the
  paper to dodge the missing import. The paper now pins `jupyter: hfa`, a kernelspec installed
  inside `.venv`. Check the render log says `Starting hfa kernel`. Never re-implement an estimator
  in a `.qmd` chunk — import `src`.
- **The number-drift check is digits-only.** Spelled counts ("seven of eight") that become live
  can change words without tripping it; diff rendered text word-by-word against the baseline too.
- **Inline `{python}` inside `$…$` math breaks on decimals and `{,}`** (Quarto escapes `14.42` →
  `14\.42`); bare integers work (`$k = `{python} len(SPORTS)`$`).
- **A validated-looking zero can be a reporting artifact.** "`crowd_pct == 0` is real" held for two
  phases while 119 ESPN zeros sat in full-crowd seasons (mostly MLB doubleheaders), and they were
  the entire MLB-2020 dose overlap. Check zeros against when restrictions actually applied, and
  look for a structural pattern (doubleheaders, one arena) before trusting them as treatment.
- **A quick diagnostic undercounts when it drops only part of the artifact set.** The pre-spec
  MLB check dropped control-season zeros only and predicted ≤ .02 of margin movement; the real fix
  (which also nulled the MLB 2021 zeros) moved it .038.
- **Row-count checks cannot see duplicates.** The zero-fix verification asserted "30,169 rows before
  and after" and passed while 23 MLB rows were duplicates. For a game-level panel, assert a unique
  `game_id` (now in `validate()`) and check same start + teams + score, not just the length.
