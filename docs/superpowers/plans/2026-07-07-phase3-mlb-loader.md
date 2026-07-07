# Phase 3 MLB Loader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Emit the validated 29-column unified panel for MLB seasons 2018–2023 to `data/interim/mlb.parquet`, single-source from ESPN, carrying the COVID crowd-dose signal.

**Architecture:** Extract a shared `src/data/_espn.py` (cached ESPN summary fetch, scoreboard-by-date walk, and the sport-blind `derive_capacity`/`check_coverage` moved from `nfl.py`). `src/data/mlb.py` is thin glue: walk the scoreboard → fetch attendance → filter to regular+postseason → map to the panel → validate. NFL is touched minimally: it imports the two moved helpers under their old private names, keeping its 28 tests green unchanged.

**Tech Stack:** Python 3.11+, pandas, numpy, requests, PyYAML, pytest. ESPN public site API (`site.api.espn.com`).

## Global Constraints

- Every loader returns the exact `src.schema.COLUMNS` set and passes `src.schema.validate()`. Sport-specific logic lives only in `src/data/`.
- `data/raw/` is immutable, write-once. ESPN responses cache to `data/raw/<sport>/espn/`.
- `crowd_pct == 0` is a REAL value (empty stadium), never coerced to null.
- Capacity = Option A empirical full-house; capped treated-season attendance (2020/2021) is NEVER used as a capacity — treated seasons borrow the venue's non-treated max.
- MLB weather columns (`temp_f`, `wind_mph`, `precip`) are null; no weather parser.
- `home_elo`/`away_elo` = 1500.0, `closing_spread`/`home_rest_days`/`away_rest_days`/`away_travel_km` = null (Phase 4 placeholders). The panel still passes the full `validate()`.
- MLB config: `load_seasons: [2018, 2023]`, `treated_seasons: [2020, 2021]`.
- Git is user-owned: run `git add`/`git commit` steps ONLY if the executing session is authorized to commit. Otherwise stage nothing and leave commits to the user.

---

### Task 1: Extract `derive_capacity` + `check_coverage` into `src/data/_espn.py`; alias them back into NFL

Move the two sport-blind helpers verbatim so all sports share one capacity/coverage implementation. NFL re-imports them under its old private names, so its existing tests are untouched.

**Files:**
- Create: `src/data/_espn.py`
- Create: `tests/test_espn.py`
- Modify: `src/data/nfl.py` (remove the two local defs; add an aliasing import)
- Reference (unchanged): `tests/test_nfl_loader.py`

**Interfaces:**
- Produces: `derive_capacity(df, treated_seasons) -> dict[(str, int), int]` where `df` has columns `stadium_id`, `season`, `attendance`; keys are `(stadium_id, season)`, values `>= 1`.
- Produces: `check_coverage(miss: dict[int, int], total: dict[int, int]) -> None`; raises `ValueError` if any season's `miss/total > 0.05`.

- [ ] **Step 1: Write the failing tests** in `tests/test_espn.py`

```python
import pandas as pd
import pytest
from src.data._espn import derive_capacity, check_coverage


def test_derive_capacity_self_reference_and_borrow():
    # venue "A": normal seasons self-reference their own max; treated 2020 borrows
    # the max over non-treated seasons (here 60000 from 2019), not its own 5000.
    df = pd.DataFrame({
        "stadium_id": ["A", "A", "A", "A"],
        "season":     [2019, 2019, 2020, 2020],
        "attendance": [40000, 60000, 5000, 0],
    })
    cap = derive_capacity(df, treated_seasons=[2020])
    assert cap[("A", 2019)] == 60000
    assert cap[("A", 2020)] == 60000  # borrowed, not 5000


def test_derive_capacity_only_treated_falls_back_to_own_max():
    df = pd.DataFrame({
        "stadium_id": ["B", "B"],
        "season":     [2020, 2020],
        "attendance": [0, 12000],
    })
    cap = derive_capacity(df, treated_seasons=[2020])
    assert cap[("B", 2020)] == 12000  # own max fallback, floored >= 1


def test_check_coverage_trips_above_5pct():
    check_coverage({2019: 1}, {2019: 100})       # 1% -> fine
    with pytest.raises(ValueError):
        check_coverage({2020: 2}, {2020: 10})    # 20% -> hard fail
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_espn.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.data._espn'`

- [ ] **Step 3: Create `src/data/_espn.py`** with the two helpers moved verbatim from `nfl.py:102-141`

