# NFL Pilot Loader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an NFL loader that turns `nfl_data_py` schedules + ESPN attendance into a DataFrame passing `src.schema.validate()`, written to `data/interim/nfl.parquet`.

**Architecture:** One module `src/data/nfl.py`, split into a pure offline-testable transform (`_build_panel`), a cached network fetch (`_fetch_attendance`), an orchestrator (`load`), and a CLI (`main`, with a `--smoke` mode). A static `config/nfl_venue_capacity.yaml` supplies stadium capacities. NFL is the pilot sport; Phase 3 conforms MLB/NBA to whatever this proves.

**Tech Stack:** Python 3.11+, pandas, nfl_data_py, requests, pyyaml, pyarrow (parquet), pytest.

**Spec:** `docs/superpowers/specs/2026-07-02-phase2-nfl-loader-design.md`

## Global Constraints

- **Git is user-owned. NEVER run `git commit`/`push`/`branch`/`add`.** Each task ends at "tests pass"; the USER commits at checkpoints. Do not stage or commit anything.
- **`data/raw/` is immutable** — the ESPN cache under `data/raw/nfl/espn/` is written once per game and never overwritten.
- **The panel must pass the full `src.schema.validate()`** — not a subset. `validate` collects all violations into one `ValueError`.
- **Dtype contract is strict:** plain `int` ≠ `Int64` ≠ `float`, and plain `bool` ≠ `boolean`. `home_win` is nullable `boolean`; `home_rest_days`/`away_rest_days` are `Int64`; scores/margin/attendance/capacity/season are plain `int`; `crowd_pct`/elo/spread/weather/travel are `float`; `is_dome`/`neutral_site`/`is_playoff`/`covid_era`/`relocated_home`/`is_bubble` are plain `bool`.
- **`crowd_pct == 0` is a REAL value** (empty 2020 stadium), never coerce to null.
- **Season range is a config parameter**, `config/sports.yaml` → `nfl.load_seasons: [2018, 2023]` (start, end inclusive).
- Run tests with `.venv/bin/pytest`.

---

### Task 1: Config + requirements

**Files:**
- Modify: `config/sports.yaml`
- Modify: `requirements.txt`
- Modify: `tests/test_config.py`

**Interfaces:**
- Produces: `config/sports.yaml` gains `nfl.load_seasons: [2018, 2023]`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_config.py`:

```python
def test_nfl_load_seasons():
    import yaml
    cfg = yaml.safe_load(open("config/sports.yaml"))
    lo, hi = cfg["nfl"]["load_seasons"]
    assert lo == 2018 and hi == 2023
    assert lo <= hi
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_config.py::test_nfl_load_seasons -v`
Expected: FAIL with `KeyError: 'load_seasons'`.

- [ ] **Step 3: Add config + requirements**

In `config/sports.yaml`, under `nfl:`, add the `load_seasons` line (keep `treated_seasons`):

```yaml
nfl:
  treated_seasons: [2020]        # 2021 reopened to full capacity league-wide
  load_seasons: [2018, 2023]     # [start, end] inclusive — seasons the loader pulls
```

In `requirements.txt`, add under the appropriate sections (they are installed but were unpinned):

```
# Fetch + parquet + tests
requests
pyarrow
pytest
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_config.py -v`
Expected: PASS (all config tests).

- [ ] **Step 5: Checkpoint** — report to user; user commits.

---

### Task 2: `_build_panel` — the pure transform

The heart of the loader. Pure function: `(schedule_df, attendance, capacity, treated_seasons) → validated panel`. No network, no disk. Assumes `schedule_df` already contains only **played** games with **non-null attendance** (the `load` orchestrator guarantees this in Task 5).

**Files:**
- Create: `src/data/nfl.py`
- Test: `tests/test_nfl_loader.py`

**Interfaces:**
- Consumes: `src.schema.validate`, `src.schema.COLUMNS`.
- Produces: `_build_panel(schedule: pd.DataFrame, attendance: dict[str, int], capacity: dict[str, int], treated_seasons: list[int]) -> pd.DataFrame` returning a DataFrame whose columns are exactly `list(COLUMNS)` in order, passing `validate()`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_nfl_loader.py`:

