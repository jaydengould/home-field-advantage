# Zero-attendance reporting artifacts — design

Date: 2026-09-15. Status: draft for user approval. Inserted between Phase 8 stages B.G2 and B.G3
(user decision 2026-09-15); Phase 8 resumes at B.G3 on the regenerated tables.

## 1. Problem

`crowd_pct == 0` is treated everywhere as a real empty stadium. It is not always one. ESPN's summary
endpoint returns `attendance == 0` for some games that were played in front of fans. Found in the
Stage B.G2 claim audit (`stage-b-G2-audit.md` row G2-16) and characterized by the controller from
`data/interim/*.parquet` (per-game list: `.superpowers/sdd/zero-attendance-fix/zero_attendance_games.csv`).

Regular-season zero-attendance games outside the treated seasons and bubbles:

| sport | season | zeros | what they are |
|---|---|---|---|
| mlb | 2018 / 2019 / 2022 / 2023 | 16 / 14 / 28 / 17 | 63 of 75 same-day doubleheader games (55 with a non-zero partner); the rest isolated. Full-crowd seasons → reporting artifacts |
| nba | 2019 / 2023 | 1 / 4 | US arenas, full-crowd seasons → artifacts |
| nba | 2022 | 15 | 12 Toronto home games 2022-01-01…02-13 (Ontario caps, real); 3 US games Oct–Nov 2021 → artifacts |
| nhl | 2022 | 10 | all Canadian home teams 2021-12-17…2022-01-31 (Quebec/Ontario closures, real) |
| nhl | 2023 | 7 | WPG, CGY and US teams in 2022-23 → artifacts |
| nfl | 2023 | 1 | IND–CLE → artifact |