```python
"""Shared ESPN data-access helpers for the per-sport loaders (NFL/MLB/NBA).

Single source of truth for the sport-blind capacity/coverage math so every sport
computes crowd_pct the same way, plus the cached ESPN fetch + scoreboard walk used
by the ESPN-sourced loaders (MLB, NBA; NFL keeps its own fetch).
"""
from __future__ import annotations


def derive_capacity(df, treated_seasons: list) -> dict:
    """Empirical full-house reference per (stadium_id, season). A NORMAL season
    self-references its own MAX announced attendance; a TREATED (COVID-restricted)
    season borrows the stadium's max over its non-treated seasons, since a
    capacity-capped season's own attendance is not a valid full house.

    Suppression is decided from `treated_seasons`, NOT a magnitude guess.
    Requires an `attendance` column. Returns {(stadium_id, season): capacity_int>=1}."""
    treated = set(treated_seasons)
    d = df[["stadium_id", "season", "attendance"]].dropna(subset=["attendance"]).copy()
    d["stadium_id"] = d["stadium_id"].astype(str)
    d["season"] = d["season"].astype(int)
    d["attendance"] = d["attendance"].astype(int)

    ref: dict = {}
    for sid, sub in d.groupby("stadium_id"):
        season_max = sub.groupby("season")["attendance"].max()
        normal = season_max[~season_max.index.isin(treated)]
        fallback = int(normal.max()) if len(normal) else int(season_max.max())
        for season, smax in season_max.items():
            cap = fallback if int(season) in treated else int(smax)
            ref[(sid, int(season))] = max(cap, 1)
    return ref


def check_coverage(miss: dict, total: dict) -> None:
    """Hard-fail if any season lost >5% of its played games to missing attendance."""
    for season, m in miss.items():
        if m / total[season] > 0.05:
            raise ValueError(
                f"season {season}: {m}/{total[season]} ({m / total[season]:.0%}) "
                f"games missing attendance (>5%) — ESPN coverage broke")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_espn.py -v`
Expected: 3 passed.

- [ ] **Step 5: Update `src/data/nfl.py`** — delete the local `_derive_capacity` and `_check_coverage` definitions (lines 102-141) and re-import them under their old names

Add near the other imports (after `from src.schema import COLUMNS, validate`):

```python
# derive_capacity/check_coverage now live in _espn.py (shared with MLB/NBA) so all
# sports compute crowd_pct identically. Keep the old private names for local use.
from src.data._espn import derive_capacity as _derive_capacity
from src.data._espn import check_coverage as _check_coverage
```

Then remove the two function bodies `def _derive_capacity(...)` and `def _check_coverage(...)`. Leave everything else (`_build_panel`, `_fetch_attendance`, `RAW_DIR`, `ESPN_URL`, `load`, `main`) untouched.

- [ ] **Step 6: Run the FULL suite to prove NFL stayed green**

Run: `pytest -v`
Expected: all previously-passing tests pass (28 NFL + 15 schema/config) plus the 3 new `_espn` tests. `tests/test_nfl_loader.py` imports `from src.data.nfl import _derive_capacity, _check_coverage` and still resolves via the aliases.

- [ ] **Step 7: Commit** (only if authorized to commit)

```bash
git add src/data/_espn.py tests/test_espn.py src/data/nfl.py
git commit -m "refactor: extract shared derive_capacity/check_coverage into _espn.py"
```

---

### Task 2: `fetch_summary` — cached ESPN summary attendance fetch

Generalize NFL's cached summary fetch over sport. New consumers (MLB now, NBA later) call it; NFL keeps its own copy.

**Files:**
- Modify: `src/data/_espn.py`
- Modify: `tests/test_espn.py`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `fetch_summary(sport: str, event_id: str, throttle: float = 0.7) -> int | None`. `sport` in `{"nfl","mlb","nba"}`. Reads/writes cache `data/raw/<sport>/espn/<event_id>.json`. Returns `gameInfo.attendance` or `None`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_espn.py`)

```python
import json
from src.data import _espn


def test_fetch_summary_uses_cache_no_network(tmp_path, monkeypatch):
    monkeypatch.setattr(_espn, "_RAW_ROOT", tmp_path)
    cache = tmp_path / "mlb" / "espn"
    cache.mkdir(parents=True)
    (cache / "555.json").write_text(json.dumps({"gameInfo": {"attendance": 22320}}))

    def boom(*a, **k):
        raise AssertionError("network hit despite cache")
    monkeypatch.setattr(_espn.requests, "get", boom)

    assert _espn.fetch_summary("mlb", "555") == 22320


