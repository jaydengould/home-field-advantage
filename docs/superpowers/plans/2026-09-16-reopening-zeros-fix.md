# Treated-Season Reopening Zeros — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Null `crowd_pct` for ESPN zero-attendance games inside a restriction window that fall on or after the home team's first game with fans (unless a sourced re-closure covers them), regenerate every table, and ship the pre-fix numbers as a sensitivity.

**Architecture:** An exhaustive, sourced per-team audit produces `fans_from` dates and `reclosures` in `config/sports.yaml`. The existing sport-blind helper `null_reporting_zeros` in `src/features/build.py` gains a reopening rule: in treated, non-excluded regular-season games, a zero on or after min(first non-zero home game, sourced date) is an artifact. `build()` passes the config; models drop null dose listwise as before.

**Tech Stack:** Python 3.11+ `.venv`, pandas, PyYAML, pytest, linearmodels (existing), WebSearch for sourcing, Quarto CLI.

**Spec:** `docs/superpowers/specs/2026-09-16-reopening-zeros-fix-design.md` (approved 2026-09-16). Executors read it first. Precedent: `docs/superpowers/plans/2026-09-15-zero-attendance-fix.md` ("fix 1").

## Global Constraints

- **Git is user-owned:** no `git commit`/`push`/`branch`. Every commit step is a snapshot: `.superpowers/sdd/phase8-polish/pkg.sh snap RZ-<task>`.
- Workspace: `.superpowers/sdd/reopening-zeros-fix/` (ledger `progress.md`, audit CSV, briefs, reports). Append start/end pointer lines to `.superpowers/sdd/phase8-polish/progress.md`.
- `data/raw/` and `data/interim/` are **not modified**. No loader re-run.
- The frozen 6a specification (`twfe.fit` defaults, `CONTROLS`, `_exclusion_mask`) is not changed.
- `crowd_pct == 0` stays 0 unless the spec §2 rule nulls it. Never impute a dose.
- Treated seasons come from `config/sports.yaml`; never hardcode a season in `src/`.
- No sport branching in `src/features` or `src/models`. Per-team facts live in config.
- `date` in `data/interim`/`data/processed` is tz-naive **UTC**. Every configured date is the UTC date of a home game.
- A re-closure needs a source. No source after a recorded search → the zero is nulled (spec §2, user 2026-09-16).
- `results/tables/zero_attendance_sensitivity.csv` must stay **byte-identical**.
- `data/processed/mlb.parquet` must stay byte-identical (MLB 2020 has no non-zero regular-season home game; MLB 2021 zeros are already null).
- American spelling in all new prose (Ruling 15).
- Test gates: `.venv/bin/pytest tests -q` (171 before this plan). Paper: `cd paper && ../.venv/bin/pytest check_paper.py test_tools.py -q` (8).
- Render (from `paper/`, foreground, tee log): `QUARTO_PYTHON=../.venv/bin/python quarto render hfa.qmd` and `... --to plain --wrap=none`. Known warnings only: ipykernel TCP; plain-only FloatRefTarget / `\hat\beta` / `1/\sqrt{k}`.
- **User checkpoint** after Task 4 (audit summary + pre/post coefficient diff). Stop before Task 5.

## Rule (verbatim from spec §2 — do not change)

> Inside a restriction window, `attendance == 0` is a real empty stadium only while that home team
> had **not yet admitted fans** that season, or during a **sourced re-closure**. A zero on or after
> the team's `fans_from` date, outside any re-closure, is a reporting artifact: `crowd_pct` → null.

`fans_from` = earlier of (1) the team's first home game with non-zero ESPN attendance that season and (2) its first home game with fans per a public source. Scope: rows with `season ∈ treated_seasons` and not `is_playoff | is_bubble | neutral_site | relocated_home`.

---

### Task 0: Workspace, archive, baselines

**Files:**
- Create: `results/tables/pre_reopen_fix/*.csv` + `SHA256SUMS`
- Create: `.superpowers/sdd/reopening-zeros-fix/progress.md`, `.../processed_pre/*.parquet`

- [ ] **Step 1: Archive and baseline**

```bash
cd /Users/jaydengould/Documents/projects/home-field-advantage
mkdir -p results/tables/pre_reopen_fix .superpowers/sdd/reopening-zeros-fix/processed_pre
cp results/tables/*.csv results/tables/pre_reopen_fix/
(cd results/tables/pre_reopen_fix && shasum -a 256 *.csv > SHA256SUMS)
cp data/processed/*.parquet .superpowers/sdd/reopening-zeros-fix/processed_pre/
shasum -a 256 -c .superpowers/sdd/phase8-polish/baseline/tables.sha256 | grep -c ': OK'
ls results/tables/pre_reopen_fix/*.csv | wc -l
.venv/bin/pytest tests -q 2>&1 | tail -1
```