```python
import pandas as pd
from src.data.nfl import _build_panel
from src.schema import validate, COLUMNS


def _fake_schedule():
    return pd.DataFrame([
        # normal outdoor home win, margin +7
        dict(game_id="2019_01_A_B", season=2019, gameday="2019-09-08", game_type="REG",
             home_team="A", away_team="B", home_score=24, away_score=17,
             spread_line=-3.0, home_rest=7, away_rest=7, stadium="Field A",
             stadium_id="AAA00", roof="outdoors", temp=70, wind=5, location="Home", espn="1001"),
        # 2020 empty stadium, away win, margin -10
        dict(game_id="2020_01_C_D", season=2020, gameday="2020-09-13", game_type="REG",
             home_team="C", away_team="D", home_score=10, away_score=20,
             spread_line=2.5, home_rest=7, away_rest=10, stadium="Field C",
             stadium_id="CCC00", roof="outdoors", temp=65, wind=8, location="Home", espn="1002"),
        # tie, margin 0
        dict(game_id="2019_10_E_F", season=2019, gameday="2019-11-10", game_type="REG",
             home_team="E", away_team="F", home_score=13, away_score=13,
             spread_line=0.0, home_rest=7, away_rest=7, stadium="Field E",
             stadium_id="EEE00", roof="outdoors", temp=55, wind=3, location="Home", espn="1003"),
        # dome with junk temp/wind that must be nulled
        dict(game_id="2019_05_G_H", season=2019, gameday="2019-10-06", game_type="REG",
             home_team="G", away_team="H", home_score=31, away_score=28,
             spread_line=-6.5, home_rest=7, away_rest=7, stadium="Dome G",
             stadium_id="GGG00", roof="dome", temp=68, wind=0, location="Home", espn="1004"),
    ])


_ATT = {"1001": 62000, "1002": 0, "1003": 61000, "1004": 65000}
_CAP = {"AAA00": 70000, "CCC00": 65000, "EEE00": 70000, "GGG00": 70000}


def _panel():
    return _build_panel(_fake_schedule(), _ATT, _CAP, treated_seasons=[2020])


def test_build_panel_validates():
    validate(_panel())  # raises if the panel violates the schema


def test_columns_exact():
    assert list(_panel().columns) == list(COLUMNS)


def test_empty_stadium_crowd_pct_zero():
    row = _panel().set_index("game_id").loc["2020_01_C_D"]
    assert row["attendance"] == 0
    assert row["crowd_pct"] == 0.0
    assert row["covid_era"] == True


def test_tie_home_win_null():
    row = _panel().set_index("game_id").loc["2019_10_E_F"]
    assert row["home_margin"] == 0
    assert pd.isna(row["home_win"])


def test_dome_weather_null():
    row = _panel().set_index("game_id").loc["2019_05_G_H"]
    assert row["is_dome"] == True
    assert pd.isna(row["temp_f"])
    assert pd.isna(row["wind_mph"])
    assert pd.isna(row["precip"])


def test_home_win_sign():
    p = _panel().set_index("game_id")
    assert p.loc["2019_01_A_B", "home_win"] == True
    assert p.loc["2019_01_A_B", "home_margin"] == 7
    assert p.loc["2020_01_C_D", "home_win"] == False
    assert p.loc["2020_01_C_D", "home_margin"] == -10


def test_missing_capacity_raises():
    cap = dict(_CAP); del cap["GGG00"]
    try:
        _build_panel(_fake_schedule(), _ATT, cap, [2020])
        assert False, "expected ValueError for missing stadium_id"
    except ValueError as e:
        assert "GGG00" in str(e)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_nfl_loader.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.data.nfl'` (or ImportError on `_build_panel`).

- [ ] **Step 3: Implement `_build_panel` (and module constants)**

Create `src/data/nfl.py`:

```python
"""NFL pilot loader → unified panel. Sport-specific logic lives here only.

Pipeline: nfl_data_py.import_schedules -> join ESPN attendance (cached) ->
apply venue capacity lookup -> _build_panel -> validate -> data/interim/nfl.parquet.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import yaml

from src.schema import COLUMNS, validate

RAW_DIR = Path("data/raw/nfl/espn")
INTERIM = Path("data/interim/nfl.parquet")
CONFIG_FILE = Path("config/sports.yaml")
CAPACITY_FILE = Path("config/nfl_venue_capacity.yaml")
ESPN_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={eid}"

# roof states with no live weather: fixed dome or retractable roof closed for the game.
DOME_ROOFS = frozenset({"dome", "closed"})


def _build_panel(schedule: pd.DataFrame, attendance: dict, capacity: dict,
                 treated_seasons: list) -> pd.DataFrame:
    """Pure transform: schedule + attendance/capacity dicts -> validated panel.

    Assumes `schedule` holds only PLAYED games whose `espn` id is present in
    `attendance` (the load() orchestrator guarantees this). Raises ValueError if
    any stadium_id is missing from `capacity`, or if the result fails validate().
    """
    df = schedule.reset_index(drop=True)

    att = df["espn"].astype(str).map(attendance)
    cap = df["stadium_id"].astype(str).map(capacity)
    missing_cap = sorted(df.loc[cap.isna(), "stadium_id"].astype(str).unique())
    if missing_cap:
        raise ValueError(f"stadium_id(s) missing from capacity lookup: {missing_cap}")

    is_dome = df["roof"].isin(DOME_ROOFS).to_numpy()
    home_margin = (df["home_score"] - df["away_score"]).astype(int)

    home_win = pd.Series(pd.NA, index=df.index, dtype="boolean")
    home_win[home_margin > 0] = True
    home_win[home_margin < 0] = False  # ties (margin == 0) stay <NA>

    temp_f = pd.to_numeric(df["temp"], errors="coerce").astype(float)
    wind_mph = pd.to_numeric(df["wind"], errors="coerce").astype(float)
    temp_f[is_dome] = np.nan
    wind_mph[is_dome] = np.nan

    panel = pd.DataFrame({
        "sport": "nfl",
        "game_id": df["game_id"].astype(str),
        "season": df["season"].astype(int),
        "date": pd.to_datetime(df["gameday"]),
        "is_playoff": df["game_type"].ne("REG").to_numpy(dtype=bool),
        "home_team": df["home_team"].astype(str),
        "away_team": df["away_team"].astype(str),
        "home_score": df["home_score"].astype(int),
        "away_score": df["away_score"].astype(int),
        "home_margin": home_margin,
        "home_win": home_win,
        "attendance": att.astype(int),
        "capacity": cap.astype(int),
        "crowd_pct": (att / cap).astype(float),
        "covid_era": df["season"].isin(treated_seasons).to_numpy(dtype=bool),
        "home_elo": 1500.0,   # neutral prior; Phase 4 overwrites
        "away_elo": 1500.0,
        "closing_spread": df["spread_line"].astype(float),
        "home_rest_days": df["home_rest"].astype("Int64"),
        "away_rest_days": df["away_rest"].astype("Int64"),
        "away_travel_km": pd.Series(np.nan, index=df.index, dtype=float),  # Phase 4
        "venue": df["stadium"].astype(str),
        "is_dome": is_dome,
        "temp_f": temp_f,
        "wind_mph": wind_mph,
        "precip": pd.Series(np.nan, index=df.index, dtype=float),  # not in source
        "neutral_site": df["location"].eq("Neutral").to_numpy(dtype=bool),
        "relocated_home": False,   # NFL: none in window
        "is_bubble": False,        # NFL: no bubble
    })

    panel = panel[list(COLUMNS)]
    validate(panel)
    return panel
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_nfl_loader.py -v`
Expected: PASS (all 7 tests).

- [ ] **Step 5: Checkpoint** — report to user; user commits.

---

### Task 3: `_fetch_attendance` — cached ESPN fetch

**Files:**
- Modify: `src/data/nfl.py`
- Test: `tests/test_nfl_loader.py`