def test_fetch_summary_missing_attendance_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(_espn, "_RAW_ROOT", tmp_path)
    cache = tmp_path / "mlb" / "espn"
    cache.mkdir(parents=True)
    (cache / "777.json").write_text(json.dumps({"gameInfo": {}}))
    assert _espn.fetch_summary("mlb", "777") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_espn.py -k fetch_summary -v`
Expected: FAIL (`AttributeError: module 'src.data._espn' has no attribute 'fetch_summary'`).

- [ ] **Step 3: Implement `fetch_summary`** — add imports and code to `src/data/_espn.py`

At the top (below `from __future__`):

```python
import json
import time
from pathlib import Path

import requests

_RAW_ROOT = Path("data/raw")
SPORT_PATH = {"nfl": "football/nfl", "mlb": "baseball/mlb", "nba": "basketball/nba"}
_SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/{path}/summary?event={eid}"


def _espn_dir(sport: str) -> Path:
    return _RAW_ROOT / sport / "espn"
```

Then the function:

```python
def fetch_summary(sport: str, event_id: str, throttle: float = 0.7) -> int | None:
    """Attendance for one game via the ESPN summary endpoint, cached (write-once)
    to data/raw/<sport>/espn/<event_id>.json. Returns None if ESPN has no
    attendance field. `event_id` must already be a clean string id."""
    cache = _espn_dir(sport) / f"{event_id}.json"
    if cache.exists():
        data = json.loads(cache.read_text())
    else:
        url = _SUMMARY_URL.format(path=SPORT_PATH[sport], eid=event_id)
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(data))
        time.sleep(throttle)
    return data.get("gameInfo", {}).get("attendance")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_espn.py -k fetch_summary -v`
Expected: 2 passed.

- [ ] **Step 5: Commit** (only if authorized)

```bash
git add src/data/_espn.py tests/test_espn.py
git commit -m "feat: add cached ESPN fetch_summary to _espn.py"
```

---

### Task 3: `walk_scoreboard` — ESPN scoreboard-by-date event walk

Iterate calendar dates, pull the cached scoreboard, and yield one normalized dict per event. Filtering by type/status is the loader's job; this yields everything with a `competitions` block.

**Files:**
- Modify: `src/data/_espn.py`
- Modify: `tests/test_espn.py`

**Interfaces:**
- Produces: `walk_scoreboard(sport: str, start: datetime.date, end: datetime.date) -> Iterator[dict]`. Each dict: `{event_id:str, date:str, season_year:int, season_type:int, home_abbr:str, away_abbr:str, home_score:int|None, away_score:int|None, venue_id:str, venue_name:str, neutral_site:bool, status:str}`. Caches each day to `data/raw/<sport>/espn/scoreboard/<YYYYMMDD>.json`. Skips events with no `competitions` or missing a home/away competitor.

- [ ] **Step 1: Write the failing test** (append to `tests/test_espn.py`)

```python
import datetime as dt


def _canned_scoreboard():
    return {"events": [
        {"id": "401", "date": "2019-06-15T20:00Z",
         "season": {"year": 2019, "type": 2},
         "competitions": [{
             "neutralSite": False,
             "venue": {"id": "31", "fullName": "Tropicana Field"},
             "status": {"type": {"name": "STATUS_FINAL"}},
             "competitors": [
                 {"homeAway": "home", "team": {"abbreviation": "TB"}, "score": "3"},
                 {"homeAway": "away", "team": {"abbreviation": "LAA"}, "score": "5"},
             ]}]},
        {"id": "999", "date": "2019-06-15T21:00Z",
         "season": {"year": 2019, "type": 2}},  # no competitions -> skipped
    ]}