Expected: `22`, `22`, `171 passed`.

- [ ] **Step 2: Ledger.** Create `.superpowers/sdd/reopening-zeros-fix/progress.md`: first line `# SDD ledger — plan: docs/superpowers/plans/2026-09-16-reopening-zeros-fix.md`, then `Task 0: complete (22 tables archived, 171 passed)`. Append to the Phase 8 ledger: `Reopening-zeros fix STARTED — ledger .superpowers/sdd/reopening-zeros-fix/progress.md`.

- [ ] **Step 3: Snapshot** `.superpowers/sdd/phase8-polish/pkg.sh snap RZ-0`

---

### Task 1: Sourced per-team audit

**Files:**
- Create: `.superpowers/sdd/reopening-zeros-fix/audit_teams.py` (list generator + checker, throwaway)
- Create: `.superpowers/sdd/reopening-zeros-fix/team_audit.csv`

**Interfaces:**
- Produces: `team_audit.csv` with columns `sport,season,team,kind,n_zero_sample,first_nonzero_utc,late_zero_dates,verdict,fans_from_utc,reclosures,sources,quotes,queries` where `kind ∈ {all_zero, late_zero}`, `verdict ∈ {no_fans, fans_from, unverified, data_only}`, `reclosures` is `;`-separated `START..END` UTC dates (empty if none), `sources` `;`-separated URLs. Task 2 copies `fans_from` and `reclosures` into config from this file.

- [ ] **Step 1: Generate the team list from data (never typed by hand)**

```python
# .superpowers/sdd/reopening-zeros-fix/audit_teams.py
"""List every audited team (spec §2 scope) and, with --check, validate team_audit.csv."""
import sys
from pathlib import Path
import pandas as pd, yaml

ROOT = Path(__file__).resolve().parents[3]
CFG = yaml.safe_load((ROOT / "config/sports.yaml").read_text())
WS = Path(__file__).parent


def scoped(sport):
    p = pd.read_parquet(ROOT / f"data/interim/{sport}.parquet")
    keep = (p["season"].isin(CFG[sport]["treated_seasons"]) & ~p["is_playoff"] & ~p["is_bubble"]
            & ~p["neutral_site"] & ~p["relocated_home"])
    p = p[keep].copy()
    p["day"] = pd.to_datetime(p["date"]).dt.normalize()
    return p


def team_list():
    rows = []
    for sport in ("nfl", "nba", "nhl"):          # spec §2: MLB not audited
        p = scoped(sport)
        for (season, team), g in p.groupby(["season", "home_team"]):
            first = g.loc[g["attendance"] > 0, "day"].min()
            zeros = g[g["attendance"] == 0]
            if zeros.empty:
                continue
            if pd.isna(first):
                rows.append((sport, season, team, "all_zero", len(zeros), "", ""))
            else:
                late = zeros[zeros["day"] > first]["day"].dt.strftime("%Y-%m-%d").tolist()
                if late:
                    rows.append((sport, season, team, "late_zero", len(late), first.strftime("%Y-%m-%d"),
                                 ";".join(late)))
    return pd.DataFrame(rows, columns=["sport", "season", "team", "kind", "n_zero_sample",
                                       "first_nonzero_utc", "late_zero_dates"])


def check():
    a = pd.read_csv(WS / "team_audit.csv", dtype=str).fillna("")
    want = team_list().astype(str)
    key = ["sport", "season", "team"]
    assert set(map(tuple, a[key].values)) == set(map(tuple, want[key].values)), "audit rows != team list"
    assert a["verdict"].isin(["no_fans", "fans_from", "unverified", "data_only"]).all()
    assert (a["verdict"].isin(["unverified", "data_only"]) | (a["sources"] != "")).all(), "verdict without source"
    assert ((a["reclosures"] == "") | (a["sources"] != "")).all(), "re-closure without source"
    assert (a["queries"] != "").all(), "every row records the queries tried"
    for _, r in a[a["verdict"] == "fans_from"].iterrows():
        g = scoped(r["sport"])
        g = g[(g["home_team"] == r["team"]) & (g["season"] == int(r["season"]))]
        assert (g["day"] == pd.Timestamp(r["fans_from_utc"])).any(), f"no home game on {r.to_dict()}"
    print("audit OK:", a["verdict"].value_counts().to_dict())


if __name__ == "__main__":
    check() if "--check" in sys.argv else print(team_list().to_string(index=False))
```

Run: `.venv/bin/python .superpowers/sdd/reopening-zeros-fix/audit_teams.py`
Expected: 29 `all_zero` rows (nba 4, nhl 11, nfl 14) and 15 `late_zero` rows (nfl ARI BAL CLE DEN PIT WAS; nba ATL BOS CLE MEM MIN UTAH; nhl FLA NJ NYI). The controller's counts were on the model sample (`_prep`, which also drops rows with missing controls), so a count here may be slightly higher. If the **team set** differs, stop and report it.