**Interfaces:**
- Produces: `_fetch_attendance(espn_id: str, throttle: float = 0.7) -> int | None`. Reads `RAW_DIR/<espn_id>.json` if present; else GETs the ESPN summary endpoint, caches the raw JSON, sleeps `throttle`. Returns `gameInfo.attendance` (`None` if absent).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_nfl_loader.py`:

```python
import json
from src.data import nfl


def test_fetch_uses_cache_no_network(tmp_path, monkeypatch):
    monkeypatch.setattr(nfl, "RAW_DIR", tmp_path)
    (tmp_path / "999.json").write_text(json.dumps({"gameInfo": {"attendance": 54321}}))

    def _boom(*a, **k):
        raise AssertionError("network was hit despite cache present")

    monkeypatch.setattr(nfl.requests, "get", _boom)
    assert nfl._fetch_attendance("999") == 54321


def test_fetch_missing_attendance_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(nfl, "RAW_DIR", tmp_path)
    (tmp_path / "888.json").write_text(json.dumps({"gameInfo": {}}))
    monkeypatch.setattr(nfl.requests, "get", lambda *a, **k: (_ for _ in ()).throw(AssertionError()))
    assert nfl._fetch_attendance("888") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_nfl_loader.py -k fetch -v`
Expected: FAIL with `AttributeError: module 'src.data.nfl' has no attribute '_fetch_attendance'`.

- [ ] **Step 3: Implement `_fetch_attendance`**

Add to `src/data/nfl.py`:

```python
def _fetch_attendance(espn_id: str, throttle: float = 0.7) -> int | None:
    """Attendance for one game via the ESPN summary endpoint, cached to RAW_DIR.
    Returns None if ESPN has no attendance field for the game."""
    cache = RAW_DIR / f"{espn_id}.json"
    if cache.exists():
        data = json.loads(cache.read_text())
    else:
        resp = requests.get(ESPN_URL.format(eid=espn_id), timeout=30)
        resp.raise_for_status()
        data = resp.json()
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(data))  # data/raw is immutable — write once
        time.sleep(throttle)
    return data.get("gameInfo", {}).get("attendance")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_nfl_loader.py -k fetch -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Checkpoint** — report to user; user commits.

---

### Task 4: Capacity lookup file (`config/nfl_venue_capacity.yaml`)

This task discovers the real `stadium_id`s in the load window and hand-fills full capacities. It is a data task, not TDD — the verification is a coverage check that every `stadium_id` in the schedule is mapped.

**Files:**
- Create: `config/nfl_venue_capacity.yaml`
- Create (temporary, delete after): a scratch script or REPL snippet.

**Interfaces:**
- Consumes: `nfl_data_py.import_schedules`.
- Produces: `config/nfl_venue_capacity.yaml` mapping `stadium_id -> capacity` (int), plus `_load_capacity() -> dict[str, int]` in `src/data/nfl.py`.

- [ ] **Step 1: Discover the stadium_ids in the window**

Run this to list every `(stadium_id, stadium, roof)` used in 2018–2023:

```bash
.venv/bin/python -c "
import nfl_data_py as nfl, pandas as pd
s = nfl.import_schedules(list(range(2018, 2024)))
u = s[['stadium_id','stadium','roof']].dropna(subset=['stadium_id']).drop_duplicates('stadium_id').sort_values('stadium')
print(u.to_string(index=False))
print('COUNT', u['stadium_id'].nunique())
"
```

Expected: ~32–36 unique stadium_ids (30-odd home stadiums + a few neutral/international venues like London/Mexico City used 2018–2019).

- [ ] **Step 2: Write `config/nfl_venue_capacity.yaml`**

Map each printed `stadium_id` to its nominal full football capacity (int). Use the reference below (match by the printed `stadium` name); values are approximate full capacity — `crowd_pct` is a ratio so ±1–2k is immaterial to the treatment. **Every stadium_id from Step 1 must have an entry.** Header comment:

```yaml
# stadium_id -> nominal FULL football capacity (the COVID cap lives in
# attendance, not here). ponytail: one capacity per stadium, ignores year-to-year
# expansions/reconfigurations; upgrade to per-(stadium, season) only if it matters.
# crowd_pct = attendance / capacity is a ratio, so ±1-2k seats is immaterial.
```