def test_walk_scoreboard_parses_and_skips(tmp_path, monkeypatch):
    monkeypatch.setattr(_espn, "_RAW_ROOT", tmp_path)
    sb_dir = tmp_path / "mlb" / "espn" / "scoreboard"
    sb_dir.mkdir(parents=True)
    (sb_dir / "20190615.json").write_text(json.dumps(_canned_scoreboard()))

    def boom(*a, **k):
        raise AssertionError("network hit despite cache")
    monkeypatch.setattr(_espn.requests, "get", boom)

    day = dt.date(2019, 6, 15)
    rows = list(_espn.walk_scoreboard("mlb", day, day))
    assert len(rows) == 1                 # the no-competitions event was skipped
    r = rows[0]
    assert r["event_id"] == "401"
    assert r["season_type"] == 2
    assert r["home_abbr"] == "TB" and r["away_abbr"] == "LAA"
    assert r["home_score"] == 3 and r["away_score"] == 5
    assert r["venue_id"] == "31"
    assert r["neutral_site"] is False
    assert r["status"] == "STATUS_FINAL"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_espn.py -k walk_scoreboard -v`
Expected: FAIL (`AttributeError: ... has no attribute 'walk_scoreboard'`).

- [ ] **Step 3: Implement `walk_scoreboard`** — add to `src/data/_espn.py`

Add imports at the top:

```python
import datetime as dt
from typing import Iterator
```

Add the URL constant near `_SUMMARY_URL`:

```python
_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/{path}/scoreboard?dates={d}"
```

Then:

```python
def _to_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _fetch_scoreboard(sport: str, day: dt.date, throttle: float = 0.7) -> dict:
    cache = _espn_dir(sport) / "scoreboard" / f"{day:%Y%m%d}.json"
    if cache.exists():
        return json.loads(cache.read_text())
    url = _SCOREBOARD_URL.format(path=SPORT_PATH[sport], d=f"{day:%Y%m%d}")
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(data))
    time.sleep(throttle)
    return data


def walk_scoreboard(sport: str, start: dt.date, end: dt.date) -> Iterator[dict]:
    """Yield one normalized dict per ESPN event across [start, end] inclusive.
    Skips events lacking a competitions block or a home/away competitor. Season-type
    and status filtering is the caller's responsibility."""
    day = start
    while day <= end:
        data = _fetch_scoreboard(sport, day)
        for ev in data.get("events", []):
            comps = ev.get("competitions")
            if not comps:
                continue
            comp = comps[0]
            home = away = None
            for c in comp.get("competitors", []):
                side = c.get("homeAway")
                if side == "home":
                    home = c
                elif side == "away":
                    away = c
            if home is None or away is None:
                continue
            season = ev.get("season", {})
            venue = comp.get("venue", {})
            status = (comp.get("status") or ev.get("status") or {})
            yield {
                "event_id": str(ev["id"]),
                "date": ev.get("date"),
                "season_year": _to_int(season.get("year")),
                "season_type": _to_int(season.get("type")),
                "home_abbr": home["team"].get("abbreviation"),
                "away_abbr": away["team"].get("abbreviation"),
                "home_score": _to_int(home.get("score")),
                "away_score": _to_int(away.get("score")),
                "venue_id": str(venue.get("id")),
                "venue_name": venue.get("fullName"),
                "neutral_site": bool(comp.get("neutralSite", False)),
                "status": status.get("type", {}).get("name"),
            }
        day += dt.timedelta(days=1)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_espn.py -k walk_scoreboard -v`
Expected: 1 passed.

- [ ] **Step 5: Commit** (only if authorized)

```bash
git add src/data/_espn.py tests/test_espn.py
git commit -m "feat: add walk_scoreboard to _espn.py"
```

---

### Task 4: `mlb._select_games` + `mlb._build_panel` — pure transforms to the panel

The sport-specific mapping. `_select_games` filters walked events to played regular+postseason games; `_build_panel` maps them to the validated 29-col panel. Both are pure (no net/disk).

**Files:**
- Create: `src/data/mlb.py`
- Create: `tests/test_mlb_loader.py`

**Interfaces:**
- Consumes: event dicts from `walk_scoreboard` (Task 3); `derive_capacity` (Task 1).
- Produces: `_select_games(events: Iterable[dict]) -> list[dict]` — keeps `season_type in {2,3}` and `status == "STATUS_FINAL"` with both scores present.
- Produces: `_build_panel(games: list[dict], attendance: dict[str,int], capacity: dict[(str,int),int], treated_seasons: list) -> pd.DataFrame` — validated panel. `attendance` keyed by `event_id`; `capacity` keyed by `(venue_id, season)`.

- [ ] **Step 1: Write the failing tests** in `tests/test_mlb_loader.py`

```python
import pandas as pd
import pytest
from src.data.mlb import _select_games, _build_panel
from src.schema import validate, COLUMNS


