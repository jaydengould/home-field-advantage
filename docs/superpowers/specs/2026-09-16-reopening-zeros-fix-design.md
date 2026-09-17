# Treated-season reporting zeros after fans returned — design

Date: 2026-09-16. Status: draft for user approval. Inserted inside Phase 8 stage B.G5, between fix
round 1 and fix round 2 (user decision 2026-09-16). B.G5 resumes at fix round 2 on the regenerated
tables. Follows `2026-09-15-zero-attendance-fix-design.md` (called "fix 1" below) and extends its rule.

## 1. Problem

Fix 1 treats every ESPN `attendance == 0` inside a restriction window as a real empty stadium. Its
§6 residual diagnostic counted only zeros *after* a team's first non-zero home game that season, so a
team whose ESPN attendance reads 0 for **every** treated-season home game never showed up in it.
That diagnostic undercounts. Found by the B.G5 re-review (N1, via Ganz & Allsop's decision to drop
MIA/IND/SAC) and characterized by the controller on 2026-09-16 (ledger, `phase8-polish/progress.md`).

**Teams whose ESPN attendance is 0 for the whole treated regular season (model sample):**

| sport | season | teams |
|---|---|---|
| nba | 2021 | IND, MIA, OKC, SAC |
| nhl | 2021 | BUF, CGY, DET, EDM, MTL, NSH, OTT, STL, TOR, VAN, WPG |
| nfl | 2020 | BUF, CHI, DET, GB, LA, LAC, LV, MIN, NE, NYG, NYJ, PHI, SEA, SF |
| mlb | 2020 | all 29 home teams (real: no fans in 2020 regular season; not re-audited) |

Controller spot checks (web, 2026-09-16): OKC hosted no fans all season (real). MIA had fans from
2021-01-28, IND from 2021-01-24, SAC from 2021-04-20, STL from 2021-02-02, BUF (NHL) from 2021-03-20,
DET (NHL) from about 2021-03-10, NSH "in January" (date unconfirmed). All coded as empty.

