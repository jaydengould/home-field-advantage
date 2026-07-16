# Phase 4 — Sport-blind Features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Populate the panel's team-quality (`home_elo`/`away_elo`), rest (`home_rest_days`/`away_rest_days`), and travel (`away_travel_km`) columns with one sport-blind module, writing model-ready panels to `data/processed/`.

**Architecture:** A single sport-blind module `src/features/build.py` with three pure transforms — `add_elo`, `add_rest`, `add_travel` — each operating on the unified 29-column schema. `build(sport)` reads `data/interim/{sport}.parquet`, applies the three, re-validates, and writes `data/processed/{sport}.parquet`. Elo params come from `config/sports.yaml`; travel coords from a new static `config/venue_coords.yaml`. A prerequisite loader fix (Task 1) removes All-Star exhibition rows the ESPN `season_type` filter missed.

**Tech Stack:** Python 3.11, pandas, numpy, pyyaml, pytest. No new dependencies (haversine hand-rolled; stdlib `math`/numpy suffices).

## Global Constraints

- **Schema is law:** every panel written to disk MUST pass `src.schema.validate()` unchanged. Do not alter `src/schema.py`.
- **Nullable dtypes:** `home_rest_days`/`away_rest_days` are `Int64` (pandas nullable); `away_travel_km` is `float64` (NaN allowed). `home_elo`/`away_elo` are non-null `float64`.
- **`data/raw/` is immutable.** Features read `data/interim/`, write `data/processed/`. Never touch raw.
- **Sport is a parameter.** No sport-specific branching in `src/features/`. Sport-specific logic (Task 1's All-Star sets) lives only in `src/data/`.
- **Git is user-owned.** Do NOT run `git commit`/`push`/`branch`. The "Commit" steps below are for the user; agents stop at a clean, tested working tree and leave committing to the human.
- **Run Python via `.venv/bin/python`** (`python` is not on PATH). Tests: `.venv/bin/python -m pytest`.
- **Elo mean = 1500.0** (single constant, all sports). **Store PRE-game ratings** in `home_elo`/`away_elo`; HFA applies only inside the win-probability expectation.

---

### Task 1: Remove All-Star exhibition rows from MLB & NBA loaders

ESPN types All-Star games as `season_type=2` (regular season), so the existing `{2,3}` filter in `_select_games` lets them through. They carry fake team abbreviations (MLB `AL`/`NL`; NBA `DUR`/`GIA`/`LEB`/`STE`/`USA`/`WORLD`), have no home city, and pollute the panel (one 2018 MLB row is even `neutral_site=False`). Drop them at the loader. NFL is clean — no change.

**Files:**
- Modify: `src/data/mlb.py` (`_select_games` + a module constant)
- Modify: `src/data/nba.py` (`_select_games` + a module constant)
- Test: `tests/test_mlb_loader.py`, `tests/test_nba_loader.py`
- Regenerate: `data/interim/mlb.parquet`, `data/interim/nba.parquet`

**Interfaces:**
- Consumes: existing `_select_games(events) -> list[dict]` in each loader; event dicts have `home_abbr`/`away_abbr`.
- Produces: same signature, now excluding All-Star rows. Downstream `_build_panel` unchanged.

- [ ] **Step 1: Write the failing MLB test**

In `tests/test_mlb_loader.py`, add:

```python
def test_select_drops_allstar_game():
    events = [
        _game("1", stype=2),                          # regular -> keep
        _game("2", home="AL", away="NL", stype=2),    # All-Star -> drop
        _game("3", home="NL", away="AL", stype=2),    # All-Star -> drop
    ]
    kept = {g["event_id"] for g in _select_games(events)}
    assert kept == {"1"}
```

- [ ] **Step 2: Run it, verify it fails**

Run: `.venv/bin/python -m pytest tests/test_mlb_loader.py::test_select_drops_allstar_game -v`
Expected: FAIL (kept == {"1","2","3"}).

- [ ] **Step 3: Implement the MLB filter**

In `src/data/mlb.py`, near the other module constants (below `PERMANENT_DOME_VENUE_IDS`):

```python
# ponytail: ESPN types the All-Star game as season_type=2 (regular season), so
# the PLAYED_TYPES filter can't catch it. These abbrevs are the only non-franchise
# "teams" in the 2018-2023 window. Exclusion set (window is fixed) beats a 30-team
# allowlist.
ALLSTAR_ABBRS = frozenset({"AL", "NL"})
```

In `_select_games`, add the guard inside the loop (after the score-null check):

```python
        if g["home_abbr"] in ALLSTAR_ABBRS or g["away_abbr"] in ALLSTAR_ABBRS:
            continue
```

- [ ] **Step 4: Run it, verify it passes**

Run: `.venv/bin/python -m pytest tests/test_mlb_loader.py -v`
Expected: PASS (all MLB loader tests).

- [ ] **Step 5: Write the failing NBA test**

In `tests/test_nba_loader.py`, add (match that file's `_game` helper signature — check its top for the exact kwargs; `home`/`away` are the abbrev fields):

```python
def test_select_drops_allstar_and_rising_stars():
    events = [
        _game("1", stype=2),                              # regular -> keep
        _game("2", home="LEB", away="DUR", stype=2),      # All-Star -> drop
        _game("3", home="USA", away="WORLD", stype=2),    # Rising Stars -> drop
    ]
    kept = {g["event_id"] for g in _select_games(events)}
    assert kept == {"1"}
```

- [ ] **Step 6: Run it, verify it fails**

Run: `.venv/bin/python -m pytest tests/test_nba_loader.py::test_select_drops_allstar_and_rising_stars -v`
Expected: FAIL.

- [ ] **Step 7: Implement the NBA filter**

In `src/data/nba.py`, near the other module constants:

```python
# ponytail: All-Star + Rising Stars "teams" (ESPN types them season_type=2). Only
# non-franchise abbrevs in the 2018-2023 window.
ALLSTAR_ABBRS = frozenset({"DUR", "GIA", "LEB", "STE", "USA", "WORLD"})
```

In NBA's `_select_games`, add the same guard inside the loop (after its existing keep/skip checks, using that file's field names for the abbrevs):

```python
        if g["home_abbr"] in ALLSTAR_ABBRS or g["away_abbr"] in ALLSTAR_ABBRS:
            continue
```

- [ ] **Step 8: Run it, verify it passes**

Run: `.venv/bin/python -m pytest tests/test_nba_loader.py -v`
Expected: PASS.

- [ ] **Step 9: Regenerate the two interim parquets (cache-warm, no re-fetch)**

Run:
```bash
.venv/bin/python -m src.data.mlb
.venv/bin/python -m src.data.nba
```
Expected: MLB writes ~13272 rows (13277 − 5), NBA ~7562 rows (7571 − 9). Both print `wrote data/interim/<sport>.parquet ...`.

- [ ] **Step 10: Verify the fake teams are gone**

Run:
```bash
.venv/bin/python -c "import pandas as pd; \
d=pd.read_parquet('data/interim/mlb.parquet'); \
print('mlb bad', d[d.home_team.isin(['AL','NL'])|d.away_team.isin(['AL','NL'])].shape[0]); \
d=pd.read_parquet('data/interim/nba.parquet'); \
bad={'DUR','GIA','LEB','STE','USA','WORLD'}; \
print('nba bad', d[d.home_team.isin(bad)|d.away_team.isin(bad)].shape[0])"
```
Expected: `mlb bad 0` and `nba bad 0`.

- [ ] **Step 11: Commit** (user)

```bash
git add src/data/mlb.py src/data/nba.py tests/test_mlb_loader.py tests/test_nba_loader.py
git commit -m "fix(data): exclude All-Star exhibition games from MLB/NBA loaders"
```

---

### Task 2: Travel feature — `venue_coords.yaml` + `add_travel`

**Files:**
- Create: `config/venue_coords.yaml`
- Create: `src/features/build.py` (module skeleton + `_haversine_km`, `load_coords`, `add_travel`)
- Test: `tests/test_features.py`

**Interfaces:**
- Produces:
  - `load_coords(path="config/venue_coords.yaml") -> dict[tuple[str, str], tuple[float, float]]` — keyed `(sport, team) -> (lat, lon)`.
  - `_haversine_km(lat1, lon1, lat2, lon2) -> float`.
  - `add_travel(panel: pd.DataFrame, coords: dict) -> pd.DataFrame` — returns a copy with `away_travel_km` populated: `is_bubble` → 0.0; `neutral_site` or `relocated_home` → NaN; else haversine(away city, home city). Raises `ValueError` listing any missing `(sport, team)` keys needed for a non-excluded row.

- [ ] **Step 1: Create `config/venue_coords.yaml`**

City-level metro coordinates, keyed by sport then team abbrev. These match the exact abbreviations in the interim panels (verified against the parquets; NFL keeps both `OAK` and `LV` for the Raiders relocation).

```yaml
# (sport, team) -> home-city (stadium) lat/lon. City-level is the correct
# resolution for travel fatigue (100s-1000s km); intra-city venue offset is noise.
# Keyed by (sport, team) because abbreviations collide across sports (WAS/WSH,
# NY/NYY...). Coords are ERA-CORRECT for the 2018-2023 load window (verified
# against Wikipedia stadium lists 2026-07-15): NFL/MLB OAK = Oakland Coliseum
# (Raiders->LV is a separate abbrev; A's->Sacramento is 2025, post-window); NBA
# LAC = downtown Crypto.com Arena (Intuit Dome is 2024+). Do NOT "update" these to
# the newer arenas Wikipedia now lists.
nfl:
  ARI: [33.53, -112.26]
  ATL: [33.75, -84.40]
  BAL: [39.28, -76.62]
  BUF: [42.77, -78.79]
  CAR: [35.23, -80.85]
  CHI: [41.86, -87.62]
  CIN: [39.10, -84.52]
  CLE: [41.51, -81.70]
  DAL: [32.75, -97.09]
  DEN: [39.74, -105.02]
  DET: [42.34, -83.05]
  GB:  [44.50, -88.06]
  HOU: [29.68, -95.41]
  IND: [39.76, -86.16]
  JAX: [30.32, -81.64]
  KC:  [39.05, -94.48]
  LA:  [33.95, -118.34]   # SoFi Stadium, Inglewood (shared with LAC)
  LAC: [33.95, -118.34]   # SoFi Stadium, Inglewood
  LV:  [36.09, -115.18]   # Allegiant Stadium, Paradise NV
  MIA: [25.96, -80.24]
  MIN: [44.97, -93.26]
  NE:  [42.09, -71.26]
  "NO": [29.95, -90.08]   # quoted: bare NO is YAML boolean false (Norway problem)
  NYG: [40.81, -74.07]
  NYJ: [40.81, -74.07]
  OAK: [37.75, -122.20]
  PHI: [39.90, -75.17]
  PIT: [40.45, -80.02]
  SEA: [47.59, -122.33]
  SF:  [37.40, -121.97]
  TB:  [27.98, -82.50]
  TEN: [36.17, -86.77]
  WAS: [38.91, -76.86]
mlb:
  ARI: [33.45, -112.07]
  ATL: [33.89, -84.47]
  BAL: [39.28, -76.62]
  BOS: [42.35, -71.10]
  CHC: [41.95, -87.66]
  CHW: [41.83, -87.63]
  CIN: [39.10, -84.51]
  CLE: [41.50, -81.69]
  COL: [39.76, -104.99]
  DET: [42.34, -83.05]
  HOU: [29.76, -95.36]
  KC:  [39.05, -94.48]
  LAA: [33.80, -117.88]
  LAD: [34.07, -118.24]
  MIA: [25.78, -80.22]
  MIL: [43.03, -87.97]
  MIN: [44.98, -93.28]
  NYM: [40.76, -73.85]
  NYY: [40.83, -73.93]
  OAK: [37.75, -122.20]
  PHI: [39.91, -75.17]
  PIT: [40.45, -80.01]
  SD:  [32.71, -117.16]
  SEA: [47.59, -122.33]
  SF:  [37.78, -122.39]
  STL: [38.62, -90.19]
  TB:  [27.77, -82.65]
  TEX: [32.75, -97.08]
  TOR: [43.64, -79.39]
  WSH: [38.87, -77.01]
nba:
  ATL: [33.76, -84.40]
  BKN: [40.68, -73.98]
  BOS: [42.37, -71.06]
  CHA: [35.23, -80.84]
  CHI: [41.88, -87.67]
  CLE: [41.50, -81.69]
  DAL: [32.79, -96.81]
  DEN: [39.75, -105.01]
  DET: [42.34, -83.06]
  GS:  [37.77, -122.39]
  HOU: [29.75, -95.36]
  IND: [39.76, -86.16]
  LAC: [34.04, -118.27]
  LAL: [34.04, -118.27]
  MEM: [35.14, -90.05]
  MIA: [25.78, -80.19]
  MIL: [43.04, -87.92]
  MIN: [44.98, -93.28]
  "NO": [29.95, -90.08]   # quoted: bare NO is YAML boolean false (Norway problem)
  NY:  [40.75, -73.99]
  OKC: [35.46, -97.52]
  ORL: [28.54, -81.38]
  PHI: [39.90, -75.17]
  PHX: [33.45, -112.07]
  POR: [45.53, -122.67]
  SA:  [29.43, -98.44]
  SAC: [38.58, -121.50]
  TOR: [43.64, -79.38]
  UTAH: [40.77, -111.90]
  WSH: [38.90, -77.02]
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_features.py`:

```python
import numpy as np
import pandas as pd
import pytest

from src.features.build import _haversine_km, load_coords, add_travel
from src.schema import COLUMNS


def _row(**kw):
    """Minimal schema-complete row; override fields via kwargs."""
    base = {c: None for c in COLUMNS}
    base.update(dict(
        sport="nba", game_id="x", season=2019, date=pd.Timestamp("2019-01-01"),
        is_playoff=False, home_team="BOS", away_team="LAL",
        home_score=100, away_score=90, home_margin=10, home_win=True,
        attendance=1, capacity=1, crowd_pct=1.0, covid_era=False,
        home_elo=1500.0, away_elo=1500.0, closing_spread=np.nan,
        home_rest_days=pd.NA, away_rest_days=pd.NA, away_travel_km=np.nan,
        venue="v", is_dome=True, temp_f=np.nan, wind_mph=np.nan, precip=np.nan,
        neutral_site=False, relocated_home=False, is_bubble=False,
    ))
    base.update(kw)
    return base


def test_haversine_known_distance():
    # NYC -> LA is ~3940 km; allow 2% slack for city-center choice.
    km = _haversine_km(40.71, -74.01, 34.05, -118.24)
    assert 3860 < km < 4020


def test_haversine_symmetric():
    a = _haversine_km(40.71, -74.01, 34.05, -118.24)
    b = _haversine_km(34.05, -118.24, 40.71, -74.01)
    assert a == pytest.approx(b)


def test_travel_normal_game_positive():
    coords = {("nba", "BOS"): (42.37, -71.06), ("nba", "LAL"): (34.04, -118.27)}
    out = add_travel(pd.DataFrame([_row()]), coords)
    assert out["away_travel_km"].iloc[0] == pytest.approx(4150, rel=0.03)


def test_travel_bubble_is_zero():
    coords = {}  # bubble path must not need coords
    out = add_travel(pd.DataFrame([_row(is_bubble=True)]), coords)
    assert out["away_travel_km"].iloc[0] == 0.0


def test_travel_neutral_and_relocated_are_null():
    coords = {}
    out = add_travel(pd.DataFrame([
        _row(neutral_site=True), _row(relocated_home=True),
    ]), coords)
    assert out["away_travel_km"].isna().all()


def test_travel_missing_coords_raises():
    with pytest.raises(ValueError, match="missing"):
        add_travel(pd.DataFrame([_row()]), coords={})


def test_load_coords_shape():
    coords = load_coords()
    assert coords[("nfl", "OAK")] != coords[("nfl", "LV")]  # relocation kept distinct
    assert isinstance(coords[("mlb", "NYY")], tuple)
```

- [ ] **Step 3: Run it, verify it fails**

Run: `.venv/bin/python -m pytest tests/test_features.py -v`
Expected: FAIL with `ModuleNotFoundError: src.features.build`.

- [ ] **Step 4: Implement `src/features/build.py` (travel portion)**

```python
"""Sport-blind feature building: Elo, rest, travel on the unified panel.

Reads data/interim/{sport}.parquet, populates the placeholder feature columns,
re-validates against the schema, writes data/processed/{sport}.parquet. The sport
is a parameter — no sport-specific branching here (that lives in src/data/).
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from src.schema import COLUMNS, validate

INTERIM = Path("data/interim")
PROCESSED = Path("data/processed")
CONFIG_FILE = Path("config/sports.yaml")
COORDS_FILE = Path("config/venue_coords.yaml")
ELO_MEAN = 1500.0


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def load_coords(path: Path | str = COORDS_FILE) -> dict:
    raw = yaml.safe_load(Path(path).read_text())
    return {(sport, team): (float(ll[0]), float(ll[1]))
            for sport, teams in raw.items() for team, ll in teams.items()}


def add_travel(panel: pd.DataFrame, coords: dict) -> pd.DataFrame:
    df = panel.copy()
    # Excluded rows never need coords: bubble -> 0 (everyone lived in Orlando),
    # neutral/relocated -> NaN (away team didn't fly to the home city).
    excluded = df["neutral_site"].to_numpy(bool) | df["relocated_home"].to_numpy(bool)
    bubble = df["is_bubble"].to_numpy(bool)
    normal = ~excluded & ~bubble

    need = df.loc[normal, ["sport", "home_team", "away_team"]]
    keys = set(zip(need["sport"], need["home_team"])) | set(zip(need["sport"], need["away_team"]))
    missing = sorted(k for k in keys if k not in coords)
    if missing:
        raise ValueError(f"venue_coords missing (sport, team): {missing}")

    km = np.full(len(df), np.nan)
    for i in np.flatnonzero(normal):
        s = df["sport"].iat[i]
        h = coords[(s, df["home_team"].iat[i])]
        a = coords[(s, df["away_team"].iat[i])]
        km[i] = _haversine_km(a[0], a[1], h[0], h[1])
    km[bubble] = 0.0
    df["away_travel_km"] = km
    return df
```

- [ ] **Step 5: Run it, verify it passes**

Run: `.venv/bin/python -m pytest tests/test_features.py -v`
Expected: PASS (all 7 tests).

- [ ] **Step 6: Commit** (user)

```bash
git add config/venue_coords.yaml src/features/build.py tests/test_features.py
git commit -m "feat(features): add_travel + venue coords (sport-blind)"
```

---

### Task 3: Rest feature — `add_rest`

Days since each team's previous game **within the same season**; first game of a season → null. Uses whole-day differences (normalize timestamps).

**Files:**
- Modify: `src/features/build.py` (add `add_rest`)
- Test: `tests/test_features.py`

**Interfaces:**
- Produces: `add_rest(panel: pd.DataFrame) -> pd.DataFrame` — copy with `home_rest_days`/`away_rest_days` filled (`Int64`; `pd.NA` for each team's first game of a season).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_features.py`:

```python
from src.features.build import add_rest


def test_rest_first_game_of_season_is_null():
    rows = [
        _row(sport="nba", game_id="g1", season=2019, date=pd.Timestamp("2019-01-01"),
             home_team="BOS", away_team="LAL"),
        _row(sport="nba", game_id="g2", season=2019, date=pd.Timestamp("2019-01-04"),
             home_team="LAL", away_team="BOS"),
    ]
    out = add_rest(pd.DataFrame(rows)).sort_values("game_id").reset_index(drop=True)
    # g1: both teams' first game of the season -> NA/NA
    assert pd.isna(out.loc[0, "home_rest_days"]) and pd.isna(out.loc[0, "away_rest_days"])
    # g2: both played g1 three days earlier
    assert out.loc[1, "home_rest_days"] == 3 and out.loc[1, "away_rest_days"] == 3


def test_rest_resets_across_seasons():
    rows = [
        _row(sport="nba", game_id="a", season=2019, date=pd.Timestamp("2019-04-01"),
             home_team="BOS", away_team="LAL"),
        _row(sport="nba", game_id="b", season=2020, date=pd.Timestamp("2019-10-25"),
             home_team="BOS", away_team="LAL"),
    ]
    out = add_rest(pd.DataFrame(rows)).sort_values("game_id").reset_index(drop=True)
    # 'b' is the first 2020 game for both teams -> NA despite a prior 2019 game
    assert pd.isna(out.loc[1, "home_rest_days"]) and pd.isna(out.loc[1, "away_rest_days"])


def test_rest_dtype_is_int64():
    out = add_rest(pd.DataFrame([_row()]))
    assert out["home_rest_days"].dtype == "Int64"
```

- [ ] **Step 2: Run it, verify it fails**

Run: `.venv/bin/python -m pytest tests/test_features.py -k rest -v`
Expected: FAIL (`add_rest` not defined).

- [ ] **Step 3: Implement `add_rest`**

Add to `src/features/build.py`:

```python
def add_rest(panel: pd.DataFrame) -> pd.DataFrame:
    df = panel.copy()
    day = df["date"].dt.normalize()

    # Long form: one entry per (team, side) with a stable pointer back to the row.
    long = pd.concat([
        pd.DataFrame({"row": df.index, "side": "home",
                      "team": df["home_team"], "season": df["season"], "day": day}),
        pd.DataFrame({"row": df.index, "side": "away",
                      "team": df["away_team"], "season": df["season"], "day": day}),
    ], ignore_index=True)

    long = long.sort_values(["team", "season", "day", "row"])
    prev = long.groupby(["team", "season"])["day"].shift(1)
    rest = (long["day"] - prev).dt.days
    long["rest"] = rest.astype("Int64")  # NA where prev is NaT (first game of season)

    home = long[long["side"] == "home"].set_index("row")["rest"]
    away = long[long["side"] == "away"].set_index("row")["rest"]
    df["home_rest_days"] = home.reindex(df.index).astype("Int64")
    df["away_rest_days"] = away.reindex(df.index).astype("Int64")
    return df
```

- [ ] **Step 4: Run it, verify it passes**

Run: `.venv/bin/python -m pytest tests/test_features.py -k rest -v`
Expected: PASS.

- [ ] **Step 5: Commit** (user)

```bash
git add src/features/build.py tests/test_features.py
git commit -m "feat(features): add_rest (days since prior game, per season)"
```

---

### Task 4: Elo feature — config block + `add_elo`

**Files:**
- Modify: `config/sports.yaml` (add `elo:` block to nfl/mlb/nba)
- Modify: `src/features/build.py` (add `add_elo`, `_elo_params`)
- Test: `tests/test_features.py`, `tests/test_config.py`

**Interfaces:**
- Consumes: `config/sports.yaml` `<sport>.elo.{k,hfa,carryover}`.
- Produces:
  - `_elo_params(sport: str) -> dict` — `{"k":float,"hfa":float,"carryover":float}`.
  - `add_elo(panel: pd.DataFrame, params: dict) -> pd.DataFrame` — copy with PRE-game `home_elo`/`away_elo` filled. Processes rows in `(date, game_id)` order; each team starts at 1500 on first appearance; between seasons `new = carryover*old + (1-carryover)*1500`; MOV multiplier `ln(|home_margin|+1)`; HFA applied only inside the expectation. Returns rows in the panel's original order.

- [ ] **Step 1: Add the Elo config block**

In `config/sports.yaml`, add under each sport (values are 538-grounded; `k` is the gate-calibrated scale param per the spec):

```yaml
# nfl:
  elo: {k: 20, hfa: 48, carryover: 0.667}
# mlb:
  elo: {k: 4, hfa: 24, carryover: 0.667}
# nba:
  elo: {k: 10, hfa: 100, carryover: 0.75}
```

(Place each `elo:` line as a child of its existing sport key, matching indentation.)

- [ ] **Step 2: Write the failing config test**

Add to `tests/test_config.py`:

```python
def test_elo_params_present_for_all_sports():
    import yaml
    from pathlib import Path
    cfg = yaml.safe_load(Path("config/sports.yaml").read_text())
    for sport in ("nfl", "mlb", "nba"):
        elo = cfg[sport]["elo"]
        assert {"k", "hfa", "carryover"} <= set(elo)
        assert 0.0 < elo["carryover"] <= 1.0
```

- [ ] **Step 3: Write the failing Elo behavior tests**

Add to `tests/test_features.py`:

```python
from src.features.build import add_elo, _elo_params


def _elo_row(gid, date, home, away, hs, as_, season=2019, sport="nba"):
    return _row(sport=sport, game_id=gid, date=pd.Timestamp(date), season=season,
                home_team=home, away_team=away, home_score=hs, away_score=as_,
                home_margin=hs - as_, home_win=(hs > as_))


def test_elo_pregame_ratings_start_at_1500():
    out = add_elo(pd.DataFrame([_elo_row("g1", "2019-01-01", "BOS", "LAL", 110, 100)]),
                  {"k": 20, "hfa": 0, "carryover": 0.75})
    assert out["home_elo"].iloc[0] == 1500.0 and out["away_elo"].iloc[0] == 1500.0


def test_elo_winner_gains_rating_next_game():
    # BOS beats LAL in g1; in g2 (BOS home again vs NYK) BOS's pre-game elo > 1500.
    rows = [
        _elo_row("g1", "2019-01-01", "BOS", "LAL", 110, 100),
        _elo_row("g2", "2019-01-03", "BOS", "NY", 100, 99),
    ]
    out = add_elo(pd.DataFrame(rows), {"k": 20, "hfa": 0, "carryover": 0.75})
    out = out.sort_values("game_id").reset_index(drop=True)
    assert out.loc[1, "home_elo"] > 1500.0  # BOS carried its g1 win forward


def test_elo_is_pregame_not_contaminated():
    # A team's stored elo for a game must NOT include that game's own result.
    row = _elo_row("g1", "2019-01-01", "BOS", "LAL", 150, 50)  # blowout
    out = add_elo(pd.DataFrame([row]), {"k": 20, "hfa": 0, "carryover": 0.75})
    assert out["home_elo"].iloc[0] == 1500.0  # pre-game, blowout not yet applied


def test_elo_preserves_row_order():
    rows = [
        _elo_row("g2", "2019-01-03", "BOS", "NY", 100, 99),
        _elo_row("g1", "2019-01-01", "BOS", "LAL", 110, 100),
    ]
    out = add_elo(pd.DataFrame(rows), {"k": 20, "hfa": 0, "carryover": 0.75})
    assert list(out["game_id"]) == ["g2", "g1"]  # original order preserved
```

- [ ] **Step 4: Run them, verify they fail**

Run: `.venv/bin/python -m pytest tests/test_features.py -k elo tests/test_config.py -v`
Expected: FAIL (`add_elo`/`_elo_params` not defined; config missing `elo`).

- [ ] **Step 5: Implement `add_elo` + `_elo_params`**

Add to `src/features/build.py`:

```python
def _elo_params(sport: str) -> dict:
    return yaml.safe_load(CONFIG_FILE.read_text())[sport]["elo"]


def add_elo(panel: pd.DataFrame, params: dict) -> pd.DataFrame:
    df = panel.copy()
    k, hfa, carry = float(params["k"]), float(params["hfa"]), float(params["carryover"])

    order = df.sort_values(["date", "game_id"]).index
    # Rating state keyed by (sport, team): team abbreviations collide across sports
    # (SF = 49ers/Giants, etc.), so on a combined cross-sport panel a team-only key
    # would conflate two franchises. Sport-safe even though build() runs per-sport.
    rating: dict[tuple, float] = {}
    last_season: dict[tuple, int] = {}
    home_pre = pd.Series(np.nan, index=df.index)
    away_pre = pd.Series(np.nan, index=df.index)

    for i in order:
        season = int(df.at[i, "season"])
        sp = df.at[i, "sport"]
        h, a = (sp, df.at[i, "home_team"]), (sp, df.at[i, "away_team"])
        for t in (h, a):
            if t not in rating:
                rating[t] = ELO_MEAN
                last_season[t] = season
            elif season != last_season[t]:
                rating[t] = carry * rating[t] + (1 - carry) * ELO_MEAN
                last_season[t] = season

        eh, ea = rating[h], rating[a]
        home_pre[i], away_pre[i] = eh, ea

        exp_home = 1.0 / (1.0 + 10 ** (-((eh + hfa) - ea) / 400.0))
        margin = int(df.at[i, "home_margin"])
        s = 1.0 if margin > 0 else (0.0 if margin < 0 else 0.5)
        delta = k * math.log(abs(margin) + 1) * (s - exp_home)
        rating[h] = eh + delta
        rating[a] = ea - delta

    df["home_elo"] = home_pre.astype(float)
    df["away_elo"] = away_pre.astype(float)
    return df
```

- [ ] **Step 6: Run them, verify they pass**

Run: `.venv/bin/python -m pytest tests/test_features.py -k elo tests/test_config.py -v`
Expected: PASS.

- [ ] **Step 7: Commit** (user)

```bash
git add config/sports.yaml src/features/build.py tests/test_features.py tests/test_config.py
git commit -m "feat(features): add_elo (538-grounded params, pre-game ratings)"
```

---

### Task 5: Pipeline `build()`/`main()` + processed parquets + Elo accuracy gate

Ties the three transforms together, writes `data/processed/`, and runs the sanity gate (schema validation + per-sport Elo accuracy/Brier vs benchmarks) on real data.

**Files:**
- Modify: `src/features/build.py` (add `build`, `elo_accuracy`, `main`)
- Test: `tests/test_features.py`

**Interfaces:**
- Consumes: `add_travel`, `add_rest`, `add_elo`, `load_coords`, `_elo_params`.
- Produces:
  - `build(sport: str) -> pd.DataFrame` — read interim → add_travel/add_rest/add_elo → `validate()` → write `data/processed/{sport}.parquet` → return panel.
  - `elo_accuracy(panel) -> tuple[float, float]` — `(accuracy, brier)` from the recomputed pre-game expectation incl. HFA (decided games only; ties excluded from accuracy).
  - `main()` — loop `("nfl","mlb","nba")`, build each, print rows + accuracy/Brier.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_features.py`:

```python
from src.features.build import build, elo_accuracy


def test_elo_accuracy_reasonable_on_synthetic():
    # Strong home team always wins big -> higher-elo side wins -> accuracy high.
    rows, elo = [], None
    for n in range(20):
        rows.append(_elo_row(f"g{n:02d}", f"2019-02-{n+1:02d}", "BOS", "LAL", 120, 100))
    out = add_elo(pd.DataFrame(rows), {"k": 20, "hfa": 100, "carryover": 0.75})
    acc, brier = elo_accuracy(out)
    assert acc > 0.8 and 0.0 <= brier <= 0.25


def test_build_writes_processed_and_validates(tmp_path, monkeypatch):
    # Smoke on real interim data for one sport; validate() must pass and file appears.
    import src.features.build as b
    panel = b.build("nfl")
    from src.schema import validate
    validate(panel)  # raises if bad
    assert (b.PROCESSED / "nfl.parquet").exists()
    assert panel["home_elo"].notna().all() and panel["away_elo"].notna().all()
    assert panel["away_travel_km"].notna().any()
```

- [ ] **Step 2: Run them, verify they fail**

Run: `.venv/bin/python -m pytest tests/test_features.py -k "accuracy or build" -v`
Expected: FAIL (`build`/`elo_accuracy` not defined).

- [ ] **Step 3: Implement `build`, `elo_accuracy`, `main`**

Add to `src/features/build.py`:

```python
def elo_accuracy(panel: pd.DataFrame, hfa: float) -> tuple[float, float]:
    # Include HFA so the gate scores the SAME expectation add_elo built ratings on
    # (spec gate #2: "higher pre-game Elo (incl. HFA) won").
    exp = 1.0 / (1.0 + 10 ** (-(((panel["home_elo"] + hfa) - panel["away_elo"]) / 400.0)))
    decided = panel["home_margin"] != 0
    y = (panel["home_margin"] > 0).astype(float)
    acc = float(((exp > 0.5) == (y == 1.0))[decided].mean())
    brier = float(((exp - y) ** 2)[decided].mean())
    return acc, brier


def build(sport: str) -> pd.DataFrame:
    panel = pd.read_parquet(INTERIM / f"{sport}.parquet")
    panel = add_travel(panel, load_coords())
    panel = add_rest(panel)
    panel = add_elo(panel, _elo_params(sport))
    panel = panel[list(COLUMNS)]
    validate(panel)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(PROCESSED / f"{sport}.parquet")
    return panel


def main() -> None:
    for sport in ("nfl", "mlb", "nba"):
        panel = build(sport)
        acc, brier = elo_accuracy(panel, _elo_params(sport)["hfa"])
        print(f"{sport}: rows={len(panel)} elo_accuracy={acc:.3f} brier={brier:.3f}")


if __name__ == "__main__":
    main()
```

Note: `elo_accuracy` includes HFA in its expectation so the gate scores the same
win-probability `add_elo` used to build the ratings (spec gate #2). Omitting it
would understate accuracy — sharply for high-HFA sports (NBA hfa=100) — and read
below the benchmark band even when the engine is fine.

- [ ] **Step 4: Run them, verify they pass**

Run: `.venv/bin/python -m pytest tests/test_features.py -k "accuracy or build" -v`
Expected: PASS.

- [ ] **Step 5: Run the full build + accuracy gate on real data**

Run: `.venv/bin/python -m src.features.build`
Expected: three lines. Accuracy bands (bug gate, NOT tuning targets): NFL ≈ 0.60–0.66, NBA ≈ 0.62–0.68, MLB ≈ 0.53–0.58. A sport near 0.50 signals an engine bug — investigate before proceeding. If NBA lands hot/cold, `k` (currently 10) is the scale knob.

- [ ] **Step 6: Ordinal sanity check**

Run:
```bash
.venv/bin/python -c "import pandas as pd; \
d=pd.read_parquet('data/processed/nba.parquet'); \
d=d[d.season==2019]; last=d.sort_values('date').groupby('home_team').tail(1); \
print(last.nlargest(5,'home_elo')[['home_team','home_elo']].to_string(index=False))"
```
Expected: strong 2018-19 teams (e.g. MIL, GS, TOR) near the top — "good teams rate higher."

- [ ] **Step 7: Full test suite green**

Run: `.venv/bin/python -m pytest -q`
Expected: all tests pass (prior loader/schema/espn suites + new feature suite).

- [ ] **Step 8: Commit** (user)

```bash
git add src/features/build.py tests/test_features.py
git commit -m "feat(features): build pipeline + Elo accuracy gate -> data/processed"
```

---

## Self-Review notes

- **Spec coverage:** IO/module shape → Tasks 2–5; Elo middle + params → Task 4; pre-game storage → Task 4 test `test_elo_is_pregame_not_contaminated`; rest first-game null → Task 3; travel bubble=0 / neutral+relocated=null → Task 2; sanity gate (validate + accuracy/Brier + ordinal) → Task 5. The All-Star exclusion (surfaced during planning) → Task 1.
- **Constant HFA / don't-bake-rest-travel:** enforced by construction — `add_elo` uses a single config `hfa` and never reads rest/travel; rest/travel are separate columns.
- **Types:** `add_*` all take/return `pd.DataFrame`; `load_coords`→dict; `_elo_params`→dict; `elo_accuracy`→(float,float). Consistent across tasks.
- **Known deferral:** `elo_accuracy` omits the HFA nudge in its expectation (documented in Task 5 Step 3) — acceptable for a bug-detection gate.