def _game(event_id, home="NYY", away="BOS", hs=5, as_=3, season=2019,
          stype=2, venue_id="10", venue="Yankee Stadium", neutral=False,
          status="STATUS_FINAL", date="2019-06-15T20:00Z"):
    return {"event_id": event_id, "date": date, "season_year": season,
            "season_type": stype, "home_abbr": home, "away_abbr": away,
            "home_score": hs, "away_score": as_, "venue_id": venue_id,
            "venue_name": venue, "neutral_site": neutral, "status": status}


def test_select_drops_preseason_allstar_and_unplayed():
    events = [
        _game("1", stype=1),                         # spring training -> drop
        _game("2", stype=4),                         # all-star -> drop
        _game("3", stype=2),                         # regular -> keep
        _game("4", stype=3),                         # postseason -> keep
        _game("5", stype=2, status="STATUS_SCHEDULED"),  # unplayed -> drop
        _game("6", stype=2, hs=None),                # missing score -> drop
    ]
    kept = {g["event_id"] for g in _select_games(events)}
    assert kept == {"3", "4"}


def _panel_of(games, treated=(2020, 2021)):
    att = {g["event_id"]: 40000 for g in games}
    cap_df = pd.DataFrame({"stadium_id": [g["venue_id"] for g in games],
                           "season": [g["season_year"] for g in games],
                           "attendance": list(att.values())})
    from src.data._espn import derive_capacity
    cap = derive_capacity(cap_df, list(treated))
    return _build_panel(games, att, cap, list(treated))


def test_build_panel_validates_and_columns_exact():
    panel = _panel_of([_game("1"), _game("2", home="LAD", venue_id="11")])
    validate(panel)
    assert list(panel.columns) == list(COLUMNS)
    assert (panel["sport"] == "mlb").all()
    assert panel["game_id"].tolist() == ["mlb_1", "mlb_2"]


def test_home_margin_and_win():
    panel = _panel_of([_game("1", hs=5, as_=3), _game("2", hs=2, as_=6)])
    assert panel["home_margin"].tolist() == [2, -4]
    assert panel["home_win"].tolist() == [True, False]


def test_is_playoff_from_season_type():
    panel = _panel_of([_game("1", stype=2), _game("2", stype=3)])
    assert panel["is_playoff"].tolist() == [False, True]


def test_is_dome_only_permanent_dome():
    panel = _panel_of([_game("1", venue_id="31"),   # Tropicana -> dome
                       _game("2", venue_id="10")])  # open -> not dome
    assert panel["is_dome"].tolist() == [True, False]
    assert panel.loc[panel["is_dome"], ["temp_f", "wind_mph", "precip"]].isna().all().all()


def test_blue_jays_2020_relocated_home():
    panel = _panel_of([_game("1", home="TOR", season=2020, venue_id="99"),
                       _game("2", home="TOR", season=2019, venue_id="12"),
                       _game("3", home="NYY", season=2020, venue_id="10")])
    reloc = dict(zip(panel["game_id"], panel["relocated_home"]))
    assert reloc == {"mlb_1": True, "mlb_2": False, "mlb_3": False}


def test_doubleheader_game_ids_unique():
    # same date/teams/venue, two distinct ESPN ids -> two unique game_ids
    panel = _panel_of([_game("100"), _game("101")])
    assert panel["game_id"].is_unique


def test_neutral_site_from_espn_flag():
    panel = _panel_of([_game("1", neutral=True), _game("2", neutral=False)])
    assert panel["neutral_site"].tolist() == [True, False]