- [ ] **Step 2: Source every row with WebSearch**

Seed `team_audit.csv` from Step 1's output. For each row, search and fill `verdict`, `fans_from_utc`, `reclosures`, `sources`, `quotes` (≤ 25 words each, verbatim), `queries` (`;`-separated, every query tried).

- `all_zero` rows: find whether the team admitted any fans in that regular season. Fans → `verdict=fans_from`, and `fans_from_utc` is the **UTC date** of the first home game the source definitely covers (an evening US game usually has the next day's UTC date; take the date from the Step 1 panel, not from the article). Never round backward. No fans all season → `no_fans`. Nothing conclusive after at least three distinct queries → `unverified`.
- `late_zero` rows: `verdict=data_only` (`fans_from_utc` = `first_nonzero_utc`), unless a source puts fans earlier (then `fans_from` with the earlier date). For **each** late-zero date, search for a re-closure (e.g. `"<team> no fans <month year>"`, `"<team> suspend fans"`). A sourced closure covering that game → add `START..END` to `reclosures` using the closure's documented span in UTC dates. No source → leave it out (it gets nulled).
- A league-wide source may cover several rows (e.g. a list of which NFL teams hosted fans in 2020); cite it on each row it covers.
- Controller spot checks already in hand (2026-09-16, re-verify the UTC game date): MIA from 2021-01-28, IND from 2021-01-24, SAC from 2021-04-20, STL (NHL) from 2021-02-02, BUF (NHL) from 2021-03-20, DET (NHL) about 2021-03-10, NSH "January 2021" (find the exact game), OKC `no_fans`.

- [ ] **Step 3: Validate**

Run: `.venv/bin/python .superpowers/sdd/reopening-zeros-fix/audit_teams.py --check`
Expected: `audit OK: {...}`. Fix rows until it passes.

- [ ] **Step 4: Ledger + snapshot.** Append the verdict counts and the `unverified` teams to the ledger. `pkg.sh snap RZ-1`.

---

### Task 2: Reopening rule in the helper, config, wiring (TDD)

**Files:**
- Modify: `src/features/build.py` (`null_reporting_zeros`, `_zero_windows` → `_zero_config`, `build`)
- Modify: `config/sports.yaml` (add `fans_from`, `reclosures` to all four sports)
- Test: `tests/test_features.py`, `tests/test_config.py`

**Interfaces:**
- Consumes: `team_audit.csv` (Task 1).
- Produces: `null_reporting_zeros(panel, windows, treated_seasons=(), fans_from=(), reclosures=()) -> tuple[pd.DataFrame, int]`. With only `windows`, behaviour is exactly fix 1's. `fans_from` items `{season: int, team: str, date: "YYYY-MM-DD", source: str}`; `reclosures` items `{team: str, start: "YYYY-MM-DD", end: "YYYY-MM-DD", source: str}` (inclusive, UTC dates). `_zero_config(sport) -> dict` returns the sport's config block. Task 4 calls the helper both ways to split counts.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_features.py`)

```python
def _rpanel(rows):
    """Treated-season rows with the exclusion flags the reopening rule reads."""
    df = pd.DataFrame(rows, columns=["season", "date", "home_team", "attendance", "crowd_pct"])
    return df.assign(date=pd.to_datetime(df["date"], format="ISO8601"), is_playoff=False,
                     is_bubble=False, neutral_site=False, relocated_home=False)


W21 = [{"seasons": [2021]}]


def test_reopening_zero_after_first_nonzero_game_is_nulled():
    p = _rpanel([(2021, "2021-01-10", "CLE", 0, 0.0),      # before fans -> real
                 (2021, "2021-01-20", "CLE", 500, 0.03),   # first fans (data)
                 (2021, "2021-02-01", "CLE", 0, 0.0)])     # after -> artifact
    out, n = null_reporting_zeros(p, W21, treated_seasons=[2021])
    assert n == 1 and out["crowd_pct"].isna().tolist() == [False, False, True]


def test_configured_fans_from_nulls_all_zero_team_from_that_date_inclusive():
    p = _rpanel([(2021, "2021-01-20", "MIA", 0, 0.0),
                 (2021, "2021-01-29", "MIA", 0, 0.0),
                 (2021, "2021-02-05", "MIA", 0, 0.0)])
    ff = [{"season": 2021, "team": "MIA", "date": "2021-01-29", "source": "x"}]
    out, n = null_reporting_zeros(p, W21, [2021], ff)
    assert n == 2 and out["crowd_pct"].isna().tolist() == [False, True, True]


def test_earlier_of_data_and_configured_date_wins():
    p = _rpanel([(2021, "2021-01-10", "IND", 0, 0.0),
                 (2021, "2021-01-15", "IND", 0, 0.0),
                 (2021, "2021-01-20", "IND", 900, 0.05)])
    late = [{"season": 2021, "team": "IND", "date": "2021-01-30", "source": "x"}]
    early = [{"season": 2021, "team": "IND", "date": "2021-01-15", "source": "x"}]
    assert null_reporting_zeros(p, W21, [2021], late)[1] == 0      # data date 01-20 wins
    assert null_reporting_zeros(p, W21, [2021], early)[1] == 1     # config date 01-15 wins


def test_sourced_reclosure_keeps_zero_real():
    p = _rpanel([(2020, "2020-10-01", "BAL", 7000, 0.1),
                 (2020, "2020-12-08", "BAL", 0, 0.0),     # inside re-closure -> real
                 (2020, "2021-01-03", "BAL", 0, 0.0)])    # outside -> artifact
    rc = [{"team": "BAL", "start": "2020-11-20", "end": "2020-12-31", "source": "x"}]
    out, n = null_reporting_zeros(p, [{"seasons": [2020]}], [2020], (), rc)
    assert n == 1 and out["crowd_pct"].isna().tolist() == [False, False, True]


def test_no_fans_team_and_untreated_season_and_excluded_rows_untouched():
    p = _rpanel([(2021, "2021-02-01", "OKC", 0, 0.0),     # never fans -> real
                 (2022, "2021-11-01", "TOR", 900, 0.05),  # untreated season, Canadian window
                 (2022, "2022-01-05", "TOR", 0, 0.0)])
    w = W21 + [{"start": "2021-12-16", "end": "2022-02-20", "home_teams": ["TOR"]}]
    out, n = null_reporting_zeros(p, w, [2021])
    assert n == 0
    q = _rpanel([(2021, "2021-01-05", "LAL", 900, 0.05), (2021, "2021-01-09", "LAL", 0, 0.0)])
    q.loc[1, "is_playoff"] = True
    assert null_reporting_zeros(q, W21, [2021])[1] == 0


def test_windows_only_call_matches_fix_one():
    p = _rpanel([(2021, "2021-01-05", "CLE", 900, 0.05), (2021, "2021-01-09", "CLE", 0, 0.0),
                 (2019, "2019-05-01", "BOS", 0, 0.0)])
    out, n = null_reporting_zeros(p, W21)
    assert n == 1 and out["crowd_pct"].isna().tolist() == [False, False, True]
```

Append to `tests/test_config.py` (match the file's existing config-loading idiom; if it has none, read `config/sports.yaml` with `yaml.safe_load`):

```python
def test_reopening_config_keys_present_and_well_formed():
    cfg = yaml.safe_load(Path("config/sports.yaml").read_text())
    for sport in ("nfl", "mlb", "nba", "nhl"):
        c = cfg[sport]
        for f in c["fans_from"]:
            assert f["season"] in c["treated_seasons"] and f["source"].startswith("http")
            pd.Timestamp(f["date"])
        for r in c["reclosures"]:
            assert pd.Timestamp(r["start"]) <= pd.Timestamp(r["end"]) and r["source"].startswith("http")
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/pytest tests/test_features.py tests/test_config.py -q`
Expected: the new helper tests fail with `TypeError` (unexpected positional/keyword argument); the config test fails with `KeyError: 'fans_from'`.

- [ ] **Step 3: Implement**

Replace `_zero_windows` and `null_reporting_zeros` in `src/features/build.py`:

```python
def _zero_config(sport: str) -> dict:
    return yaml.safe_load(CONFIG_FILE.read_text())[sport]


def null_reporting_zeros(panel: pd.DataFrame, windows: list[dict], treated_seasons=(),
                         fans_from=(), reclosures=()) -> tuple[pd.DataFrame, int]:
    """attendance==0 is a real empty stadium only inside a documented restriction window
    (config zero_attendance_windows). Outside every window it is an ESPN reporting artifact:
    crowd_pct -> null (dose unknown). attendance keeps the as-reported 0. Sport-blind.

    Reopening rule (spec 2026-09-16): in treated-season games no model excludes, a zero on or
    after the home team's first game with fans -- the earlier of its first non-zero attendance
    and a sourced `fans_from` date -- is also an artifact, unless a sourced re-closure covers it."""
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

    reopened = pd.Series(False, index=df.index)
    if len(treated_seasons):
        audited = (df["season"].isin(treated_seasons) & ~df["is_playoff"] & ~df["is_bubble"]
                   & ~df["neutral_site"] & ~df["relocated_home"])
        first = day.where(audited & (df["attendance"] > 0)).groupby(
            [df["season"], df["home_team"]]).transform("min")
        for f in fans_from:
            d = pd.Timestamp(f["date"])
            m = (df["season"] == f["season"]) & (df["home_team"] == f["team"])
            first = first.where(~m | (first <= d), d)          # NaT <= d is False -> d
        reopened = audited & (day >= first)                    # NaT -> False
        for r in reclosures:
            reopened &= ~((df["home_team"] == r["team"]) & (day >= pd.Timestamp(r["start"]))
                          & (day <= pd.Timestamp(r["end"])))

    artifact = (df["attendance"] == 0) & (~real | reopened)
    df.loc[artifact, "crowd_pct"] = np.nan
    return df, int(artifact.sum())
```

In `build()` replace the helper call with:

```python
    c = _zero_config(sport)
    panel, n_null = null_reporting_zeros(panel, c["zero_attendance_windows"], c["treated_seasons"],
                                         c["fans_from"], c["reclosures"])
```

Grep for other `_zero_windows` callers (`grep -rn _zero_windows src tests paper`) and switch them to `_zero_config(sport)["zero_attendance_windows"]`.

- [ ] **Step 4: Config from the audit**

Add to every sport block in `config/sports.yaml`, below `zero_attendance_windows`, with a one-line comment pointing at the spec. MLB gets empty lists. For nfl/nba/nhl, emit entries from `team_audit.csv`: one `fans_from` item per `verdict=fans_from` row (first URL in `sources`), one `reclosures` item per `START..END` in `reclosures`. `data_only`, `no_fans` and `unverified` rows need no entry. Generate the YAML text with a short script and paste it; do not hand-type dates.

```yaml
  # Reopening rule (spec docs/superpowers/specs/2026-09-16-reopening-zeros-fix-design.md):
  # sourced first-fans home game (UTC date) and sourced re-closures. Audit: .superpowers/sdd/reopening-zeros-fix/team_audit.csv
  fans_from:
    - {season: 2021, team: MIA, date: "2021-01-29", source: "https://..."}
  reclosures: []
```

(The MIA line above illustrates the format only; the real date and URL come from the audit.)

- [ ] **Step 5: Run tests**

Run: `.venv/bin/pytest tests -q`
Expected: all pass; count = 171 + 7 = `178 passed`.

- [ ] **Step 6: Snapshot** `pkg.sh snap RZ-2`; ledger line.

---

### Task 3: Rebuild processed panels and verify counts

**Files:** `data/processed/*.parquet` (regenerated only)

- [ ] **Step 1: Rebuild**

Run: `.venv/bin/python -m src.features.build 2>&1 | tee .superpowers/sdd/reopening-zeros-fix/build.log`
Expected: four `nulled N` lines; MLB's N equals fix 1's MLB count (107).

- [ ] **Step 2: Verify against the audit independently**

```python
import pandas as pd, yaml
from src.features.build import null_reporting_zeros
cfg = yaml.safe_load(open("config/sports.yaml"))
pre = ".superpowers/sdd/reopening-zeros-fix/processed_pre"
for s in ("nfl", "mlb", "nba", "nhl"):
    old, new = pd.read_parquet(f"{pre}/{s}.parquet"), pd.read_parquet(f"data/processed/{s}.parquet")
    assert len(old) == len(new) and (old["game_id"].values == new["game_id"].values).all()
    changed = old["crowd_pct"].notna() & new["crowd_pct"].isna()
    assert (old.loc[changed, "crowd_pct"] == 0).all() and (new.loc[changed, "attendance"] == 0).all()
    other = [c for c in new.columns if c != "crowd_pct"]
    pd.testing.assert_frame_equal(old[other], new[other])
    assert not (old["crowd_pct"].isna() & new["crowd_pct"].notna()).any()
    t = new[changed]
    assert t["season"].isin(cfg[s]["treated_seasons"]).all()
    print(s, "newly nulled:", int(changed.sum()), t.groupby("home_team").size().to_dict())
```

Expected: `mlb newly nulled: 0`; every newly nulled team in nfl/nba/nhl is a `fans_from` or `data_only`/`late_zero` team in `team_audit.csv`; no `no_fans` or `unverified` team appears. Check that by hand against the audit and record the per-team counts in the ledger.

- [ ] **Step 3: Byte-identity and validation**

```bash
shasum -a 256 data/processed/mlb.parquet .superpowers/sdd/reopening-zeros-fix/processed_pre/mlb.parquet
.venv/bin/pytest tests -q 2>&1 | tail -1
```

Expected: identical MLB hashes; `178 passed`. If MLB differs, stop: the scope filter is wrong.

- [ ] **Step 4: Snapshot** `pkg.sh snap RZ-3`; ledger line.

---

### Task 4: Regenerate tables, sensitivity tables, user checkpoint

**Files:**
- Modify: `src/models/sensitivity.py` (`_n_nulled`, `zero_attendance_sensitivity`, new `reopen_zero_sensitivity`, `main`)
- Test: `tests/test_sensitivity.py`
- Regenerate: `results/tables/*.csv`; create `results/tables/reopen_zero_sensitivity.csv`

**Interfaces:**
- Consumes: `null_reporting_zeros`, `_zero_config` (Task 2).
- Produces: `_n_nulled(sport) -> tuple[int, int]` = (fix-1 nulls, reopening-rule nulls), computed from `data/interim`. `zero_attendance_sensitivity(pre_dir=None, post_dir=None)` (post defaults to `TABLES / "pre_reopen_fix"`). `reopen_zero_sensitivity(pre_dir=None) -> pd.DataFrame` writes `reopen_zero_sensitivity.csv` with fix 1's columns: `sport,outcome,coef_pre,se_pre,ci_low_pre,ci_high_pre,n_obs_pre,coef_post,se_post,ci_low_post,ci_high_post,n_obs_post,n_nulled`. Task 5 reads it.

- [ ] **Step 1: Failing tests.** In `tests/test_sensitivity.py::test_zero_attendance_sensitivity_joins_pre_and_post`, change exactly two lines: `lambda sport: 75` → `lambda sport: (75, 0)`, and `S.zero_attendance_sensitivity(pre_dir=pre)` → `S.zero_attendance_sensitivity(pre_dir=pre, post_dir=post)`. Add:

```python
def test_reopen_zero_sensitivity_uses_second_count(tmp_path, monkeypatch):
    import src.models.sensitivity as S
    pre, post = tmp_path / "pre", tmp_path / "post"
    pre.mkdir(); post.mkdir()
    cols = ["sport", "outcome", "sample", "coef", "se", "ci_low", "ci_high", "n_obs"]
    for s in S.SPORTS:
        pd.DataFrame([[s, "home_win", "pooled", 0.01, 0.02, -0.03, 0.05, 1000]], columns=cols).to_csv(
            pre / f"twfe_{s}.csv", index=False)
        pd.DataFrame([[s, "home_win", "pooled", 0.00, 0.02, -0.04, 0.04, 990]], columns=cols).to_csv(
            post / f"twfe_{s}.csv", index=False)
    monkeypatch.setattr(S, "TABLES", post)
    monkeypatch.setattr(S, "_n_nulled", lambda sport: (7, 10))
    out = S.reopen_zero_sensitivity(pre_dir=pre)
    assert (out["n_nulled"] == 10).all() and (out["n_obs_post"] == 990).all()
    assert (post / "reopen_zero_sensitivity.csv").exists()
```

Run: `.venv/bin/pytest tests/test_sensitivity.py -q` → the new test fails (`AttributeError: reopen_zero_sensitivity`).

- [ ] **Step 2: Implement** in `src/models/sensitivity.py`:

```python
def _n_nulled(sport: str) -> tuple[int, int]:
    """(fix-1 nulls outside every window, reopening-rule nulls inside windows), from data/interim."""
    c = _zero_config(sport)
    p = pd.read_parquet(f"data/interim/{sport}.parquet")
    n1 = null_reporting_zeros(p, c["zero_attendance_windows"])[1]
    n_all = null_reporting_zeros(p, c["zero_attendance_windows"], c["treated_seasons"],
                                 c["fans_from"], c["reclosures"])[1]
    return n1, n_all - n1


def _fix_sensitivity(pre_dir: Path, post_dir: Path, which: int, out_name: str) -> pd.DataFrame:
    keep = ["sport", "outcome", "coef", "se", "ci_low", "ci_high", "n_obs"]
    rows = []
    for s in SPORTS:
        pre = pd.read_csv(pre_dir / f"twfe_{s}.csv")
        post = pd.read_csv(post_dir / f"twfe_{s}.csv")
        pre, post = (d[d["sample"] == "pooled"][keep] for d in (pre, post))
        m = pre.merge(post, on=["sport", "outcome"], suffixes=("_pre", "_post"))
        m["n_nulled"] = _n_nulled(s)[which]
        rows.append(m)
    out = pd.concat(rows, ignore_index=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    out.to_csv(TABLES / out_name, index=False)
    return out


def zero_attendance_sensitivity(pre_dir: Path | None = None, post_dir: Path | None = None) -> pd.DataFrame:
    """Frozen 6a pooled estimates before vs after fix 1 (spec 2026-09-15). "After" is the state
    archived before the reopening fix, so this table does not move when later fixes land."""
    return _fix_sensitivity(pre_dir or TABLES / "pre_zero_fix", post_dir or TABLES / "pre_reopen_fix",
                            0, "zero_attendance_sensitivity.csv")


def reopen_zero_sensitivity(pre_dir: Path | None = None) -> pd.DataFrame:
    """Frozen 6a pooled estimates before vs after the reopening rule (spec 2026-09-16)."""
    return _fix_sensitivity(pre_dir or TABLES / "pre_reopen_fix", TABLES, 1,
                            "reopen_zero_sensitivity.csv")
```

Import `null_reporting_zeros, _zero_config` from `src.features.build`. In `main()`, add `reopen_fix = reopen_zero_sensitivity()` after `zero_fix`, and print it the way `zero_fix` is printed. Delete the old `_n_nulled` and `zero_attendance_sensitivity` bodies.

Run: `.venv/bin/pytest tests -q` → `179 passed`.

- [ ] **Step 3: Regenerate every table** (same order fix 1 used: descriptive, twfe, did, sensitivity; check each module's `main` exists before running)

```bash
for m in src.viz.descriptive src.models.twfe src.models.did src.models.sensitivity; do
  .venv/bin/python -m $m > .superpowers/sdd/reopening-zeros-fix/regen_${m##*.}.log 2>&1 || echo "FAIL $m"
done
(cd results/tables/pre_reopen_fix && shasum -a 256 -c SHA256SUMS 2>/dev/null | sed 's/^/pre: /' | grep -v ': OK' )
for f in results/tables/pre_reopen_fix/*.csv; do n=$(basename $f); cmp -s $f results/tables/$n && echo "same $n" || echo "CHANGED $n"; done
```

Expected: `same` for `descriptive_hfa.csv`, every `did_*.csv`, and **`zero_attendance_sensitivity.csv`**. If fix 1's table changed, stop.

- [ ] **Step 4: Pre/post report for the user** — write `.superpowers/sdd/reopening-zeros-fix/checkpoint.md` containing: (a) audit verdict counts, every `unverified` team, every re-closure with its source; (b) newly nulled games per sport (model sample `n_obs` change from `reopen_zero_sensitivity.csv`); (c) `reopen_zero_sensitivity.csv` printed with a `shift_se = (coef_post − coef_pre)/se_pre` column; (d) the four headline win-probability coefficients before/after (`twfe_cross_sport.csv`); (e) which other CSVs changed and by how much in their key columns (`meta_cross_sport` pooled estimate, `noise_floor`, `season_effects` p floor, `dose_overlap`); (f) whether "in all eight cells MDE_80 > HFA" still holds (recompute as in `paper/check_paper.py::abstract_expected`).

- [ ] **Step 5: Snapshot** `pkg.sh snap RZ-4`; ledger line. **STOP — user checkpoint.** Show the user `checkpoint.md`. Do not start Task 5 without their go-ahead.

---

### Task 5: Paper — disclosure, live values, gates

**Files:**
- Modify: `paper/hfa.qmd` (setup `csv(...)` loads; Data section item 1; `@sec-zero`; `@tbl-specsummary` zero row; abstract typed numbers if changed)
- Modify: `paper/number-ledger.md` only if a typed number needs a row

**Interfaces:**
- Consumes: `reopen_zero_sensitivity.csv`, `config/sports.yaml` `fans_from`/`reclosures`, `team_audit.csv` is **not** read by the paper (it is gitignored workspace); unverified teams are listed from config comments or computed as all-zero teams without `fans_from`, see Step 2.

- [ ] **Step 1: Baseline the paper before editing.** `pkg.sh snap RZ-5`. Run the paper gate and note which tests fail purely from Task 4's data change (expected: `test_abstract_numbers` if a headline coefficient's third decimal moved; any in-document `assert` whose wording no longer holds). Record them; each must be resolved in this task or routed (Step 4).

- [ ] **Step 2: Live variables.** In the setup chunk next to `zsens = csv("zero_attendance_sensitivity")` add `rsens = csv("reopen_zero_sensitivity")`. In the data chunk near `data_zero_nulled`, add:

```python
# Reopening rule (spec 2026-09-16): treated-season zeros after a team's first game with fans.
data_reopen_nulled = {s: int(pick(rsens, sport=s, outcome="home_win")["n_nulled"]) for s in SPORTS}
data_reopen_nulled_total = sum(data_reopen_nulled.values())
data_reopen_sourced = {s: len(_sports_cfg[s]["fans_from"]) for s in SPORTS}
data_reopen_reclosures = sum(len(_sports_cfg[s]["reclosures"]) for s in SPORTS)
```

The unverified teams are a short fixed list from the audit; type them in prose with a ledger row `D` (design fact, source `team_audit.csv`), rather than reading gitignored workspace files at render time.

- [ ] **Step 3: Prose.** Keep it short and in the paper's voice (`docs/paper-writing-guide.md`; American spelling).
  - Data section, item 1: after the fix-1 sentence, add one or two sentences: inside the restriction windows ESPN also reports zero for games after a team had readmitted fans; a zero on or after the team's first game with fans (earliest of the data and a public source) is treated as missing unless a documented re-closure covers it; `{python} data_reopen_nulled_total` games, with the per-league counts; teams whose status could not be sourced keep empty-stadium coding (name them). State that this rule was added after estimates had been seen, and that both versions are reported in @sec-zero.
  - `@sec-zero`: add a paragraph with a live largest-shift sentence built exactly like `rob-zero-vars` but on `rsens` (`rob_reopen_max_shift_se`, label, pre/post), and whether any interval's zero or full-advantage exclusion changes (reuse `_excl_set` with `_pre = T / "pre_reopen_fix"`, asserting the result is what the prose says). Name the file `reopen_zero_sensitivity.csv`.
  - `@tbl-specsummary`: add a row `| Zeros after a team readmitted fans as missing | Coded as empty (0) | ≤ {rob_reopen_max_shift_se} SE in every cell (@sec-zero) |`.
  - Abstract: update any typed headline coefficient that changed so `test_abstract_numbers` passes. Do **not** reword the Ganz & Allsop sentence ("upper edge"); that is B.G5 fix round 2 (N1), which is written after this fix.

- [ ] **Step 4: Asserts that now fail.** For each in-document `assert` that fails after the data change: if it guards wording this task owns (Data section, @sec-zero, spec summary), fix the wording. If it guards the Ganz & Allsop mapping or another B.G5 N1 sentence, do not reword: report the assert text and the new value to the controller, who routes it into fix round 2 and decides how to keep the render green meanwhile. Any other failing assert: stop and report.

- [ ] **Step 5: Gates**

```bash
cd paper && ../.venv/bin/pytest check_paper.py test_tools.py -q 2>&1 | tail -1
QUARTO_PYTHON=../.venv/bin/python quarto render hfa.qmd 2>&1 | tee ../.superpowers/sdd/reopening-zeros-fix/render.log | grep -ci warn
QUARTO_PYTHON=../.venv/bin/python quarto render hfa.qmd --to plain --wrap=none 2>&1 | tail -3
cd .. && .venv/bin/pytest tests -q 2>&1 | tail -1
```

Expected: `8 passed`; warn lines only the known ipykernel TCP ones; plain render completes; `179 passed`. Then run `pkg.sh diff RZ-5` and confirm every hunk in `paper/` belongs to Steps 2–4.

- [ ] **Step 6: Refresh the Phase 8 table baseline.** The B.G5 gate checks `baseline/tables.sha256`. Move the old file to `baseline/tables.pre_reopen_fix.sha256` and write a new one: `shasum -a 256 results/tables/*.csv > .superpowers/sdd/phase8-polish/baseline/tables.sha256`. Ledger line in both ledgers.

- [ ] **Step 7: Snapshot** `pkg.sh snap RZ-5-done`.

---

### Task 6: Docs

**Files:** `docs/data-pipeline.md`, `docs/design-decisions.md`, `docs/results.md`, `docs/agent-pitfalls.md`, `docs/phase-log.md`, `CLAUDE.md`

- [ ] **Step 1: `docs/data-pipeline.md`** — in "ESPN zero-attendance reporting artifacts", replace the **Residual** sentences with: the reopening rule (one sentence), per-sport newly nulled counts, and a compact per-team table (sport, team, verdict, fans_from UTC, re-closures, one source URL) generated from `team_audit.csv`. Name the `unverified` teams as the remaining residual.
- [ ] **Step 2: `docs/design-decisions.md`** — one entry: why `fans_from` is min(data, source); why re-closures need a source; why null not impute; that the rule was added after estimates were seen and both versions ship.
- [ ] **Step 3: `docs/results.md`** — update every number that changed (headline win-probability line, any NBA/NHL coefficient cited) from the CSVs; add `reopen_zero_sensitivity.csv` and `pre_reopen_fix/` beside the fix-1 line.
- [ ] **Step 4: `docs/agent-pitfalls.md`** — new trap: a residual diagnostic defined relative to a team's first non-zero game cannot see teams that report zero all season; count all-zero teams separately.
- [ ] **Step 5: `docs/phase-log.md`** — entry for this fix (date, rule, counts, tables archived, headline shift).
- [ ] **Step 6: `CLAUDE.md`** — test count; the `crowd_pct == 0` fact gains "and only until that team first readmitted fans (config `fans_from`/`reclosures`)"; headline numbers if changed; Status line: reopening-zeros fix done, B.G5 resumes at fix round 2. Keep under 200 lines.
- [ ] **Step 7: Close out.** Ledger `Task 6: complete`; Phase 8 ledger `Reopening-zeros fix COMPLETE — B.G5 resumes at fix round 2 (N1) against the new tables`. `pkg.sh snap RZ-6`.