Reference full capacities by team home stadium (map the printed `stadium` string / `stadium_id` to these):

```
Arizona (State Farm)        63400    New England (Gillette)      65800
Atlanta (Mercedes-Benz)     71000    New Orleans (Superdome)     73200
Baltimore (M&T Bank)        71000    NY Giants/Jets (MetLife)    82500
Buffalo (Highmark/Bills)    71600    Las Vegas (Allegiant)       65000
Carolina (Bank of America)  74900    Oakland (Coliseum, ≤2019)   56000
Chicago (Soldier Field)     61500    Philadelphia (Lincoln Fin.) 69600
Cincinnati (Paycor/PBS)     65500    Pittsburgh (Acrisure/Heinz) 68400
Cleveland (Huntington/First)67900    LA Rams+Chargers (SoFi,≥2020)70000
Dallas (AT&T)               80000    LA Rams (Coliseum, ≤2019)   77500
Denver (Empower/Mile High)  76100    LA Chargers (Dignity,≤2019) 27000
Detroit (Ford Field)        65000    San Francisco (Levi's)      68500
Green Bay (Lambeau)         81400    Seattle (Lumen/CenturyLink) 68700
Houston (NRG)               72200    Tampa Bay (Raymond James)   65600
Indianapolis (Lucas Oil)    67000    Tennessee (Nissan)          69100
Jacksonville (EverBank/TIAA)67800    Washington (FedEx)          82000
Kansas City (Arrowhead)     76400    Miami (Hard Rock)           65300
Minnesota (US Bank)         66900
# Neutral / international (2018-2019, if present in Step 1):
London (Wembley)            86000    London (Tottenham)          62800
Mexico City (Azteca)        87000
```

If Step 1 prints a `stadium_id`/`stadium` not covered above, look up that stadium's listed capacity and add it. Do not leave any id unmapped.

- [ ] **Step 3: Add `_load_capacity` + coverage check**

Add to `src/data/nfl.py`:

```python
def _load_capacity() -> dict:
    raw = yaml.safe_load(CAPACITY_FILE.read_text())
    return {str(k): int(v) for k, v in raw.items()}
```

Verify coverage — every scheduled stadium_id is mapped:

```bash
.venv/bin/python -c "
import nfl_data_py as nfl
from src.data.nfl import _load_capacity
s = nfl.import_schedules(list(range(2018, 2024)))
have = set(_load_capacity())
need = set(s['stadium_id'].dropna().astype(str).unique())
missing = need - have
print('MISSING:', sorted(missing))
assert not missing, missing
print('OK — all', len(need), 'stadium_ids mapped')
"
```

Expected: `OK — all N stadium_ids mapped`. If MISSING is non-empty, add those ids to the yaml (Step 2) and re-run.

- [ ] **Step 4: Delete any scratch script.** Confirm no temp files remain in the repo.

- [ ] **Step 5: Checkpoint** — report to user; user commits.

---

### Task 5: `load` + `main` + smoke gate

Wires the pipeline end to end and proves it on a tiny 2020 slice before the full pull.

**Files:**
- Modify: `src/data/nfl.py`

**Interfaces:**
- Consumes: `_fetch_attendance`, `_build_panel`, `_load_capacity`.
- Produces:
  - `load(seasons: list[int], treated_seasons: list[int], weeks: list[int] | None = None) -> tuple[pd.DataFrame, list[str]]` — returns `(panel, dropped_espn_ids)`.
  - `main(smoke: bool = False) -> None` — CLI entry; `--smoke` runs the 2020 wk1–2 gate, else the full config range → `data/interim/nfl.parquet`.

- [ ] **Step 1: Implement `load`, `main`, and the CLI**

Add to `src/data/nfl.py`:

```python
import argparse
from collections import defaultdict

import nfl_data_py as nfl


def load(seasons: list, treated_seasons: list, weeks: list | None = None):
    """Full pipeline for the given seasons. Returns (validated_panel, dropped_espn_ids).

    Drops unplayed games and games ESPN has no attendance for. Hard-fails if any
    season loses >5% of its played games to missing attendance (ESPN coverage broke).
    """
    sched = nfl.import_schedules(list(seasons))
    played = sched[sched["home_score"].notna() & sched["away_score"].notna()].copy()
    if weeks is not None:
        played = played[played["week"].isin(weeks)].copy()
    played["espn"] = played["espn"].astype(str)

    attendance: dict = {}
    dropped: list = []
    miss_by_season: dict = defaultdict(int)
    total_by_season = played["season"].value_counts().to_dict()

    for eid, season in zip(played["espn"], played["season"]):
        a = None if eid in ("nan", "None", "") else _fetch_attendance(eid)
        if a is None:
            dropped.append(eid)
            miss_by_season[season] += 1
        else:
            attendance[eid] = int(a)

    for season, miss in miss_by_season.items():
        frac = miss / total_by_season[season]
        if frac > 0.05:
            raise ValueError(
                f"season {season}: {miss}/{total_by_season[season]} "
                f"({frac:.0%}) games missing attendance (>5%) — ESPN coverage broke")

    played = played[played["espn"].isin(attendance)].copy()
    panel = _build_panel(played, attendance, _load_capacity(), treated_seasons)
    return panel, dropped


def _config_nfl() -> dict:
    return yaml.safe_load(CONFIG_FILE.read_text())["nfl"]


def main(smoke: bool = False) -> None:
    cfg = _config_nfl()
    treated = cfg["treated_seasons"]

    if smoke:
        panel, dropped = load([2020], treated, weeks=[1, 2])
        cols = ["game_id", "home_team", "away_team", "attendance", "capacity", "crowd_pct"]
        print(panel[cols].to_string(index=False))
        print(f"\nrows={len(panel)} dropped_missing_attendance={len(dropped)}")
        # 2020 wk1-2: empties exist and NOTHING is full (caps in force) — a broken
        # join would show ~60k everywhere or all-NaN. Spike reference: 15895/10166/0/0.
        assert (panel["crowd_pct"] == 0).any(), "expected empty-stadium games in 2020 wk1-2"
        assert panel["crowd_pct"].max() < 0.6, "2020 was capped — no full crowds expected"
        assert panel["attendance"].le(panel["capacity"]).all(), "attendance exceeds capacity"
        print("SMOKE OK")
        return

    lo, hi = cfg["load_seasons"]
    seasons = list(range(lo, hi + 1))
    panel, dropped = load(seasons, treated)
    INTERIM.parent.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(INTERIM)
    print(f"wrote {INTERIM} rows={len(panel)} "
          f"seasons={lo}-{hi} dropped_missing_attendance={len(dropped)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true",
                    help="run the 2020 wk1-2 gate and exit (no full pull)")
    main(smoke=ap.parse_args().smoke)
```

- [ ] **Step 2: Confirm unit tests still pass**