**Teams with zeros after their first fans game (fix 1's residual, model sample):**
nfl ARI 3, BAL 4, CLE 1, DEN 3, PIT 3, WAS 3 · nba ATL 2, BOS 4, CLE 5, MEM 2, MIN 2, UTAH 2 ·
nhl FLA 1, NJ 1, NYI 1. Fix 1 left these at 0 "by rule". Some NFL ones may be real December 2020
re-closures; the isolated NBA ones are probably artifacts.

**Why it matters.** Scratch sensitivity (frozen `twfe.fit`, post-reopening zeros nulled, nothing
written): NBA pooled win +0.0157 → +0.0059 (−0.38 SE), restricted −0.44 SE, margin −0.28/−0.34 SE;
NHL (approximate dates) +0.03 to +0.38 SE. No interval conclusion flips, but the paper's NBA headline
number moves, and the Ganz & Allsop presence mapping (N1) depends on these same zeros.

## 2. Rule (pre-committed; the 2026-09-16 scratch estimates were seen, see §6)

> Inside a restriction window, `attendance == 0` is a real empty stadium only while that home team
> had **not yet admitted fans** that season, or during a **sourced re-closure**. A zero on or after
> the team's `fans_from` date, outside any re-closure, is a reporting artifact: `crowd_pct` → null,
> exactly as in fix 1.

`fans_from` for each (sport, treated season, home team) is the **earlier** of:
1. the date of the team's first home game with non-zero ESPN attendance that season (data), and
2. the date of its first home game with fans according to a public source (team, league or news).

Pre-committed edge cases:
- **Who counts as fans (amended 2026-09-16, user decision after the Task 1 source review):** spectators
  from the public, ticketed **or** invited (season-ticket holders, invited healthcare workers or first
  responders attending as guests). **Not** fans: anyone affiliated with a team or working the event
  (players' families, team staff, media, on-duty security/medical personnel). A game with only
  affiliated or working people present is an empty stadium. Why: a spectator's size is carried by the
  dose, so category exclusions by crowd size would presuppose the effect; affiliated/working people
  are what sources mean when they say "no fans".
- **Source says no fans all season** (e.g. OKC): no `fans_from`; its zeros stay real.
- **No source found either way** for an all-season-zero team: its zeros stay real, and the team is
  listed as unverified in the disclosure. We do not guess a date.
- **Source gives only a month or a vague date**: use the earliest home game the source definitely
  covers (e.g. "fans at the Feb 14 game" → that game). Never round backward.
- **Re-closure**: a zero after `fans_from` stays real only if a source documents that the specific
  game, or a period covering it, was closed to fans. No source → null. (User, 2026-09-16: a real
  re-closure of a reopened stadium will be documented online; absence after a recorded search is
  evidence the zero is an artifact. The audit row records the queries tried.)
- **Playoffs and bubbles** are excluded from every model; audit them only when they share a window
  with regular-season games. Relocated games (TOR in Tampa) are excluded and not audited.
- Audit scope is **exhaustive**: every home team in every treated season of nfl 2020, nba 2021 and
  nhl 2021 that has at least one zero in the model sample (the two lists above). MLB 2020 is not
  audited (league-wide closed-door regular season, and hub-bubble postseason already neutral). MLB
  2021 zeros are already all null under fix 1.

Every audited team gets a verdict (`no fans all season` / `fans_from YYYY-MM-DD` / `unverified`), a
source URL, and any re-closure intervals, whichever way the estimate moves.

**Dates.** `date` in `data/processed` is UTC for NBA/NHL (an evening local game can carry the next
day's UTC date). `fans_from` is stored as the **UTC date of the first home game with fans**, and the
plan verifies that a home game for that team exists on that UTC date. Home teams never host two
games on one date in these leagues, so an earlier home game cannot share it.

## 3. Where the code goes

- `config/sports.yaml`, per sport: `fans_from: [{team, date, source}]` and
  `reclosures: [{team, start, end, source}]`. Data, not code, so the rule stays sport-blind.
  Data-derived `fans_from` dates (rule 1) are **not** typed into config: the helper computes them.
- `src/features/build.py`: extend `null_reporting_zeros` so a zero inside a window is an artifact
  when `date >= fans_from(team)` and no re-closure covers it, where `fans_from(team)` = min(first
  non-zero home game in that season, configured date). No new function unless the extension makes
  the helper unreadable. `build(sport)` already calls it on the interim panel.
- No loader change, no network, no schema change (`crowd_pct` is already nullable).
- Downstream is already NaN-safe for `crowd_pct` (fix 1 audited every use). Estimator (b) never
  reads `crowd_pct`.
- The audit worksheet (every team, verdict, date, URL, quote) lives at
  `.superpowers/sdd/reopening-zeros-fix/team_audit.csv` while we work; the final per-team table goes
  in `docs/data-pipeline.md`.

## 4. Regeneration and sensitivity

1. Archive the current tables verbatim to `results/tables/pre_reopen_fix/` (all 22 CSVs + SHA256SUMS)
   before rebuilding. The frozen 6a *specification* is unchanged; only the data are corrected.
2. Rebuild `data/processed` from `data/interim` (no loader re-run), then every table via the existing
   `main()`s. Expected byte-identical: `descriptive_hfa`, `did_*` (neither reads `crowd_pct`).
3. `zero_attendance_sensitivity.csv` (fix 1) must stay **byte-identical**: its "post" column means
   "after fix 1", so it reads `pre_reopen_fix/` as post, and its `n_nulled` counts only fix 1's nulls.
4. New `results/tables/reopen_zero_sensitivity.csv`, same columns as fix 1's table: per sport ×
   outcome, 6a pooled coef / SE / CI / n_obs before (`pre_reopen_fix/`) and after, plus `n_nulled`
   for this fix.
5. Paper: live expressions update automatically. Re-check the abstract's typed numbers,
   `abstract_expected()` and the number ledger; update any typed headline number that changes.
   @sec-zero and the Data section's zero-attendance paragraph disclose the second rule, its count
   and the unverified teams; the "residual" sentence is replaced. The G5 fix-round-2 brief (N1) is
   written **after** this fix, against the new numbers.

## 5. Acceptance

- Unit tests for the extended helper: zero before / on / after `fans_from`; data-derived vs config
  date (earlier wins); re-closure keeps a zero real; team with no `fans_from` keeps zeros; zeros
  outside every window unchanged from fix 1. Full suite passes (count grows from 171).
- Every team in the §1 lists has a row in the audit table with a verdict and a source (or
  `unverified`). A test or an assert fails if a model-sample zero after a team's first non-zero game
  stays real without a configured re-closure.
- Panel row counts unchanged; `validate()` passes for all four sports; MLB `data/processed` byte-identical.
- Pre/post diff of every 6a headline coefficient reported to the user **before** the paper is
  re-rendered, with fix 1's table confirmed byte-identical.
- Paper gate (`check_paper.py`), both renders (known warnings only), and drift traced to this fix.

## 6. Legitimacy and what the paper must say

This is a data correction after estimates were seen, so it needs to be clearly not a forking path:
- **Exhaustive and mechanical**: the rule covers every zero-bearing team in every treated season,
  not the teams that move the estimate. The scratch run shows it moving NBA toward zero and NHL away
  from zero; both ship.
- **Not outcome-blind**, and the paper says so: the problem was found through a literature
  comparison, the scratch sensitivity was seen before this spec, and both versions ship in
  `reopen_zero_sensitivity.csv`.

## 7. Known residual, disclosed not fixed

- Games where fans were present but ESPN reported a non-zero *wrong* number are out of scope.
- `unverified` teams keep real-zero coding; the disclosure names them.

## 8. Docs

`docs/data-pipeline.md` (rule, per-team table, counts, residual replaced) ·
`docs/design-decisions.md` (why `fans_from`, why min of data and source) · `CLAUDE.md` `crowd_pct == 0`
fact and headline numbers if they change · `docs/results.md` · `docs/phase-log.md` ·
`docs/agent-pitfalls.md` (a residual diagnostic defined relative to the first non-zero game is blind to
all-zero teams).