def test_crowd_pct_and_placeholders():
    panel = _panel_of([_game("1")])
    row = panel.iloc[0]
    assert row["crowd_pct"] == 1.0            # 40000/40000
    assert row["home_elo"] == 1500.0 and row["away_elo"] == 1500.0
    assert pd.isna(row["closing_spread"]) and pd.isna(row["away_travel_km"])
    assert pd.isna(row["home_rest_days"]) and pd.isna(row["temp_f"])
    assert bool(row["is_bubble"]) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_mlb_loader.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'src.data.mlb'`).

- [ ] **Step 3: Implement `src/data/mlb.py`** (transforms + constants; `load`/`main` come in Task 5)

```python
"""MLB loader → unified panel. Single-source from ESPN (schedule/scores via the
scoreboard walk, attendance via the summary endpoint). Sport-specific logic only.

No weather is captured for MLB (it doesn't confound a policy-identified, margin-
outcome crowd estimate; see the design spec). is_dome flags only MLB's one
permanent dome; retractables are treated as open (venue-level approximation,
analytically inert since weather is null).
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import yaml

from src.data._espn import check_coverage, derive_capacity, fetch_summary, walk_scoreboard
from src.schema import COLUMNS, validate

INTERIM = Path("data/interim/mlb.parquet")
CONFIG_FILE = Path("config/sports.yaml")

# ESPN season.type: 2 = regular, 3 = postseason (1 = preseason, 4 = all-star).
PLAYED_TYPES = frozenset({2, 3})
FINAL = "STATUS_FINAL"
# ponytail: MLB's only permanent (non-retractable) dome is Tropicana Field
# (ESPN venue id 31). Retractables -> open; inert here since MLB weather is null.
PERMANENT_DOME_VENUE_IDS = frozenset({"31"})


def _select_games(events: Iterable[dict]) -> list[dict]:
    """Keep only played regular-season + postseason games (drop preseason, all-star,
    and unplayed/incomplete rows)."""
    out = []
    for g in events:
        if g["season_type"] not in PLAYED_TYPES:
            continue
        if g["status"] != FINAL:
            continue
        if g["home_score"] is None or g["away_score"] is None:
            continue
        out.append(g)
    return out


def _build_panel(games: list[dict], attendance: dict, capacity: dict,
                 treated_seasons: list) -> pd.DataFrame:
    """Pure transform: selected games + attendance/capacity dicts -> validated panel.
    `attendance` keyed by event_id, `capacity` by (venue_id, season). Raises
    ValueError on a missing capacity key or a validate() failure."""
    df = pd.DataFrame(games).reset_index(drop=True)

    keys = list(zip(df["venue_id"].astype(str), df["season_year"].astype(int)))
    missing_cap = sorted({k for k in keys if k not in capacity})
    if missing_cap:
        raise ValueError(f"(venue_id, season) missing from capacity: {missing_cap}")
    cap = pd.Series([capacity[k] for k in keys], index=df.index)
    att = df["event_id"].map(attendance)

    home_margin = (df["home_score"] - df["away_score"]).astype(int)
    home_win = pd.Series(pd.NA, index=df.index, dtype="boolean")
    home_win[home_margin > 0] = True
    home_win[home_margin < 0] = False   # ties (margin == 0) stay <NA>

    season = df["season_year"].astype(int)
    is_dome = df["venue_id"].astype(str).isin(PERMANENT_DOME_VENUE_IDS).to_numpy()
    relocated = ((df["home_abbr"] == "TOR") & (season == 2020)).to_numpy()

    nan = lambda: pd.Series(np.nan, index=df.index, dtype=float)
    panel = pd.DataFrame({
        "sport": "mlb",
        "game_id": "mlb_" + df["event_id"].astype(str),
        "season": season,
        "date": pd.to_datetime(df["date"]).dt.tz_localize(None),
        "is_playoff": df["season_type"].eq(3).to_numpy(dtype=bool),
        "home_team": df["home_abbr"].astype(str),
        "away_team": df["away_abbr"].astype(str),
        "home_score": df["home_score"].astype(int),
        "away_score": df["away_score"].astype(int),
        "home_margin": home_margin,
        "home_win": home_win,
        "attendance": att.astype(int),
        "capacity": cap.astype(int),
        "crowd_pct": (att / cap).astype(float),
        "covid_era": season.isin(treated_seasons).to_numpy(dtype=bool),
        "home_elo": 1500.0,
        "away_elo": 1500.0,
        "closing_spread": nan(),          # baseball is a moneyline sport; Elo controls quality
        "home_rest_days": pd.Series(pd.NA, index=df.index, dtype="Int64"),  # Phase 4
        "away_rest_days": pd.Series(pd.NA, index=df.index, dtype="Int64"),  # Phase 4
        "away_travel_km": nan(),          # Phase 4
        "venue": df["venue_name"].astype(str),
        "is_dome": is_dome,
        "temp_f": nan(),                  # no MLB weather
        "wind_mph": nan(),
        "precip": nan(),
        "neutral_site": df["neutral_site"].to_numpy(dtype=bool),
        "relocated_home": relocated,
        "is_bubble": False,               # NBA-only concept
    })

    panel = panel[list(COLUMNS)]
    validate(panel)
    return panel
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_mlb_loader.py -v`
Expected: all tests pass.

- [ ] **Step 5: Commit** (only if authorized)

```bash
git add src/data/mlb.py tests/test_mlb_loader.py
git commit -m "feat: add MLB _select_games and _build_panel transforms"
```

---

### Task 5: `mlb.load` + `mlb.main` orchestration + config, with a real-data smoke check

Wire the pieces into the full pipeline, add MLB to `config/sports.yaml`, and prove the 2020 dose signal on real ESPN data.

**Files:**
- Modify: `src/data/mlb.py`
- Modify: `config/sports.yaml`
- Modify: `tests/test_mlb_loader.py`

**Interfaces:**
- Consumes: `_select_games`, `_build_panel` (Task 4); `walk_scoreboard`, `fetch_summary`, `derive_capacity`, `check_coverage` (Tasks 1–3).
- Produces: `load(seasons: Iterable[int], treated_seasons: list) -> tuple[pd.DataFrame, list[str]]`; `main(smoke: bool = False) -> None`.

- [ ] **Step 1: Add MLB config** to `config/sports.yaml` (mirror the NFL block)

```yaml
mlb:
  load_seasons: [2018, 2023]
  treated_seasons: [2020, 2021]
```

- [ ] **Step 2: Write the failing orchestration test** (append to `tests/test_mlb_loader.py`)

```python
def test_load_orchestrates_walk_fetch_and_coverage(monkeypatch):
    # two 2019 games at the same venue + one unplayed; attendance fetched per id.
    events = [
        _game("1", venue_id="10", hs=5, as_=3),
        _game("2", venue_id="10", hs=1, as_=0),
        _game("9", venue_id="10", status="STATUS_SCHEDULED"),  # dropped by _select
    ]
    from src.data import mlb
    monkeypatch.setattr(mlb, "walk_scoreboard", lambda sport, s, e: iter(events))
    monkeypatch.setattr(mlb, "fetch_summary",
                        lambda sport, eid: {"1": 30000, "2": 40000}.get(eid))
    panel, dropped = mlb.load([2019], treated_seasons=[2020, 2021])
    assert len(panel) == 2
    assert panel["game_id"].tolist() == ["mlb_1", "mlb_2"]
    # capacity = venue's 2019 max (40000); crowd_pct is dose vs full house
    assert panel.set_index("game_id").loc["mlb_1", "crowd_pct"] == 30000 / 40000
    assert dropped == []
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_mlb_loader.py -k load_orchestrates -v`
Expected: FAIL (`AttributeError: module 'src.data.mlb' has no attribute 'load'`).

- [ ] **Step 4: Implement `load` + `main`** — append to `src/data/mlb.py`

```python
def _season_window(year: int) -> tuple[dt.date, dt.date]:
    # generous: late-March openers through the early-November World Series.
    return dt.date(year, 3, 1), dt.date(year, 11, 30)


def load(seasons, treated_seasons):
    """Full pipeline for the given seasons. Returns (validated_panel, dropped_ids).
    Drops unplayed/preseason/all-star games and games ESPN has no attendance for.
    Hard-fails if any season loses >5% of its played games to missing attendance."""
    games = []
    for year in seasons:
        start, end = _season_window(int(year))
        games.extend(_select_games(walk_scoreboard("mlb", start, end)))

    total = defaultdict(int)
    for g in games:
        total[int(g["season_year"])] += 1

    attendance: dict = {}
    dropped: list = []
    miss = defaultdict(int)
    for g in games:
        a = fetch_summary("mlb", g["event_id"])
        if a is None:
            dropped.append(g["event_id"])
            miss[int(g["season_year"])] += 1
        else:
            attendance[g["event_id"]] = int(a)

    check_coverage(miss, total)

    games = [g for g in games if g["event_id"] in attendance]
    cap_df = pd.DataFrame({
        "stadium_id": [g["venue_id"] for g in games],
        "season": [g["season_year"] for g in games],
        "attendance": [attendance[g["event_id"]] for g in games],
    })
    capacity = derive_capacity(cap_df, list(treated_seasons))
    panel = _build_panel(games, attendance, capacity, list(treated_seasons))
    return panel, dropped


def _config_mlb() -> dict:
    return yaml.safe_load(CONFIG_FILE.read_text())["mlb"]


def main(smoke: bool = False) -> None:
    cfg = _config_mlb()
    treated = cfg["treated_seasons"]
    lo, hi = cfg["load_seasons"]

    if smoke:
        panel, dropped = load([2019, 2020], treated)
        sub = panel[panel["season"] == 2020]
        print(f"2020 rows={len(sub)} crowd_pct max={sub['crowd_pct'].max():.3f} "
              f"empties={(sub['crowd_pct'] == 0).sum()} dropped={len(dropped)}")
        assert (sub["crowd_pct"] == 0).any(), "expected empty-stadium 2020 games"
        assert sub["crowd_pct"].max() < 0.6, "2020 was capped — no full crowds expected"
        assert panel["attendance"].le(panel["capacity"]).all(), "attendance exceeds capacity"
        print("SMOKE OK")
        return

    panel, dropped = load(range(lo, hi + 1), treated)
    INTERIM.parent.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(INTERIM)
    print(f"wrote {INTERIM} rows={len(panel)} seasons={lo}-{hi} "
          f"dropped_missing_attendance={len(dropped)}")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true",
                    help="run 2019+2020 assertions on real ESPN data and exit")
    main(smoke=ap.parse_args().smoke)
```

- [ ] **Step 5: Run the unit test to verify it passes**

Run: `pytest tests/test_mlb_loader.py -k load_orchestrates -v`
Expected: 1 passed.

- [ ] **Step 6: Run the FULL suite**

Run: `pytest -v`
Expected: all tests pass (NFL 28 + schema/config 15 + `_espn` 6 + MLB loader ~11).

- [ ] **Step 7: Real-data smoke** (hits ESPN; caches to `data/raw/mlb/espn/`; first run is slow)

Run: `python -m src.data.mlb --smoke`
Expected: prints `2020 rows=... crowd_pct max=0.xxx empties=... dropped=0` then `SMOKE OK`. `max` should be well under 0.6 (only the ~11k postseason bubble has any 2020 crowd; the regular season is all empties).

- [ ] **Step 8: Full write** (optional — populates the interim parquet)

Run: `python -m src.data.mlb`
Expected: `wrote data/interim/mlb.parquet rows=... seasons=2018-2023 dropped_missing_attendance=...`

- [ ] **Step 9: Commit** (only if authorized)

```bash
git add src/data/mlb.py config/sports.yaml tests/test_mlb_loader.py
git commit -m "feat: add MLB load/main orchestration + config + smoke"
```

---

## Self-Review

**Spec coverage:**
- Single-source ESPN, no cross-source join → Tasks 3–5. ✔
- `_espn.py` with `fetch_summary`/`walk_scoreboard`/`derive_capacity`/`check_coverage` → Tasks 1–3. ✔
- NFL minimal edit, tests green → Task 1 (alias import), Step 6 full-suite guard. ✔
- Column mapping (game_id prefix, is_playoff==3, is_dome permanent-only, weather null, Elo/rest/travel placeholders, closing_spread null) → Task 4. ✔
- Config `[2018,2023]` / treated `[2020,2021]` → Task 5 Step 1. ✔
- Relocated TOR 2020 → Task 4 `test_blue_jays_2020_relocated_home`. ✔
- neutral_site from ESPN flag → Task 4 `test_neutral_site_from_espn_flag`. ✔
- Preseason/all-star filter + doubleheader unique ids → Task 4 `_select_games` + `test_doubleheader_game_ids_unique`. ✔
- Capacity Option A / capped crowds never used as capacity → Task 1 tests. ✔
- Coverage >5% gate → Task 1 `test_check_coverage_trips_above_5pct`. ✔
- 2020 smoke (empties exist, nothing full, att ≤ cap) → Task 5 Steps 4/7. ✔
- 2020 postseason bubble documented limitation → no code needed (kept in panel; capacity borrows). ✔

**Placeholder scan:** No TBD/TODO/"add error handling" — every code step is complete. ✔

**Type consistency:** `derive_capacity(df, treated_seasons)` keyed `(stadium_id, season)` — MLB passes `venue_id` as `stadium_id` (Task 5 `cap_df`) and looks up `(venue_id, season)` (Task 4). `fetch_summary(sport, event_id)` and `walk_scoreboard(sport, start, end)` signatures match their callers in Task 5. `_select_games`→`_build_panel`→`load` dict keys (`event_id`, `season_year`, `season_type`, `venue_id`, `home_abbr`, `home_score`, `status`, `neutral_site`) are consistent across Tasks 3–5. ✔