Run: `.venv/bin/pytest tests/test_nfl_loader.py -v`
Expected: PASS (all tests — the added code doesn't touch `_build_panel`/`_fetch_attendance`).

- [ ] **Step 3: Run the smoke gate (first real ESPN fetch — ~30 games, ~1 min)**

Run: `.venv/bin/python -m src.data.nfl --smoke`
Expected: a printed table of ~25–30 games, some with `crowd_pct` 0.0 and none above ~0.5, ending in `SMOKE OK`. Raw JSON now cached under `data/raw/nfl/espn/`.

If it fails: inspect the printed table. All-NaN crowd_pct → attendance join broken (check `espn` id type/formatting). ~60k everywhere → wrong season or attendance field. A capacity ValueError → add the stadium_id to Task 4's yaml.

- [ ] **Step 4: Checkpoint** — report smoke output to user; user commits.

---

### Task 6: Full pull → `data/interim/nfl.parquet`

The full 2018–2023 fetch. Long-running (~30–60 min, ESPN throttled) but resumable — cached games are skipped on re-run.

**Files:**
- Produces: `data/interim/nfl.parquet`

- [ ] **Step 1: Run the full pull**

Run: `.venv/bin/python -m src.data.nfl`
Expected: after the fetch loop, `wrote data/interim/nfl.parquet rows=~1600 seasons=2018-2023 dropped_missing_attendance=<small>`.

- [ ] **Step 2: Verify the written panel**

Run:

```bash
.venv/bin/python -c "
import pandas as pd
from src.schema import validate
p = pd.read_parquet('data/interim/nfl.parquet')
validate(p)  # raises if the round-tripped panel is off
print('rows', len(p), 'seasons', sorted(p['season'].unique()))
print('crowd_pct by season (mean):')
print(p.groupby('season')['crowd_pct'].mean().round(3))
print('empty games (crowd_pct==0):', int((p['crowd_pct'] == 0).sum()))
"
```

Expected: ~1600 rows across 2018–2023; `crowd_pct` mean ≈ 0.9+ in 2018/2019/2022/2023, sharply lower in 2020 (many zeros), partial in 2021; a chunk of `crowd_pct==0` games (2020 empties). This before/during/after shape is the whole point — sanity-check it looks right.

- [ ] **Step 3: Checkpoint** — report row counts + the per-season crowd_pct table to user; user commits. Phase 2 done.

---

## Self-Review

**Spec coverage:**
- Architecture (`_build_panel`/`_fetch_attendance`/`load`/`main`) → Tasks 2, 3, 5. ✓
- Column mapping table + dtype coercion → Task 2 `_build_panel`. ✓
- Capacity lookup keyed on stadium_id, hard-error on gaps → Task 4 + `_build_panel` check. ✓
- Missing-attendance drop-and-log + 5% circuit breaker → Task 5 `load`. ✓
- Smoke test w/ 2020 anchors → Task 5 Step 3. ✓
- Config `load_seasons` → Task 1. ✓
- Parquet output → Task 6. ✓
- Testing (validate, empty→0, tie→null, dome→null weather, sign, fetch cache) → Tasks 2, 3. ✓

**Placeholder scan:** No TBD/TODO; all code shown; capacity values provided as a reference table (Task 4 reconciles printed names to it). ✓

**Type consistency:** `_build_panel(schedule, attendance, capacity, treated_seasons)`, `_fetch_attendance(espn_id, throttle)`, `_load_capacity()`, `load(seasons, treated_seasons, weeks)`, `main(smoke)` — names/signatures consistent across Tasks 2–6. `RAW_DIR`/`INTERIM`/`CAPACITY_FILE`/`CONFIG_FILE`/`DOME_ROOFS` defined once in Task 2, reused. ✓

---

## Plan revision (2026-07-02): Option A — empirical capacity

Supersedes Task 4 (static yaml) and adjusts Tasks 2 & 5. See spec Addendum.

**Task 2 change** — `_build_panel`'s `capacity` arg is now keyed by `(stadium_id, season)`
tuples, not `stadium_id`. Missing-key error and the `_CAP` test fixture update to tuple keys.

**Task 4 (revised) — `_derive_capacity`:**
- `_derive_capacity(df) -> dict[(stadium_id, season), int]`. Per stadium: `season_max =
  attendance.max()` per season; `omax = season_max.max()`; a season is suppressed if
  `season_max < 0.5*omax`; normal seasons map to their own max; suppressed seasons map to
  the max over that stadium's non-suppressed seasons.
- Replaces `config/nfl_venue_capacity.yaml` + `_load_capacity` (both removed).
- Test: a fake multi-season attendance frame where one season is ~empty; assert normal
  seasons self-reference and the empty season borrows the non-suppressed max.

**Task 5 (revised) — `load` + `main` + smoke:**
- `load(seasons, treated_seasons)` (no `weeks`): fetch attendance; drop null `espn` then
  `.astype("int64").astype(str)` (the float-id bug fix); circuit-break >5%/season missing;
  attach `attendance` column; `capacity = _derive_capacity(played)`; `_build_panel(...)`.
- `main(smoke=False)`: both branches run the full configured load (cache is warm → fast).
  smoke slices the returned panel to `season == 2020`, prints it, and asserts
  `(crowd_pct == 0).any()` and `crowd_pct.max() < 0.6`; non-smoke writes parquet.

**Task 6** — unchanged, but the cache is already warm from the audit, so the full pull is
seconds, not 30–60 min.
