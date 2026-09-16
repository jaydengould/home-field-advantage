# Zero-Attendance Reporting Artifacts — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Null `crowd_pct` for ESPN zero-attendance games outside documented restriction windows, regenerate every table, and keep the pre-fix numbers as a sensitivity.

**Architecture:** Per-sport restriction windows live in `config/sports.yaml`. One sport-blind helper in `src/features/build.py` nulls `crowd_pct` where `attendance == 0` falls outside every window; `build()` applies it, so `data/processed` is corrected while `data/interim` stays as reported. Models already drop null dose listwise; tables regenerate through the existing module `main()`s.

**Tech Stack:** Python 3.11+ `.venv`, pandas, PyYAML, pytest, linearmodels (existing), Quarto CLI for the paper.

**Spec:** `docs/superpowers/specs/2026-09-15-zero-attendance-fix-design.md` (approved 2026-09-15; §3/§4 revised same day — helper in `build.py`, only `crowd_pct` nullable, no loader re-run). Executors read the spec first.

## Global Constraints

- **Git is user-owned:** no `git commit`/`push`/`branch`. Replace every commit step with a snapshot: `.superpowers/sdd/phase8-polish/pkg.sh snap ZA-<task>` (the script snapshots paper, docs, results/tables, src, config, tests, CLAUDE.md).
- Workspace: `.superpowers/sdd/zero-attendance-fix/` (briefs, reports, ledger `progress.md`). Phase 8's ledger is `.superpowers/sdd/phase8-polish/progress.md` — append a pointer line there at start and end.
- `data/raw/` and `data/interim/` are **not modified**. No loader is re-run. No network.
- The frozen 6a specification (`twfe.fit` defaults, `CONTROLS`, `_exclusion_mask`) is not changed.
- `crowd_pct == 0` inside a window stays 0; it is never coerced to null.
- Treated seasons are read from `config/sports.yaml`; never hardcode them in code.
- No sport branching in `src/features` or `src/models`.
- Project test gate: `.venv/bin/pytest tests -q` (158 before this plan). Paper gate: `cd paper && ../.venv/bin/pytest check_paper.py test_tools.py -q`.
- Render (from `paper/`, foreground, tee log): `QUARTO_PYTHON=../.venv/bin/python quarto render hfa.qmd` and `... --to plain --wrap=none`.
- **User checkpoint** after Task 4 (pre/post coefficient diff) — stop and show the user before Task 5.

## Rule (verbatim from spec §2 — do not change)

An `attendance == 0` is real only if the game falls inside a documented restriction window for its
sport; outside every window, `crowd_pct` is set to null.

Expected nulled counts (acceptance, from `.superpowers/sdd/zero-attendance-fix/zero_attendance_games.csv`):

| sport | season → nulled |
|---|---|
| mlb | 2018: 16 · 2019: 14 · 2021: 32 · 2022: 28 · 2023: 17 (total 107) |
| nba | 2019: 1 · 2022: 3 · 2023: 4 (total 8) |
| nhl | 2023: 7 |
| nfl | 2023: 1 |

Zero nulled in: NFL 2020, MLB 2020, NBA 2021, NHL 2021, NBA/NHL 2020 bubble games, Canadian home games 2021-12-16…2022-02-20.
(Counts include playoff rows if any; the listed seasons have no zero-attendance playoff games.)

---

### Task 0: Workspace, archive, baselines

**Files:**
- Create: `results/tables/pre_zero_fix/*.csv` (copies), `results/tables/pre_zero_fix/SHA256SUMS`
- Create: `.superpowers/sdd/zero-attendance-fix/progress.md`, `.superpowers/sdd/zero-attendance-fix/processed_pre/*.parquet`

- [ ] **Step 1: Archive tables and processed panels**

```bash
cd /Users/jaydengould/Documents/projects/home-field-advantage
mkdir -p results/tables/pre_zero_fix .superpowers/sdd/zero-attendance-fix/processed_pre
cp results/tables/*.csv results/tables/pre_zero_fix/
(cd results/tables/pre_zero_fix && shasum -a 256 *.csv > SHA256SUMS)
cp data/processed/*.parquet .superpowers/sdd/zero-attendance-fix/processed_pre/
shasum -a 256 -c .superpowers/sdd/phase8-polish/baseline/tables.sha256 | grep -c ': OK'
ls results/tables/pre_zero_fix/*.csv | wc -l
.venv/bin/pytest tests -q 2>&1 | tail -1
```