Inside treated seasons: MLB 2021 has 32 zeros (21 doubleheaders). All 30 MLB clubs admitted fans in
2021 ([ESPN](https://www.espn.com/mlb/story/_/id/31009930/mlb-season-2021-which-teams-fans-stands-opening-day),
[Forbes](https://www.forbes.com/sites/maurybrown/2021/03/07/team-by-team-look-at-mlb-fan-attendance-for-opening-day-2021/)),
so every MLB 2021 zero is an artifact. NFL 2020, MLB 2020, NBA 2021, NHL 2021 zeros are genuine
closed-door games (in bulk; see §6 for the residual).

Why it matters: these games enter estimator (a) as dose 0 in full-crowd periods, attenuating the
dose contrast, and they are the entire MLB-2020 `control_overlap` (75 / 9,687 = 0.77%). A controller
diagnostic (MLB only, control-season zeros dropped) moved MLB 6a by ≤ .002 on win probability and
.02 on margin — a credibility fix, not an expected change in findings.

## 2. Rule (pre-committed before any regenerated estimate is seen)

> An ESPN `attendance == 0` is a **real** observation only if the game falls inside a documented
> restriction window for its sport. Outside every window, a zero is a **reporting artifact**: the
> game stays in the panel, but its `attendance` and `crowd_pct` are set to **null** (unknown).

Windows, stored per sport in `config/sports.yaml` under a new key `zero_attendance_windows` (list of
`{start, end, home_teams?}` in local game date, inclusive; `home_teams` omitted = all teams):

| sport | window | source |
|---|---|---|
| nfl | 2020 regular season + postseason (the 2020 season window) | all teams restricted 2020 (existing treated-season basis) |
| mlb | 2020 season window only (**not** 2021) | 2020 closed-door season; 2021 all clubs admitted fans (above) |
| nba | 2020 bubble (from 2020-07-30); the 2021 season window; Canadian home teams (TOR) 2021-12-16…2022-02-20 | bubble; treated season; Ontario 1,000-cap from 2021-12-31 and 500-cap until 2022-02-21 ([ESPN](https://www.espn.com/nba/story/_/id/32966099/toronto-raptors-maple-leafs-halt-ticket-sales-limit-crowds-1000-fans-due-covid-surge), [Global News](https://globalnews.ca/news/8622386/scotiabank-arena-ontario-covid-capacity-limits/)) |
| nhl | 2020 bubble (from 2020-08-01); the 2021 season window; Canadian home teams (MTL, OTT, TOR, WPG, CGY, EDM, VAN) 2021-12-16…2022-02-20 | bubble; treated season; Quebec closed-door from 2021-12-16 ([CBC](https://www.cbc.ca/news/canada/montreal/habs-flyers-bell-centre-closed-doors-1.6288949)) + Ontario as above |

Windows are written as data, so the rule itself is sport-blind. Exact per-sport season-window dates
are taken from each loader's existing season-window function, not retyped.

Why null, not drop: dropping a game would change neighbors' rest days, travel and the Elo chain, and
would remove games from estimator (b), which never uses dose. Null keeps every non-dose feature and (b)
unchanged; estimator (a) drops the game through its existing listwise deletion (`twfe._prep` →
`dropna`), visible in `n_dropped`.

Why not impute the doubleheader partner's attendance: we cannot verify single-admission, and 12 of 75
MLB control zeros and all non-MLB artifacts have no partner.

## 3. Where the code goes

- `config/sports.yaml`: `zero_attendance_windows` per sport.
- `src/features/build.py`: one sport-blind pure helper `null_reporting_zeros(panel, windows)` —
  sets `crowd_pct` null for `attendance == 0` rows outside every window; returns (panel, count).
  `build(sport)` calls it on the interim panel before re-validation, so `data/processed` carries the
  correction and `data/interim` stays the as-reported loader output. **Revised 2026-09-15 (controller,
  after code survey):** not in the loaders, because re-running the NFL loader re-downloads schedules
  via `nfl_data_py` (not cached) — a network dependency the "local cache only" constraint forbids.
  The rule has no sport branching (windows are config data), so it satisfies principle 1.
- `src/schema.py`: only `crowd_pct` becomes `nullable=True`. `attendance` keeps the as-reported 0
  (an honest record of what ESPN said); the crowd_pct == attendance/capacity check already skips
  null crowd_pct.
- `derive_capacity` is unaffected (venue-season max ignores zeros).
- Downstream (`src/features`, `src/models`, `src/viz`): no logic change; audit every `crowd_pct` use
  for NaN safety (e.g. shares computed as `(x == 0).mean()` over a column containing NaN, quantiles,
  `fit_d["crowd_pct"] == 0` splits, season-dummy fits that drop `crowd_pct` but whose `_prep`
  dropna may still include it). A NaN-unsafe site is fixed to exclude null dose explicitly.
- The existing "games ESPN has no attendance for are dropped" behavior is **out of scope** and unchanged.

## 4. Regeneration and sensitivity

1. Archive the current tables verbatim to `results/tables/pre_zero_fix/` (all 21 CSVs + their sha256)
   before anything is rebuilt. The frozen 6a *specification* is unchanged; only the data are corrected.
2. Rebuild `data/processed` from the existing `data/interim` (no loader re-run, no network), then
   every `results/tables/*.csv` via the existing module `main()`s. Expected byte-identical: the
   tables that never read `crowd_pct` (`descriptive_hfa`, `did_*`).
3. New table `results/tables/zero_attendance_sensitivity.csv`: per sport × outcome, 6a pooled coef /
   SE / CI / n_obs before (archived) and after, plus the per-sport count of nulled games by season.
4. Paper: Stage A's live expressions pick up new values automatically. `paper/number-ledger.md`,
   `abstract_expected()` and typed abstract numbers are re-checked; the abstract's typed headline
   numbers are updated if they change. The Data section discloses the rule and the count (B.G2 rows
   G2-16 / G2-24, resumed after this fix); @sec-robust reports the sensitivity table.

## 5. Acceptance

- Tests: new unit tests for the helper (inside/outside window, team-scoped window, zero vs non-zero,
  null propagation) and schema nullability; full suite passes (count grows from 158).
- Nulled-game counts match §1 exactly (MLB 75 control + 32 in 2021; NBA 1+3+4 = 8; NHL 7; NFL 1;
  zero nulled inside NFL 2020 / MLB 2020 / NBA 2021 / NHL 2021 / bubbles / Canadian window).
- Panel row counts unchanged (30,169 games); `validate()` passes for all four sports.
- Every table regenerates; any table whose non-MLB rows change beyond the NBA/NHL/NFL artifact
  games is explained. Pre/post diff of headline coefficients reported to the user **before** the
  paper is re-rendered.
- Paper gates (`check_paper.py`, drift from snap-B-G2 end state) pass; every numeric drift traces to
  this fix.

## 6. Known residual, disclosed not fixed

Inside NBA 2021 and NHL 2021 (and NFL 2020), a reporting zero for a game that actually admitted a
partial crowd would be indistinguishable from a closed-door game by this rule. Diagnostic only (no
rule change): count treated-season zeros that occur after the home team's first non-zero-attendance
home game of that season; report the count in data-pipeline.md and the paper's limitations.

## 7. Docs

`docs/data-pipeline.md` (rule, windows, counts, residual) · `docs/design-decisions.md` (null-not-drop,
window rule) · `CLAUDE.md` fact "`crowd_pct == 0` is a REAL value" → real inside documented restriction
windows; reporting zeros outside them are null; headline numbers if they change · `docs/results.md`
· `docs/phase-log.md`.
