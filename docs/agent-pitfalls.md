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
  estimation sample the range is 0 → 0.400 with p99 at 0.288.
- **Filter on `is_bubble`, never `neutral_site`** — 58 of 130 NHL bubble games are not flagged
  neutral.

- **6a and 6b are in different units.** 6a is per unit of `crowd_pct`; 6b is a level
  (HFA_full − HFA_reduced). For months the paper compared them unscaled ("differ by 4–268%",
  "6b smaller in the NFL, as expected from raw vs adjusted") and a caption called both per-unit;
  every audit round passed it. Compare 6b with 6a × dose gap (`dose_overlap` all_treated
  control_mean − treated_mean); MLB's gap is 0.33, so the unscaled comparison was off ~3× there.

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
- **Don't draft a citation's wording before its source is read.** C1's approved MLB sentence ("bias not
  shown to depend on the crowd") was contradicted by a paper found but not yet read (Saiegh & Wong
  2026); and a sentence went into the paper citing an NHL source the verifier had already flagged as
  not supporting it. Read → then write; re-read the verifier's caveats before pasting its proposal.
- **A 403 or Cloudflare "Just a moment..." page is not "unreadable".** C2's search agent marked
  McMahon & Quintanar abstract-only; the Wayback Machine had the repository PDF
  (`archive.org/wayback/available?url=…`, then fetch `web/<ts>id_/<url>`). Try the archive and
  OpenAlex `locations` before declaring a source unread. Hsu (2024) still had no copy anywhere.
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
- **A residual diagnostic defined relative to a team's first non-zero game is blind to teams that
  report zero all season.** Fix 1's zero-attendance residual (2026-09-15) counted only zeros
  *after* a team's first non-zero home game, so a team whose ESPN attendance reads 0 for **every**
  treated-season home game — 29 team-seasons across nfl/nba/nhl, including three of the four
  NBA all-zero teams that actually hosted fans (IND, MIA, SAC — the fourth, OKC, is verified
  `no_fans` all season) and two of NFL's four originally-flagged teams that, under the amended
  fan definition, kept sourced `fans_from` entries (GB, PHI; DET and MIN were re-verdicted to
  `no_fans`) — never appeared in it and was silently coded as a real empty stadium.
  The reopening-zeros fix (2026-09-16) caught this by auditing "reports zero the whole season" as
  its own category (`kind=all_zero` in `team_audit.csv`), generated from the data, not from the
  residual. **Count all-zero-season entities separately from a diagnostic scoped to "after the
  first X"; the two failure modes don't share a codepath.**
- **A cited "effect" can be a raw mean.** Ganz & Allsop's NBA 2.13 → 0.44 was carried for phases as
  their causal estimate and converted into our units; the primary source's tables show it is a raw
  2020–21 gap (p = .09) and the causal estimates are +4.53 (FE) / +1.74 per 1,000 fans (IV). Read the
  source's tables, not its abstract or a secondary summary; "1.69 ≈ our 1.34" looked like
  corroboration and hid it. The same frame survived in the docs after the paper was fixed.
- **Label the clustering from the code, not from memory.** The NHL within-2021 CI was called
  "game-clustered" in three ledgers/docs; `within_season_dose` calls `twfe.fit`, which clusters by
  home team (29 clusters).
- **"This number appears in some CSV" proves nothing.** The CSVs hold thousands of values: 43% of
  all 3-decimal numbers below 1 match *some* cell by chance, so a grep/match sweep passed the stale
  MLB triple `0.146/0.184`. Verify a docs number by naming its exact table, row and column (or the
  panel computation), never by finding it somewhere.
- **Row-count checks cannot see duplicates.** The zero-fix verification asserted "30,169 rows before
  and after" and passed while 23 MLB rows were duplicates. For a game-level panel, assert a unique
  `game_id` (now in `validate()`) and check same start + teams + score, not just the length.
- **Live `{python}` does not work in a `#| tbl-cap:` / `#| fig-cap:` chunk option** — it renders as
  literal `{python} …` text in both HTML and PDF (render-tested twice, B.G4). Every number in every
  caption in `paper/hfa.qmd` is therefore hardcoded, ledgered, and goes stale silently on any data
  regeneration: `@tbl-mlbsplit`'s `n` was 12,893 against a CSV that said 12,871 after the MLB dedup,
  and the drift check cannot catch it because a hardcoded caption number never drifts. After
  regenerating `results/tables/`, re-check every caption number by hand.
- **Bound every superlative to a named table.** "The largest positive win-probability estimate
  anywhere in the study" was false twice in one section: `within_season_dose.csv` holds an NBA
  win coefficient of +0.387 (4.6× the claim) and `season_effects.csv` an NFL deviation of +0.129,
  neither of them printed, because the chunk that would show them filters to two sports. The same
  bug sat in "the largest within-season magnitude anywhere in this study" (NBA margin is +5.55).
  A superlative over *printed* results is checkable; one over "the study" must be checked against
  every CSV, including the rows no table displays.
  **Narrowing a superlative to "in @tbl-X" is not a fix when tbl-X is itself a filtered view.**
  "Largest within-season magnitude in @tbl-within" was true only because the table printed NHL
  and MLB while the prose counted all eight fits; showing every league (B.S C-2, 2026-09-21)
  made it false again. Tables should show every row the prose counts over.
- **A figure that reproduces from nothing recurs.** Three separate claims in this paper quoted a
  multiplier no artifact produces: "0.14–0.76×" (imported from a different sensitivity, true range
  0.44–0.77), "roughly fifty times" (true max 38), "four times larger" (true 12.5). Each survived
  because the surrounding sentence was plausible. When a claim quotes a ratio, recompute the ratio
  and name its numerator and denominator — do not check only that the direction is right.