Expected: `21`, `21`, `158 passed`.

- [ ] **Step 2: Ledger** — create `.superpowers/sdd/zero-attendance-fix/progress.md` with first line `# SDD ledger — plan: docs/superpowers/plans/2026-09-15-zero-attendance-fix.md` and `Task 0: complete (21 tables archived, 158 passed)`. Append to the Phase 8 ledger: `Zero-attendance fix STARTED — ledger .superpowers/sdd/zero-attendance-fix/progress.md`.

- [ ] **Step 3: Snapshot** `.superpowers/sdd/phase8-polish/pkg.sh snap ZA-0`

---

### Task 1: Windows config, schema nullability, helper, wiring (TDD)

**Files:**
- Modify: `config/sports.yaml` (add `zero_attendance_windows` to each sport)
- Modify: `src/schema.py` (`crowd_pct` → `nullable=True`)
- Modify: `src/features/build.py` (add `null_reporting_zeros`, `_zero_windows`; call in `build`)
- Test: `tests/test_features.py`, `tests/test_schema.py`, `tests/test_config.py`

**Interfaces:**
- Produces: `null_reporting_zeros(panel: pd.DataFrame, windows: list[dict]) -> tuple[pd.DataFrame, int]` — returns a copy with `crowd_pct` null on reporting zeros, and the count nulled. `_zero_windows(sport: str) -> list[dict]` reads config.
- Window dict keys: `seasons` (list[int]) **or** `start`/`end` (ISO date strings, inclusive, compared to the panel's `date` column normalized to day); optional `home_teams` (list[str]). A row is inside a window if every present key matches.

- [ ] **Step 1: Write failing tests** — append to `tests/test_features.py`:

```python
from src.features.build import null_reporting_zeros


def _zpanel(rows):
    return pd.DataFrame(rows, columns=["season", "date", "home_team", "attendance", "crowd_pct"]).assign(
        date=lambda d: pd.to_datetime(d["date"]))


def test_zero_outside_every_window_is_nulled():
    p = _zpanel([(2019, "2019-05-01", "BOS", 0, 0.0)])
    out, n = null_reporting_zeros(p, [{"seasons": [2020]}])
    assert n == 1 and out["crowd_pct"].isna().all()


def test_zero_inside_season_window_stays_zero():
    p = _zpanel([(2020, "2020-08-01", "BOS", 0, 0.0)])
    out, n = null_reporting_zeros(p, [{"seasons": [2020]}])
    assert n == 0 and (out["crowd_pct"] == 0.0).all()


def test_nonzero_attendance_never_nulled():
    p = _zpanel([(2019, "2019-05-01", "BOS", 30000, 0.8)])
    out, n = null_reporting_zeros(p, [])
    assert n == 0 and out["crowd_pct"].iloc[0] == 0.8


def test_date_window_is_inclusive_and_team_scoped():
    w = [{"start": "2021-12-16", "end": "2022-02-20", "home_teams": ["TOR"]}]
    p = _zpanel([
        (2022, "2021-12-16 23:00", "TOR", 0, 0.0),   # start day, in team -> real
        (2022, "2022-02-20", "TOR", 0, 0.0),         # end day -> real
        (2022, "2022-02-21", "TOR", 0, 0.0),         # after end -> artifact
        (2022, "2022-01-10", "BOS", 0, 0.0),         # wrong team -> artifact
    ])
    out, n = null_reporting_zeros(p, w)
    assert n == 2
    assert out["crowd_pct"].isna().tolist() == [False, False, True, True]


def test_helper_does_not_mutate_input():
    p = _zpanel([(2019, "2019-05-01", "BOS", 0, 0.0)])
    null_reporting_zeros(p, [])
    assert p["crowd_pct"].iloc[0] == 0.0
```

Append to `tests/test_schema.py`:

```python
def test_null_crowd_pct_is_valid():
    df = valid_panel()
    df["attendance"] = [0]
    df["crowd_pct"] = [float("nan")]
    validate(df)  # reporting-artifact zero: dose unknown, must not raise
```

Append to `tests/test_config.py` (read its existing loader helper first and reuse it):

```python
def test_every_sport_has_zero_attendance_windows():
    import yaml
    cfg = yaml.safe_load(open("config/sports.yaml"))
    for sport in ("nfl", "mlb", "nba", "nhl"):
        w = cfg[sport]["zero_attendance_windows"]
        assert isinstance(w, list) and w
        for win in w:
            assert ("seasons" in win) != ("start" in win)
            assert set(win) <= {"seasons", "start", "end", "home_teams"}
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/pytest tests/test_features.py tests/test_schema.py tests/test_config.py -q`
Expected: FAIL — ImportError `null_reporting_zeros`; schema test fails on "null(s) in non-nullable column"; config KeyError.

- [ ] **Step 3: Implement**

`config/sports.yaml` — add under each sport (keep existing keys/comments):

```yaml
nfl:
  # Real empty/capped games live only here; any attendance==0 outside these windows is an
  # ESPN reporting artifact and becomes null crowd_pct in data/processed (spec 2026-09-15).
  zero_attendance_windows:
    - {seasons: [2020]}
mlb:
  zero_attendance_windows:
    - {seasons: [2020]}            # NOT 2021: all 30 clubs admitted fans in 2021
nba:
  zero_attendance_windows:
    - {seasons: [2021]}
    - {start: "2020-07-30", end: "2020-10-31"}                         # Orlando bubble
    - {start: "2021-12-16", end: "2022-02-20", home_teams: [TOR]}      # Ontario caps
nhl:
  zero_attendance_windows:
    - {seasons: [2021]}
    - {start: "2020-08-01", end: "2020-10-31"}                         # Toronto/Edmonton bubble
    - {start: "2021-12-16", end: "2022-02-20", home_teams: [MTL, OTT, TOR, WPG, CGY, EDM, VAN]}
```

`src/schema.py`: `"crowd_pct":  Col("float", nullable=True, min=0.0, max=1.05),`

`src/features/build.py` — add (near `_elo_params`), and call in `build`:

```python
def _zero_windows(sport: str) -> list[dict]:
    return yaml.safe_load(CONFIG_FILE.read_text())[sport]["zero_attendance_windows"]


def null_reporting_zeros(panel: pd.DataFrame, windows: list[dict]) -> tuple[pd.DataFrame, int]:
    """attendance==0 is a real empty stadium only inside a documented restriction window
    (config zero_attendance_windows). Outside every window it is an ESPN reporting artifact:
    crowd_pct -> null (dose unknown). attendance keeps the as-reported 0. Sport-blind."""
    df = panel.copy()
    day = pd.to_datetime(df["date"]).dt.normalize()
    real = pd.Series(False, index=df.index)
    for w in windows:
        m = pd.Series(True, index=df.index)
        if "seasons" in w:
            m &= df["season"].isin(w["seasons"])
        if "start" in w:
            m &= (day >= pd.Timestamp(w["start"])) & (day <= pd.Timestamp(w["end"]))
        if "home_teams" in w:
            m &= df["home_team"].isin(w["home_teams"])
        real |= m
    artifact = (df["attendance"] == 0) & ~real
    df.loc[artifact, "crowd_pct"] = np.nan
    return df, int(artifact.sum())
```

In `build(sport)`, after `panel = pd.read_parquet(...)`:

```python
    panel, n_null = null_reporting_zeros(panel, _zero_windows(sport))
    print(f"{sport}: nulled {n_null} reporting-artifact zero-attendance crowd_pct")
```

- [ ] **Step 4: Run tests** — `.venv/bin/pytest tests/test_features.py tests/test_schema.py tests/test_config.py -q` → PASS. Then `.venv/bin/pytest tests -q` → all pass (158 + 7). If an existing test asserts `crowd_pct` non-nullable, report it — do not delete it; the fix is to update that assertion to the new rule and say so in the report.

- [ ] **Step 5: Snapshot** `pkg.sh snap ZA-1`

---

### Task 2: NaN-safety audit of every `crowd_pct` consumer

**Files:**
- Modify (only if a site is unsafe): `src/models/sensitivity.py`, `src/models/twfe.py` (non-spec helpers only), `src/viz/descriptive.py`, `paper/hfa.qmd` chunks, `paper/check_paper.py`
- Create: `.superpowers/sdd/zero-attendance-fix/task-2-audit.md`
- Test: `tests/test_sensitivity.py` (for any fixed site)

- [ ] **Step 1: List every consumer**

```bash
grep -rn "crowd_pct" src/models src/viz paper/hfa.qmd paper/check_paper.py | grep -v "^\s*#"
```

- [ ] **Step 2: Classify each hit** in `task-2-audit.md` as `| file:line | expression | NaN behavior | safe? |`. Known-safe patterns: `twfe.fit` (listwise `dropna` over regressors incl. `crowd_pct`); `dose_overlap` (`dropna(subset=["crowd_pct"])` first); `_collinearity_r2` (`dropna`); `.mean()/.min()/.max()/.quantile()` (skip NaN). **Unsafe** patterns to look for: `(x == 0).mean()` or `(x > 0).mean()` over a column that still contains NaN (NaN counts as False in the denominator); `len(...)` used as a denominator alongside a dose split; boolean masks `crowd_pct == 0` / `> 0` on an un-dropped frame whose two halves are expected to partition it (e.g. `within_season_dose` `empty`/`fans` from `_dose_fit_sample` — check whether that sample is post-`dropna`); paper chunks computing shares or counts from parquet `crowd_pct`.
  Note (expected, correct, not a bug): fits with `drop_controls=["crowd_pct"]` (season effects, RI, noise floor, LOSO season dummies) keep null-dose games, because dose is not in their regressor set.

- [ ] **Step 3: For each unsafe site**, write a failing test in `tests/test_sensitivity.py` using a tiny panel with one null `crowd_pct` row that shows the wrong share/count; then fix by dropping null dose before the computation (`.dropna(subset=["crowd_pct"])`). Run the test to PASS. If no unsafe site exists, write that in the audit and make no code change.

- [ ] **Step 4:** `.venv/bin/pytest tests -q` → all pass. Snapshot `pkg.sh snap ZA-2`.

---

### Task 3: Rebuild processed panels and verify counts

**Files:**
- Modify (regenerated): `data/processed/{nfl,mlb,nba,nhl}.parquet`
- Create: `.superpowers/sdd/zero-attendance-fix/task-3-verify.md`

- [ ] **Step 1: Rebuild**

```bash
.venv/bin/python -m src.features.build 2>&1 | tee .superpowers/sdd/zero-attendance-fix/build.log
```

Expected lines: `nfl: nulled 1`, `mlb: nulled 107`, `nba: nulled 8`, `nhl: nulled 7`; Elo accuracy lines identical to before (`grep elo_accuracy` in the log vs the paper's `data_elo_acc_*` values).

- [ ] **Step 2: Verify against the rule table and the pre-fix panels**

```bash
.venv/bin/python - <<'EOF'
import pandas as pd
EXP = {"mlb": {2018: 16, 2019: 14, 2021: 32, 2022: 28, 2023: 17},
       "nba": {2019: 1, 2022: 3, 2023: 4}, "nhl": {2023: 7}, "nfl": {2023: 1}}
tot = 0
for s, exp in EXP.items():
    new = pd.read_parquet(f"data/processed/{s}.parquet")
    old = pd.read_parquet(f".superpowers/sdd/zero-attendance-fix/processed_pre/{s}.parquet")
    assert len(new) == len(old), s
    assert new.drop(columns="crowd_pct").equals(old.drop(columns="crowd_pct")), f"{s}: non-dose column changed"
    changed = new["crowd_pct"].isna() & old["crowd_pct"].notna()
    assert (old.loc[changed, "attendance"] == 0).all()
    got = new[changed].groupby("season").size().to_dict()
    assert got == exp, (s, got, exp)
    assert new["crowd_pct"].isna().sum() == changed.sum()          # no other nulls
    tot += len(new)
print("OK rows", tot)
EOF
```

Expected: `OK rows 30169`. Any assertion failure → STOP and report (do not adjust windows).

- [ ] **Step 3: Residual diagnostic (spec §6, disclose only)** — count treated-season zeros (inside windows, `seasons` entries only) that occur after the home team's first non-zero-attendance regular-season home game of that season, per sport; write counts to `task-3-verify.md`.

```bash
.venv/bin/python - <<'EOF'
import pandas as pd, yaml
cfg = yaml.safe_load(open("config/sports.yaml"))
for s in ("nfl", "mlb", "nba", "nhl"):
    p = pd.read_parquet(f"data/processed/{s}.parquet")
    p = p[~p["is_playoff"]].sort_values("date")
    for yr in cfg[s]["treated_seasons"]:
        q = p[p["season"] == yr]
        first_fans = q[q["attendance"] > 0].groupby("home_team")["date"].min()
        z = q[(q["attendance"] == 0) & q["crowd_pct"].notna()]
        late = (z["date"] > z["home_team"].map(first_fans)).sum()
        print(s, yr, "real-window zeros", len(z), "after team's first fans game", int(late))
EOF
```

- [ ] **Step 4:** Snapshot `pkg.sh snap ZA-3`.

---

### Task 4: Regenerate tables and build the sensitivity table

**Files:**
- Modify (regenerated): all 21 `results/tables/*.csv`, `results/figures/*.png`
- Modify: `src/models/sensitivity.py` (add `zero_attendance_sensitivity`, call from `main`)
- Create: `results/tables/zero_attendance_sensitivity.csv`
- Test: `tests/test_sensitivity.py`

**Interfaces:**
- Produces: `zero_attendance_sensitivity(pre_dir: Path = TABLES / "pre_zero_fix") -> pd.DataFrame` with columns `sport, outcome, coef_pre, se_pre, ci_low_pre, ci_high_pre, n_obs_pre, coef_post, se_post, ci_low_post, ci_high_post, n_obs_post, n_nulled`. Reads pooled rows of `twfe_cross_sport`-equivalent per-sport CSVs (`twfe_{sport}.csv`, `sample == "pooled"`) from `pre_dir` and from `TABLES`; `n_nulled` = count of `attendance == 0 & crowd_pct.isna()` in `data/processed/{sport}.parquet` (all rows).

- [ ] **Step 1: Failing test** in `tests/test_sensitivity.py`:

```python
def test_zero_attendance_sensitivity_joins_pre_and_post(tmp_path, monkeypatch):
    import pandas as pd
    from src.models import sensitivity as S
    cols = ["sport", "outcome", "sample", "coef", "se", "ci_low", "ci_high", "n_obs"]
    row = lambda c, n: ["mlb", "home_win", "pooled", c, 0.01, c - 0.02, c + 0.02, n]
    pre, post = tmp_path / "pre", tmp_path / "post"
    pre.mkdir(); post.mkdir()
    pd.DataFrame([row(-0.019, 12893)], columns=cols).to_csv(pre / "twfe_mlb.csv", index=False)
    pd.DataFrame([row(-0.017, 12818)], columns=cols).to_csv(post / "twfe_mlb.csv", index=False)
    monkeypatch.setattr(S, "TABLES", post)
    monkeypatch.setattr(S, "SPORTS", ["mlb"])
    monkeypatch.setattr(S, "_n_nulled", lambda sport: 75)
    out = S.zero_attendance_sensitivity(pre_dir=pre)
    r = out.iloc[0]
    assert (r.coef_pre, r.coef_post, r.n_obs_pre, r.n_obs_post, r.n_nulled) == (-0.019, -0.017, 12893, 12818, 75)
```

(Read `sensitivity.py` first: if `SPORTS`/`TABLES` are imported names rather than module attributes, adapt the monkeypatch targets to what the module actually uses and note it in the report.)

- [ ] **Step 2:** Run → FAIL (`AttributeError: zero_attendance_sensitivity`).

- [ ] **Step 3: Implement** in `src/models/sensitivity.py`:

```python
def _n_nulled(sport: str) -> int:
    p = pd.read_parquet(f"data/processed/{sport}.parquet", columns=["attendance", "crowd_pct"])
    return int(((p["attendance"] == 0) & p["crowd_pct"].isna()).sum())


def zero_attendance_sensitivity(pre_dir: Path | None = None) -> pd.DataFrame:
    """Frozen 6a pooled estimates before vs after nulling ESPN zero-attendance reporting
    artifacts (spec 2026-09-15). Data correction only; the specification is unchanged."""
    pre_dir = pre_dir if pre_dir is not None else TABLES / "pre_zero_fix"
    keep = ["sport", "outcome", "coef", "se", "ci_low", "ci_high", "n_obs"]
    rows = []
    for s in SPORTS:
        pre = pd.read_csv(pre_dir / f"twfe_{s}.csv")
        post = pd.read_csv(TABLES / f"twfe_{s}.csv")
        pre, post = (d[d["sample"] == "pooled"][keep] for d in (pre, post))
        m = pre.merge(post, on=["sport", "outcome"], suffixes=("_pre", "_post"))
        m["n_nulled"] = _n_nulled(s)
        rows.append(m)
    out = pd.concat(rows, ignore_index=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    out.to_csv(TABLES / "zero_attendance_sensitivity.csv", index=False)
    return out
```

Call it at the end of `main()` (after the twfe tables exist — `main` order below runs `twfe` first) with a print block like the others.

- [ ] **Step 4:** `.venv/bin/pytest tests/test_sensitivity.py -q` → PASS; `.venv/bin/pytest tests -q` → all pass.

- [ ] **Step 5: Regenerate everything, in order**

```bash
for m in src.viz.descriptive src.models.twfe src.models.did src.models.sensitivity; do
  .venv/bin/python -m $m 2>&1 | tee -a .superpowers/sdd/zero-attendance-fix/regen.log || break
done
ls results/tables/*.csv | wc -l      # expect 22
(cd results/tables && shasum -a 256 -c pre_zero_fix/SHA256SUMS 2>/dev/null | sed 's|^|pre: |')
```

- [ ] **Step 6: Pre/post report** — write `.superpowers/sdd/zero-attendance-fix/task-4-diff.md`:
  - which of the 21 CSVs are byte-identical (expected identical: `descriptive_hfa.csv`, `did_*.csv`, `did_cross_sport.csv`; anything else identical or changed gets one line of explanation);
  - the full `zero_attendance_sensitivity.csv`;
  - headline pooled win-probability coefficient per sport before → after (`twfe_cross_sport.csv`), and whether each CI's relation to zero and to the full-HFA threshold (the three G1 exclusion cells: MLB win, NBA win, NHL margin) changed;
  - `dose_overlap.csv` MLB rows before → after (MLB 2020 `control_overlap` expected 0.0077 → 0);
  - count of paper-cited cells that change at printed precision.

- [ ] **Step 7:** Snapshot `pkg.sh snap ZA-4`. **USER CHECKPOINT — stop; show the user `task-4-diff.md`'s summary. Do not start Task 5 without their go-ahead.**

---

### Task 5: Paper re-render, gates, and the two parked B.G2 rows

**Files:**
- Modify: `paper/hfa.qmd` (Data section G2-16/G2-24 disclosure; @sec-robust one sentence + sensitivity reference; any abstract typed number that changed), `paper/check_paper.py` (`abstract_expected()` only if needed), `paper/number-ledger.md`
- Create: `.superpowers/sdd/phase8-polish/stage-b-G2-zero-fixes.md`

- [ ] **Step 1: Re-render and diff numbers**

```bash
cd paper
QUARTO_PYTHON=../.venv/bin/python quarto render hfa.qmd --to plain --wrap=none 2>&1 | tee ../.superpowers/sdd/zero-attendance-fix/render-plain.log
../.venv/bin/python drift.py ../.superpowers/sdd/phase8-polish/snap-ZA-0/paper/hfa.qmd ../.superpowers/sdd/phase8-polish/snap-ZA-0/paper/hfa.txt hfa.qmd hfa.txt | tee ../.superpowers/sdd/zero-attendance-fix/drift-numbers.log
../.venv/bin/pytest check_paper.py test_tools.py -q
```

Every numeric drift must appear in `task-4-diff.md`'s changed cells. `test_abstract_numbers` failing means a typed abstract number changed: update the abstract text to the new source value (the abstract is YAML, typed).

- [ ] **Step 2: Scan for prose now contradicted by new values** — any sentence whose comparison, count or sign depends on a changed cell (e.g., "three cells exclude a full-advantage effect", "all eight … smallest by 2%", "five of eight", MLB dose-overlap interpretation). List each with before/after in the fixes file; fix counts that are already live automatically; **escalate to the user** any sentence whose claim flips.

- [ ] **Step 3: Parked B.G2 rows** (user-approved content, 2026-09-15):
  - **G2-16** (Data, `crowd_pct == 0 is a real value`): state the rule — a zero is real inside documented restriction windows; elsewhere ESPN zero-attendance is treated as a reporting artifact and the game's dose is set to missing (live count per league from `zero_attendance_sensitivity.csv` `n_nulled`); most MLB cases are doubleheaders.
  - **G2-24** (MLB 2020 overlap "cleaner than the NFL's"): rewrite against the regenerated `dose_overlap.csv` values (live); the pre-fix 0.77% was entirely reporting artifacts.
  - **@sec-robust**: one sentence reporting the data-correction sensitivity (largest change in any pooled 6a coefficient, live from the CSV) — pre-fix vs post-fix.
  Log to `stage-b-G2-zero-fixes.md` as `| audit id | before | after (source) | after (rendered) |`.

- [ ] **Step 4: Gates** — PDF+HTML render (only known warnings: ipykernel TCP; plain-only FloatRefTarget / `\hat\beta` / `1/\sqrt{k}`); paper gate passes; `.venv/bin/pytest tests -q` passes.

- [ ] **Step 5:** Snapshot `pkg.sh snap ZA-5`. Dispatch a fresh verifier on the Task 5 diff (`pkg.sh diff ZA-4`) with the Stage B verifier brief shape (resolved? new claim? un-ided edit?).

- [ ] **Step 6: Rebaseline** Phase 8 table hashes for later gates:

```bash
cd /Users/jaydengould/Documents/projects/home-field-advantage
cp .superpowers/sdd/phase8-polish/baseline/tables.sha256 .superpowers/sdd/phase8-polish/baseline/tables.pre_zero_fix.sha256
shasum -a 256 results/tables/*.csv > .superpowers/sdd/phase8-polish/baseline/tables.sha256
```

---

### Task 6: Docs

**Files:** `docs/data-pipeline.md`, `docs/design-decisions.md`, `docs/results.md`, `docs/phase-log.md`, `docs/agent-pitfalls.md`, `CLAUDE.md`, `.superpowers/sdd/phase8-polish/progress.md`

- [ ] **Step 1:** `docs/data-pipeline.md` "Known data imperfections": the artifact, the window rule, per-sport nulled counts, the §6 residual count from Task 3.
- [ ] **Step 2:** `docs/design-decisions.md`: null-not-drop and where the rule lives (build.py, not loaders — NFL loader needs network). Also fix the stale "Two-way FE inverted every sign" (L77): NFL and NBA invert; NHL inflates ~11×; MLB keeps sign (from `season_fe_sensitivity.csv`).
- [ ] **Step 3:** `docs/results.md`: headline numbers from regenerated CSVs; fix L20 "postseasons collapse into bubbles" (NBA/NHL 2021 playoffs were ordinary home games, dose .73/.50).
- [ ] **Step 4:** `CLAUDE.md`: fact "`crowd_pct == 0` is a REAL value" → "…real inside the documented restriction windows (`config/sports.yaml` `zero_attendance_windows`); ESPN zeros outside them are null crowd_pct in data/processed"; "invert every sign" → accurate; headline numbers if changed; test count; Status pointer → Phase 8 resumes at B.G3.
- [ ] **Step 5:** `docs/phase-log.md` row; `docs/agent-pitfalls.md` bullet: "a validated-looking zero can be a reporting artifact — check zeros against when restrictions actually applied". Note for the user: `src/models/sensitivity.py` `dose_overlap` docstring "cleaner than NFL" claim — correct it in this task (src is writable in this plan).
- [ ] **Step 6:** Phase 8 ledger: `Zero-attendance fix COMPLETE — resume Phase 8 at B.G3 (re-audit against regenerated tables)`; update its RESUME HERE block.
