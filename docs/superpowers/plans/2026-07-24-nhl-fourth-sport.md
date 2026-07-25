# NHL Fourth Sport Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add NHL as a fourth sport to the home-field-advantage study — a new ESPN-sourced loader emitting the existing 29-column panel, plus config, downstream wiring, a travel-confound diagnostic, and full regeneration of every result.

**Architecture:** `src/data/nhl.py` mirrors `src/data/nba.py` (continuous scoreboard walk filtered by ESPN `season_year`, attendance via the summary endpoint, Option-A empirical capacity) with four NHL deltas: a 32-team whitelist replacing the All-Star blacklist, a modal-venue rule for `relocated_home`, a date-based `is_bubble`, and a wider season window for the Aug–Sep 2020 bubble tail. Everything downstream is already sport-blind, so integration is four one-word edits plus config.

**Tech Stack:** Python 3.11 (`.venv`), pandas, numpy, pyyaml, requests, linearmodels, matplotlib, pytest.

**Spec:** `docs/superpowers/specs/2026-07-24-nhl-fourth-sport-design.md`

## Global Constraints

- **NEVER run `git commit`, `git add`, `git push`, or `git checkout -b`.** Git is user-owned in this project; the user commits their own history. Where a normal plan would commit, **stop and report for review** instead.
- `data/raw/` is immutable and write-once. Never delete or overwrite cached ESPN JSON.
- Sport-specific logic lives **only** in `src/data/`. Never branch on sport in `src/features/`, `src/models/`, or `src/viz/`.
- Every panel must pass `src.schema.validate()` with **exactly** the 29 columns of `COLUMNS`, in order.
- `crowd_pct == 0` is a REAL value (empty arena), never null. Never coerce it.
- Run tests with `.venv/bin/pytest` from the repo root. Full suite is currently **104 tests, all passing** — it must stay green.
- Elo is a **control variable**. No K-tuning, ever, for any reason.
- NHL `treated_seasons: [2021]`, `load_seasons: [2018, 2023]` — seasons are labeled by **end year**.

---

### Task 1: NHL game selection and panel construction (pure, no network)

**Files:**
- Create: `src/data/nhl.py`
- Modify: `src/data/_espn.py:19`
- Modify: `config/sports.yaml`
- Test: `tests/test_nhl_loader.py`

**Interfaces:**
- Consumes: `src.data._espn.{fetch_summary, walk_scoreboard, derive_capacity, check_coverage}`; `src.schema.{COLUMNS, validate}`
- Produces: `nhl.NHL_TEAMS: frozenset[str]`, `nhl.BUBBLE_SEASON: int`, `nhl.BUBBLE_START: datetime.date`, `nhl._select_games(events: Iterable[dict]) -> list[dict]`, `nhl._build_panel(games: list[dict], attendance: dict, capacity: dict, treated_seasons: list) -> pd.DataFrame`

- [ ] **Step 1: Register the NHL path in the shared ESPN helper**

In `src/data/_espn.py` line 19, change:

```python
SPORT_PATH = {"nfl": "football/nfl", "mlb": "baseball/mlb", "nba": "basketball/nba"}
```

to:

```python
SPORT_PATH = {"nfl": "football/nfl", "mlb": "baseball/mlb",
              "nba": "basketball/nba", "nhl": "hockey/nhl"}
```

Also update the module docstring's first line from `(NFL/MLB/NBA)` to `(NFL/MLB/NBA/NHL)`.

- [ ] **Step 2: Add the NHL config block**

Append to `config/sports.yaml`:

```yaml
nhl:
  load_seasons: [2018, 2023]     # [start, end] inclusive — seasons the loader pulls
  treated_seasons: [2021]        # only 2020-21 (season 2021) is the empty->partial reopening;
                                 # season 2020's pre-March games are full-crowd, and its empty
                                 # games are the Aug-Sep Toronto/Edmonton bubble (is_bubble)
  # 538 NHL Elo (Neil Paine): K=6, home ice 50 Elo pts, retain 70% between seasons.
  # Our ln(|margin|+1) MOV multiplier runs 86-95% of 538's across 1-5 goal margins,
  # so K transfers directly (unlike NBA, which needed halving).
  elo: {k: 6, hfa: 50, carryover: 0.70}
```

- [ ] **Step 3: Write the failing tests**

Create `tests/test_nhl_loader.py`:

```python
import datetime as dt

import pandas as pd
import pytest

from src.data import nhl
from src.data.nhl import _build_panel, _select_games
from src.schema import COLUMNS, validate


def _game(event_id, home="TOR", away="BOS", hs=4, as_=2, season=2019,
          stype=2, venue_id="1838", venue="Scotiabank Arena", neutral=False,
          status="STATUS_FINAL", date="2019-01-15T20:00Z"):
    return {"event_id": event_id, "date": date, "season_year": season,
            "season_type": stype, "home_abbr": home, "away_abbr": away,
            "home_score": hs, "away_score": as_, "venue_id": venue_id,
            "venue_name": venue, "neutral_site": neutral, "status": status}


def test_select_drops_preseason_allstar_and_unplayed():
    events = [
        _game("1", stype=1),                              # preseason -> drop
        _game("2", stype=4),                              # all-star type -> drop
        _game("3", stype=2),                              # regular -> keep
        _game("4", stype=3),                              # postseason -> keep
        _game("5", stype=2, status="STATUS_POSTPONED"),   # postponed -> drop
        _game("6", stype=2, hs=None),                     # missing score -> drop
    ]
    kept = {g["event_id"] for g in _select_games(events)}
    assert kept == {"3", "4"}


def test_select_whitelist_drops_non_franchise_teams():
    # All-Star/exhibition rosters are not real franchises. A whitelist catches them
    # regardless of how ESPN types the game (the NBA/MLB All-Star leak was type=2).
    events = [
        _game("1", home="TOR", away="BOS"),               # real -> keep
        _game("2", home="ATL", away="MET"),               # All-Star divisions -> drop
        _game("3", home="PAC", away="CEN"),               # All-Star divisions -> drop
        _game("4", home="UTAH", away="BOS"),              # post-window franchise -> drop
    ]
    kept = {g["event_id"] for g in _select_games(events)}
    assert kept == {"1"}


def _panel_of(games, treated=(2021,)):
    att = {g["event_id"]: 18000 for g in games}
    cap_df = pd.DataFrame({"stadium_id": [g["venue_id"] for g in games],
                           "season": [g["season_year"] for g in games],
                           "attendance": list(att.values())})
    from src.data._espn import derive_capacity
    cap = derive_capacity(cap_df, list(treated))
    return _build_panel(games, att, cap, list(treated))


def test_build_panel_validates_and_columns_exact():
    panel = _panel_of([_game("1"), _game("2", home="BOS", venue_id="1824")])
    validate(panel)
    assert list(panel.columns) == list(COLUMNS)
    assert (panel["sport"] == "nhl").all()
    assert panel["game_id"].tolist() == ["nhl_1", "nhl_2"]


def test_shootout_game_keeps_espn_final_score():
    # DECISION (spec 4.1): OT/SO games use ESPN's final score unchanged. 538 found
    # "no predictive power in differentiating between one-goal results in regulation
    # versus overtime/shootouts". This test guards that decision against drift.
    panel = _panel_of([_game("1", hs=3, as_=2)])
    row = panel.iloc[0]
    assert row["home_margin"] == 1
    assert bool(row["home_win"]) is True


def test_all_games_indoor_dome_and_weather_null():
    panel = _panel_of([_game("1"), _game("2", venue_id="1824")])
    assert panel["is_dome"].all()
    assert panel[["temp_f", "wind_mph", "precip"]].isna().all().all()


def test_relocated_home_from_modal_venue():
    # TOR plays 3 games at its own arena and 1 at a football stadium (Winter Classic).
    games = [_game("1", home="TOR", venue_id="1838"),
             _game("2", home="TOR", venue_id="1838"),
             _game("3", home="TOR", venue_id="1838"),
             _game("4", home="TOR", venue_id="99999")]   # off-venue -> relocated
    panel = _panel_of(games)
    reloc = dict(zip(panel["game_id"], panel["relocated_home"]))
    assert reloc == {"nhl_1": False, "nhl_2": False, "nhl_3": False, "nhl_4": True}


def test_relocated_home_is_per_team_per_season():
    # A venue change BETWEEN seasons is the new normal, not a relocation.
    games = [_game("1", home="ARI", season=2022, venue_id="1829"),
             _game("2", home="ARI", season=2022, venue_id="1829"),
             _game("3", home="ARI", season=2023, venue_id="7000"),
             _game("4", home="ARI", season=2023, venue_id="7000")]
    panel = _panel_of(games)
    assert not panel["relocated_home"].any()


def test_is_bubble_is_date_based():
    panel = _panel_of([
        _game("1", season=2020, date="2020-08-15T20:00Z", stype=3),   # bubble
        _game("2", season=2020, date="2020-02-15T20:00Z"),            # pre-pause
        _game("3", season=2021, date="2021-05-15T20:00Z"),            # wrong season
    ])
    bub = dict(zip(panel["game_id"], panel["is_bubble"]))
    assert bub == {"nhl_1": True, "nhl_2": False, "nhl_3": False}


def test_covid_era_only_2021():
    panel = _panel_of([_game("1", season=2020), _game("2", season=2021)],
                      treated=(2021,))
    era = dict(zip(panel["game_id"], panel["covid_era"]))
    assert era == {"nhl_1": False, "nhl_2": True}


def test_closing_spread_null_and_phase4_placeholders():
    panel = _panel_of([_game("1")])
    row = panel.iloc[0]
    assert pd.isna(row["closing_spread"])     # puck line is a fixed +/-1.5, no signal
    assert row["home_elo"] == 1500.0 and row["away_elo"] == 1500.0
    assert pd.isna(row["away_travel_km"])
    assert pd.isna(row["home_rest_days"]) and pd.isna(row["away_rest_days"])


def test_empty_arena_crowd_pct_zero_not_null():
    games = [_game("1", venue_id="20", season=2021, hs=1, as_=0),
             _game("2", venue_id="20", season=2021, hs=4, as_=2)]
    att = {"1": 0, "2": 19000}
    cap_df = pd.DataFrame(
        {"stadium_id": ["20", "20", "20"], "season": [2021, 2021, 2019],
         "attendance": [0, 19000, 19000]})
    from src.data._espn import derive_capacity
    cap = derive_capacity(cap_df, [2021])
    panel = _build_panel(games, att, cap, [2021])
    row = panel.set_index("game_id").loc["nhl_1"]
    assert row["crowd_pct"] == 0.0
    assert pd.notna(row["crowd_pct"])


def test_missing_capacity_raises():
    with pytest.raises(ValueError):
        _build_panel([_game("1", venue_id="77", season=2019)],
                     {"1": 18000}, capacity={}, treated_seasons=[2021])


def test_neutral_site_from_espn_flag():
    panel = _panel_of([_game("1", neutral=True), _game("2", neutral=False)])
    assert panel["neutral_site"].tolist() == [True, False]
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_nhl_loader.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.data.nhl'`

- [ ] **Step 5: Implement `src/data/nhl.py` (selection + panel only)**

```python
"""NHL loader → unified panel. Single-source from ESPN (schedule/scores via the
scoreboard walk, attendance via the summary endpoint). Sport-specific logic only.

NHL is all-indoor (is_dome=True everywhere, weather null). Four NHL-specific
deltas vs. the NBA loader:
  1. A 32-team WHITELIST instead of an all-star blacklist — robust to however
     ESPN types exhibition games (the NBA/MLB all-star leak was season_type=2).
  2. relocated_home from a MODAL-VENUE rule — catches Winter Classic / Stadium
     Series / Heritage Classic outdoor games and the NHL Global Series in Europe
     without a hand-maintained list.
  3. is_bubble is DATE-based: every season-2020 game from 2020-08-01 was played
     in the sealed Toronto/Edmonton hubs (1 Aug - 28 Sep 2020).
  4. A wider season window — the 2020 bubble tail runs to late September and the
     2021 season ran January-July.

OT/shootout games keep ESPN's final score unchanged (spec §4.1). 538's NHL Elo
found "no predictive power in differentiating between one-goal results in
regulation versus overtime/shootouts".
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

INTERIM = Path("data/interim/nhl.parquet")
CONFIG_FILE = Path("config/sports.yaml")

# ESPN season.type: 2 = regular, 3 = postseason (1 = preseason, 4 = all-star).
PLAYED_TYPES = frozenset({2, 3})
FINAL = "STATUS_FINAL"

# The 32 franchises active in the 2018-2023 window. ARI (Coyotes) is IN; UTAH is
# NOT (2024 relocation, post-window) — ESPN's teams endpoint lists current teams,
# so do not regenerate this from it. Whitelisting both sides drops All-Star
# division rosters and exhibitions regardless of how ESPN types them.
NHL_TEAMS = frozenset({
    "ANA", "ARI", "BOS", "BUF", "CGY", "CAR", "CHI", "COL", "CBJ", "DAL",
    "DET", "EDM", "FLA", "LA", "MIN", "MTL", "NSH", "NJ", "NYI", "NYR",
    "OTT", "PHI", "PIT", "SJ", "SEA", "STL", "TB", "TOR", "VAN", "VGK",
    "WSH", "WPG",
})

# 2020 Toronto/Edmonton bubble: 1 Aug - 28 Sep 2020, all of season 2020's tail.
BUBBLE_SEASON = 2020
BUBBLE_START = dt.date(2020, 8, 1)


def _select_games(events: Iterable[dict]) -> list[dict]:
    """Keep only played regular-season + postseason games between real franchises
    (drops preseason, all-star, exhibitions, postponed/unplayed, score-less rows)."""
    out = []
    for g in events:
        if g["season_type"] not in PLAYED_TYPES:
            continue
        if g["status"] != FINAL:
            continue
        if g["home_score"] is None or g["away_score"] is None:
            continue
        if g["home_abbr"] not in NHL_TEAMS or g["away_abbr"] not in NHL_TEAMS:
            continue
        out.append(g)
    return out


def _relocated_home(df: pd.DataFrame) -> np.ndarray:
    """True where the home team is NOT at its modal venue for that season.

    Catches outdoor games (Winter Classic / Stadium Series / Heritage Classic),
    the NHL Global Series in Europe, and arena displacements — without a
    hand-maintained list. A between-season venue change (e.g. ARI -> Mullett in
    2023) is the season's new modal venue, so it is correctly NOT flagged.

    NOTE: bubble games are also flagged (the home team really was elsewhere).
    That is correct; they are excluded downstream via neutral_site/is_bubble too.
    """
    venue = df["venue_id"].astype(str)
    season = df["season_year"].astype(int)
    key = pd.MultiIndex.from_arrays([df["home_abbr"].astype(str), season])
    modal = (pd.DataFrame({"team": df["home_abbr"].astype(str), "season": season,
                           "venue": venue})
             .groupby(["team", "season"])["venue"]
             .agg(lambda s: s.value_counts().idxmax()))   # deterministic on ties
    expected = modal.reindex(key).to_numpy()
    return (venue.to_numpy() != expected)


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

    # OT/SO games keep ESPN's final score (spec §4.1) -> margin is never 0 in NHL.
    home_margin = (df["home_score"] - df["away_score"]).astype(int)
    home_win = pd.Series(pd.NA, index=df.index, dtype="boolean")
    home_win[home_margin > 0] = True
    home_win[home_margin < 0] = False

    season = df["season_year"].astype(int)
    date = pd.to_datetime(df["date"]).dt.tz_localize(None)
    is_bubble = ((season == BUBBLE_SEASON)
                 & (date.dt.date >= BUBBLE_START)).to_numpy(dtype=bool)

    nan = lambda: pd.Series(np.nan, index=df.index, dtype=float)
    panel = pd.DataFrame({
        "sport": "nhl",
        "game_id": "nhl_" + df["event_id"].astype(str),
        "season": season,
        "date": date,
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
        "closing_spread": nan(),   # puck line is a fixed +/-1.5 -> no quality signal
        "home_rest_days": pd.Series(pd.NA, index=df.index, dtype="Int64"),  # Phase 4
        "away_rest_days": pd.Series(pd.NA, index=df.index, dtype="Int64"),  # Phase 4
        "away_travel_km": nan(),   # Phase 4
        "venue": df["venue_name"].astype(str),
        "is_dome": True,           # NHL is all-indoor; outdoor games are relocated_home
        "temp_f": nan(),
        "wind_mph": nan(),
        "precip": nan(),
        "neutral_site": df["neutral_site"].to_numpy(dtype=bool),
        "relocated_home": _relocated_home(df),
        "is_bubble": is_bubble,
    })

    panel = panel[list(COLUMNS)]
    validate(panel)
    return panel
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_nhl_loader.py -v`
Expected: **13 passed**

If `test_relocated_home_from_modal_venue` fails with a shape or dtype error, the `modal.reindex(key)` alignment is wrong — verify `modal.index.names == ["team", "season"]` matches the `MultiIndex.from_arrays` order.

- [ ] **Step 7: Stop and report for review**

Do NOT commit. Report: files changed, test counts, and any deviation from the code above.

---

### Task 2: Season window, load orchestration, and smoke check

**Files:**
- Modify: `src/data/nhl.py` (append)
- Test: `tests/test_nhl_loader.py` (append)

**Interfaces:**
- Consumes: `nhl.{_select_games, _build_panel, NHL_TEAMS}` from Task 1
- Produces: `nhl._season_window(seasons) -> tuple[datetime.date, datetime.date]`, `nhl.load(seasons, treated_seasons) -> tuple[pd.DataFrame, list]`, `nhl.main(smoke: bool = False) -> None`

- [ ] **Step 1: Write the failing tests**

First extend the import at the top of `tests/test_nhl_loader.py`:

```python
from src.data.nhl import _build_panel, _select_games, _season_window
```

Then append:

```python
def test_season_window_spans_two_calendar_years_incl_bubble_tail():
    start, end = _season_window([2020, 2021])
    assert start <= dt.date(2019, 10, 2)           # 2019-20 opening night
    assert dt.date(2020, 9, 28) <= end             # 2020 bubble ran to 28 Sep
    assert dt.date(2021, 7, 7) <= end              # 2021 season ran to July


def test_load_single_walk_and_season_filter(monkeypatch):
    captured = {}
    events = [
        _game("1", season=2020, venue_id="1838", hs=4, as_=2),
        _game("2", season=2021, venue_id="1838", hs=1, as_=3),
        _game("9", season=2019, venue_id="1838"),      # not requested -> filtered
    ]

    def fake_walk(sport, start, end):
        captured["sport"], captured["start"], captured["end"] = sport, start, end
        return iter(events)

    monkeypatch.setattr(nhl, "walk_scoreboard", fake_walk)
    monkeypatch.setattr(nhl, "fetch_summary", lambda sport, eid: 18000)
    panel, dropped = nhl.load([2020, 2021], treated_seasons=[2021])
    assert captured["sport"] == "nhl"
    assert captured["start"] <= dt.date(2020, 9, 28) <= captured["end"]
    assert set(panel["season"]) == {2020, 2021}
    assert panel["game_id"].tolist() == ["nhl_1", "nhl_2"]
    assert dropped == []


def test_load_drops_games_missing_attendance(monkeypatch):
    events = [_game("1", season=2021, venue_id="1838"),
              _game("2", season=2021, venue_id="1838")]
    monkeypatch.setattr(nhl, "walk_scoreboard", lambda s, a, b: iter(events))
    monkeypatch.setattr(
        nhl, "fetch_summary", lambda sport, eid: None if eid == "2" else 18000)
    # 1 of 2 missing = 50% > 5% coverage gate -> hard fail
    with pytest.raises(ValueError, match="missing attendance"):
        nhl.load([2021], treated_seasons=[2021])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_nhl_loader.py -v -k "season_window or load_"`
Expected: FAIL — `ImportError: cannot import name '_season_window' from 'src.data.nhl'`

- [ ] **Step 3: Implement the orchestration**

Append to `src/data/nhl.py`:

```python
def _season_window(seasons) -> tuple[dt.date, dt.date]:
    """One continuous calendar range covering every requested (end-year-labeled)
    NHL season: Sept 1 of the year before the earliest season through Sept 30 of
    the latest. The wide tail is required twice over — season 2020's playoffs ran
    to 28 Sep 2020 (the bubble) and season 2021 ran January to July 2021. The walk
    yields each event once; the caller filters by ESPN season_year."""
    lo, hi = min(seasons), max(seasons)
    return dt.date(int(lo) - 1, 9, 1), dt.date(int(hi), 9, 30)


def load(seasons, treated_seasons):
    """Full pipeline for the given (end-year) seasons. Returns (validated_panel,
    dropped_ids). One continuous scoreboard walk, filtered to the requested
    season_year set; drops preseason/all-star/unplayed games and games ESPN has no
    attendance for. Hard-fails if any season loses >5% of its played games."""
    seasons = [int(s) for s in seasons]
    wanted = set(seasons)
    start, end = _season_window(seasons)
    games = [g for g in _select_games(walk_scoreboard("nhl", start, end))
             if g["season_year"] in wanted]

    total = defaultdict(int)
    for g in games:
        total[int(g["season_year"])] += 1

    attendance: dict = {}
    dropped: list = []
    miss = defaultdict(int)
    for g in games:
        a = fetch_summary("nhl", g["event_id"])
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


def _config_nhl() -> dict:
    return yaml.safe_load(CONFIG_FILE.read_text())["nhl"]


def main(smoke: bool = False) -> None:
    cfg = _config_nhl()
    treated = cfg["treated_seasons"]
    lo, hi = cfg["load_seasons"]

    if smoke:
        panel, dropped = load([2020, 2021], treated)
        bubble = panel[panel["is_bubble"]]
        s21 = panel[panel["season"] == 2021]
        so_share = float((panel["home_margin"].abs() == 1).mean())
        print(f"bubble rows={len(bubble)} bubble_crowd_max={bubble['crowd_pct'].max():.3f} "
              f"2021 rows={len(s21)} 2021_crowd_pct min={s21['crowd_pct'].min():.3f} "
              f"max={s21['crowd_pct'].max():.3f} empties={(s21['crowd_pct'] == 0).sum()} "
              f"one_goal_share={so_share:.3f} dropped={len(dropped)}")
        assert len(bubble) > 0, "expected 2020 bubble games"
        assert (bubble["crowd_pct"] == 0).all(), "bubble games must be empty (no-fans)"
        assert (s21["crowd_pct"] == 0).any(), "expected some empty 2021 games"
        assert s21["crowd_pct"].mean() < 0.7, "2021 should be restricted on average"
        clean = panel[~panel["is_bubble"] & ~panel["relocated_home"]]
        assert clean["attendance"].le(clean["capacity"]).all(), "attendance exceeds capacity"
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
                    help="run 2020+2021 assertions on real ESPN data and exit")
    main(smoke=ap.parse_args().smoke)
```

- [ ] **Step 4: Run the full NHL suite**

Run: `.venv/bin/pytest tests/test_nhl_loader.py -v`
Expected: **16 passed** (13 from Task 1 + 3 here)

- [ ] **Step 5: Run the whole suite for regressions**

Run: `.venv/bin/pytest -q`
Expected: **120 passed** (104 existing + 16 new), 0 failed. The `_espn.py` change must not break `tests/test_espn.py`.

- [ ] **Step 6: Stop and report for review**

Do NOT commit.

---

### Task 3: Real-data pull → `data/interim/nhl.parquet`

**Files:**
- Creates (data, gitignored): `data/raw/nhl/espn/**`, `data/interim/nhl.parquet`

**Interfaces:**
- Consumes: `nhl.main` from Task 2
- Produces: `data/interim/nhl.parquet` — the 29-column validated panel for seasons 2018–2023

⚠️ **This task is hours of wall clock**, not minutes: ~7,900 summary fetches plus ~1,500 scoreboard days, against an endpoint that soft-rate-limits bulk pulls. `_cached_get` retries with capped backoff and the cache is write-once, so a pull is self-completing across re-runs. Expect ~8 GB of cache.

- [ ] **Step 1: Smoke against live ESPN first**

Run: `.venv/bin/python -m src.data.nhl --smoke`
Expected: a printed summary line ending `SMOKE OK`.

This pulls only seasons 2020–2021. If it fails, **stop** — do not start the full pull. Likely causes: an ESPN schema change (`gameInfo.attendance` moved), or a bubble game ESPN has no attendance for (should be `0`, not missing).

- [ ] **Step 2: Run the full pull**

Run: `.venv/bin/python -m src.data.nhl`
Expected (final line): `wrote data/interim/nhl.parquet rows=<N> seasons=2018-2023 dropped_missing_attendance=<M>`

If it exits with a `requests` error partway, **re-run the same command** — the cache is write-once, so each re-run resumes where the last stopped.

- [ ] **Step 3: Verify the panel against expectations**

Run:

```bash
.venv/bin/python -c "
import pandas as pd
p = pd.read_parquet('data/interim/nhl.parquet')
print('rows', len(p), 'teams', p.home_team.nunique())
print(p.groupby('season').agg(n=('home_margin','size'), crowd=('crowd_pct','mean')).round(3))
print('bubble', int(p.is_bubble.sum()), 'neutral', int(p.neutral_site.sum()))
print('relocated total', int(p.relocated_home.sum()),
      'relocated excl. bubble', int((p.relocated_home & ~p.is_bubble).sum()))
print('one-goal share', round(float((p.home_margin.abs()==1).mean()), 3))
print('margin==0 rows', int((p.home_margin==0).sum()))
"
```

Expected, and what a deviation means:

| Check | Expected | If not |
|---|---|---|
| `crowd_pct` mean 2021 | **well below** other seasons (the treatment) | the dose signal is broken — stop |
| `crowd_pct` mean 2018/19/22/23 | ~0.9+ | capacity derivation is off |
| season 2020 `n` | fewer than a normal season | correct — it stopped 11 Mar 2020 |
| `margin==0 rows` | **0** | a tie leaked in; NHL has none |
| `relocated excl. bubble` | roughly 20–40 across six seasons | far higher means the modal rule is misfiring |
| `relocated total` | much larger than the above | **correct** — bubble games are legitimately off-venue |
| teams | 32 | 31 means SEA is missing; 33 means UTAH leaked |

⚠️ Do **not** treat a large `relocated total` as a bug. Bubble games are genuinely not at the home team's arena, so the modal rule flags them; they are excluded downstream anyway.

- [ ] **Step 4: Record the measured shootout share**

The spec flags "~10% of games" as an unverified estimate. The one-goal share printed above is an upper bound on it (it includes regulation one-goal wins). Note the actual number in your report so Phase 8 cites a measured figure rather than a recollection.

- [ ] **Step 5: Stop and report for review**

Report the full verification output. Do NOT commit.

---

### Task 4: Venue coordinates and downstream sport-list wiring

**Files:**
- Modify: `config/venue_coords.yaml`
- Modify: `src/features/build.py:156`
- Modify: `src/viz/descriptive.py:17`
- Modify: `src/models/twfe.py:28,32`
- Modify: `src/models/did.py:25`

**Interfaces:**
- Consumes: `data/interim/nhl.parquet` from Task 3
- Produces: `data/processed/nhl.parquet` (feature-complete, validated)

- [ ] **Step 1: Add NHL coordinates**

Append to `config/venue_coords.yaml`. **Era-correct for 2018–2023:** ARI is the Arizona Coyotes (Glendale) — UTAH is a 2024 relocation and must NOT appear. All keys quoted to avoid the YAML "Norway problem" that silently dropped `NO` in Phase 4.

```yaml
nhl:
  "ANA": [33.81, -117.88]   # Honda Center, Anaheim
  "ARI": [33.53, -112.26]   # Gila River Arena, Glendale (Mullett/Tempe 2023 is ~30km — noise)
  "BOS": [42.37, -71.06]    # TD Garden
  "BUF": [42.87, -78.88]    # KeyBank Center
  "CGY": [51.04, -114.05]   # Scotiabank Saddledome
  "CAR": [35.80, -78.72]    # PNC Arena, Raleigh
  "CHI": [41.88, -87.67]    # United Center
  "COL": [39.75, -105.01]   # Ball Arena, Denver
  "CBJ": [39.97, -83.01]    # Nationwide Arena
  "DAL": [32.79, -96.81]    # American Airlines Center
  "DET": [42.34, -83.05]    # Little Caesars Arena
  "EDM": [53.55, -113.50]   # Rogers Place
  "FLA": [26.16, -80.33]    # Amerant Bank Arena, Sunrise
  "LA":  [34.04, -118.27]   # Crypto.com Arena
  "MIN": [44.94, -93.10]    # Xcel Energy Center, St Paul
  "MTL": [45.50, -73.57]    # Bell Centre
  "NSH": [36.16, -86.78]    # Bridgestone Arena
  "NJ":  [40.73, -74.17]    # Prudential Center, Newark
  "NYI": [40.70, -73.75]    # Long Island — Barclays/Nassau/UBS all within ~25km
  "NYR": [40.75, -73.99]    # Madison Square Garden
  "OTT": [45.30, -75.93]    # Canadian Tire Centre
  "PHI": [39.90, -75.17]    # Wells Fargo Center
  "PIT": [40.44, -79.99]    # PPG Paints Arena
  "SJ":  [37.33, -121.90]   # SAP Center
  "SEA": [47.62, -122.35]   # Climate Pledge Arena (season 2022+)
  "STL": [38.63, -90.20]    # Enterprise Center
  "TB":  [27.94, -82.45]    # Amalie Arena
  "TOR": [43.64, -79.38]    # Scotiabank Arena
  "VAN": [49.28, -123.11]   # Rogers Arena
  "VGK": [36.10, -115.18]   # T-Mobile Arena, Las Vegas
  "WSH": [38.90, -77.02]    # Capital One Arena
  "WPG": [49.89, -97.14]    # Canada Life Centre
```

- [ ] **Step 2: Verify coverage before building features**

Run: `.venv/bin/pytest tests/ -q -k coords`
Expected: PASS. `test_coords_cover_every_panel_team` now reads `nhl.parquet` too and fails loudly on any missing or boolean-coerced key.

- [ ] **Step 3: Add `"nhl"` to the four sport lists**

`src/features/build.py:156`:
```python
    for sport in ("nfl", "mlb", "nba", "nhl"):
```

`src/viz/descriptive.py:17`:
```python
SPORTS = ["nfl", "mlb", "nba", "nhl"]
```

`src/models/did.py:25`:
```python
SPORTS = ["nfl", "mlb", "nba", "nhl"]
```

`src/models/twfe.py:28` and `:32`:
```python
SPORTS = ["nfl", "mlb", "nba", "nhl"]
```
```python
# dataviz skill categorical slots 1-4, matches src/viz/descriptive.py
SPORT_COLORS = {"nfl": "#2a78d6", "mlb": "#008300", "nba": "#e87ba4", "nhl": "#e08b00"}
```

`#e08b00` (amber) is the 4th categorical slot: distinguishable from the existing blue/green/pink under both deuteranopia and protanopia, since both figures encode sport by line colour. If `src/viz/descriptive.py` keeps its own colour map, add the identical `nhl` entry there so the two figures stay consistent.

- [ ] **Step 4: Build NHL features**

Run: `.venv/bin/python -m src.features.build`
Expected: four lines, the new one reading `nhl: rows=<N> elo_accuracy=<A> brier=<B>`

⚠️ **Elo accuracy gate:** NHL is expected near **0.57–0.58**, below NFL (0.627) and NBA (0.639), because hockey is the least predictable of the four. **Anything at or above 0.52 is a PASS.** Below 0.52 indicates a real bug (check that Elo state is keyed by `(sport, team)` and NHL params loaded as k=6/hfa=50/carryover=0.70). **Do NOT tune K** — Elo is a control variable and tuning is forbidden by the Phase 4 decision.

- [ ] **Step 5: Confirm the processed panel and travel sanity**

Run:

```bash
.venv/bin/python -c "
import pandas as pd
from src.schema import validate
p = pd.read_parquet('data/processed/nhl.parquet'); validate(p)
t = p.loc[~p.is_bubble & ~p.neutral_site & ~p.relocated_home, 'away_travel_km']
print('rows', len(p), 'travel median', round(float(t.median()),1),
      'max', round(float(t.max()),1))
print('rest null share', round(float(p.home_rest_days.isna().mean()),3))
print('elo range', round(float(p.home_elo.min()),1), round(float(p.home_elo.max()),1))
"
```

Expected: `validate()` raises nothing; travel median in the high hundreds to low thousands of km with a max under ~5,000 (Vancouver–Florida is the continental extreme); rest-null share small (first game of each team-season); Elo spread roughly 1350–1650.

- [ ] **Step 6: Run the full suite**

Run: `.venv/bin/pytest -q`
Expected: **120 passed**, 0 failed.

- [ ] **Step 7: Stop and report for review**

Report the Elo accuracy number explicitly. Do NOT commit.

---

### Task 5: NHL travel-confound diagnostic

**Files:**
- Modify: `src/models/twfe.py` — `fit()` signature (`:61`, `:73`) **and** `main()` (after the NFL sensitivity block at `:150-157`)
- Test: `tests/test_twfe.py` (append)

**Interfaces:**
- Consumes: `twfe.fit(panel, outcome, sample="pooled", treated_seasons=None, extra_controls=())`
- Produces: `twfe.fit(..., drop_controls=())` — one new keyword argument, the symmetric counterpart to the existing `extra_controls`; plus a printed diagnostic and two rows in `results/tables/twfe_nhl_travel_diagnostic.csv`

**Why a parameter and not a module-global swap:** `fit()` reads the module-level
`CONTROLS` at call time, so temporarily rebinding that global would also work. A
parameter is preferred because `extra_controls` already exists and does the exact
mirror-image job — `drop_controls` completes an established idea rather than
introducing mutable module state that a reader of `fit()`'s signature cannot see.

**Why:** the 2020–21 NHL season ran realigned regional divisions (including an all-Canadian division), so crowds and travel fell together. This measures the confound instead of assuming `away_travel_km` handles it. **Per spec §2.4 both outcomes are reported** — small movement means the confound is empirically minor; large movement means NHL's estimate is not separable from the travel shock.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_twfe.py`:

```python
def test_drop_controls_removes_only_the_named_control():
    # The NHL travel diagnostic refits dropping away_travel_km. In _synth, travel is
    # independent noise, so dropping it must NOT move the planted beta=3.0 much.
    # Also pins the property the diagnostic depends on: dropping a control must not
    # silently change the estimation sample (see below).
    import src.models.twfe as twfe

    panel = _synth(beta=3.0)
    base = twfe.fit(panel, "home_margin", "pooled", [2020, 2021])
    reduced = twfe.fit(panel, "home_margin", "pooled", [2020, 2021],
                       drop_controls=["away_travel_km"])

    assert "coef_away_travel_km" in base                 # present in the full spec
    assert "coef_away_travel_km" not in reduced          # genuinely dropped
    assert "coef_elo_diff" in reduced                    # other controls survive
    assert twfe.CONTROLS == ["crowd_pct", "elo_diff", "rest_diff", "away_travel_km"]
    assert abs(reduced["coef"] - base["coef"]) < 0.5     # independent control -> small move


def test_drop_controls_does_not_change_the_estimation_sample():
    # A dropped control also leaves the dropna() column set, so it COULD enlarge the
    # sample — which would let a sample shift masquerade as a coefficient shift and
    # silently invalidate the diagnostic. Verified zero for nfl/mlb/nba on real data
    # (away_travel_km is NaN only on neutral/relocated games, which _exclusion_mask
    # already drops). This locks that property in.
    panel = _synth(beta=3.0)
    base = fit(panel, "home_margin", "pooled", [2020, 2021])
    reduced = fit(panel, "home_margin", "pooled", [2020, 2021],
                  drop_controls=["away_travel_km"])
    assert reduced["n_obs"] == base["n_obs"]
```

Note `_synth` is the existing fixture in this file (`tests/test_twfe.py:8`); it already supplies `away_travel_km` with real variance, and treated seasons are 2020/2021. `fit` is already imported at the top of that file.

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/pytest tests/test_twfe.py -v -k drop_controls`
Expected: FAIL — `TypeError: fit() got an unexpected keyword argument 'drop_controls'`

- [ ] **Step 3: Add the `drop_controls` parameter to `fit()`**

In `src/models/twfe.py`, change the signature at line 61:

```python
def fit(panel, outcome, sample="pooled", treated_seasons=None, extra_controls=(),
        drop_controls=()):
```

and the control assembly at line 73:

```python
    controls = [c for c in CONTROLS if c not in drop_controls] + list(extra_controls)
```

Extend the docstring with one line:

```
    drop_controls removes named controls from the default set (the symmetric
    counterpart to extra_controls); used by the NHL travel-confound diagnostic.
```

Change nothing else in `fit()`. With `drop_controls=()` — the default — behaviour is
byte-identical to before, so all existing callers and results are unaffected.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_twfe.py -v`
Expected: all PASS (6 existing + 2 new = 8).

- [ ] **Step 5: Implement the diagnostic**

In `src/models/twfe.py`, inside `main()`, immediately after the NFL sensitivity `print(...)` at line ~157, insert:

```python
    # NHL-only diagnostic: the 2020-21 season ran realigned regional divisions
    # (incl. an all-Canadian division), so crowd and travel fell together. Measure
    # the confound rather than assume away_travel_km absorbs it. Reported either way.
    nhl = _prep(panels["nhl"])
    treated_nhl = cfg["nhl"]["treated_seasons"]
    t = nhl[nhl["season"].isin(treated_nhl)][["crowd_pct", "away_travel_km"]].dropna()
    rho = float(t["crowd_pct"].corr(t["away_travel_km"])) if len(t) > 2 else float("nan")

    diag_rows = []
    for outcome in ["home_margin", "home_win"]:
        base = next(r for r in rows if r["sport"] == "nhl"
                    and r["outcome"] == outcome and r["sample"] == "pooled")
        drop = fit(panels["nhl"], outcome, "pooled", treated_nhl,
                   drop_controls=["away_travel_km"])
        diag_rows.append({
            "outcome": outcome,
            "corr_crowd_travel_treated": rho,
            "coef_with_travel": base["coef"],
            "coef_without_travel": drop["coef"],
            "delta": drop["coef"] - base["coef"],
            # n_obs for BOTH fits: dropping a control also drops it from dropna(), so
            # an unequal sample would let a sample shift masquerade as a coef shift.
            # These must match; if they do not, the diagnostic is not interpretable.
            "n_obs_with_travel": base["n_obs"],
            "n_obs_without_travel": drop["n_obs"],
        })
        print(f"[NHL travel diagnostic] {outcome}: corr(crowd,travel|treated)={rho:+.3f} "
              f"coef {base['coef']:+.3f} -> {drop['coef']:+.3f} "
              f"(delta {drop['coef'] - base['coef']:+.3f}) "
              f"n {base['n_obs']} -> {drop['n_obs']}")
        if base["n_obs"] != drop["n_obs"]:
            print("  ⚠️  sample changed when dropping travel — coef delta is NOT a "
                  "clean control effect; investigate before interpreting")
    pd.DataFrame(diag_rows).to_csv(
        "results/tables/twfe_nhl_travel_diagnostic.csv", index=False)
```

⚠️ This must go **after** `results` is built and **after** `Path("results/tables").mkdir(...)` at line ~142, since it writes into that directory and reads `rows`.

- [ ] **Step 6: Confirm the full suite**

Run: `.venv/bin/pytest -q`
Expected: **122 passed** (104 existing + 16 loader + 2 diagnostic), 0 failed.

Note `main()` is not exercised by the suite; the diagnostic block itself runs for the first time in Task 6. Do not run `python -m src.models.twfe` here — Task 6 owns the regeneration.

- [ ] **Step 7: Stop and report for review**

Do NOT commit.

---

### Task 6: Regenerate all results and update CLAUDE.md

**Files:**
- Regenerates: `results/tables/*.csv`, `results/figures/*.png`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: `data/processed/{nfl,mlb,nba,nhl}.parquet`, the wiring from Task 4, the diagnostic from Task 5

⚠️ **NHL is not additive — it invalidates the existing results.** Every cross-sport table, both figures, and the pooled estimate change.

- [ ] **Step 1: Regenerate descriptive HFA**

Run: `.venv/bin/python -m src.viz.descriptive`
Expected: writes `results/tables/descriptive_hfa.csv` and `results/figures/hfa_by_season.png`, printing a per-sport gate line including a new `nhl` row.

Record NHL's pooled full-crowd win% and margin, and whether its treated season (2021) dips below the pooled baseline. Existing baselines for comparison: nfl win .552 / margin 1.75, mlb .528 / 0.04, nba .570 / 2.26.

- [ ] **Step 2: Regenerate the TWFE estimates**

Run: `.venv/bin/python -m src.models.twfe`
Expected: `twfe_{nfl,mlb,nba,nhl}.csv`, `twfe_cross_sport.csv`, `twfe_nhl_travel_diagnostic.csv`, `twfe_crowd_effect.png`, plus the NFL sensitivity line and the two NHL travel-diagnostic lines.

- [ ] **Step 3: Regenerate the DiD estimates**

Run: `.venv/bin/python -m src.models.did`
Expected: `did_{nfl,mlb,nba,nhl}.csv`, `did_cross_sport.csv`, `did_hfa_shrink.png`.

- [ ] **Step 4: Check coherence between the two estimators**

Run:

```bash
.venv/bin/python -c "
import pandas as pd
t = pd.read_csv('results/tables/twfe_nhl.csv'); d = pd.read_csv('results/tables/did_nhl.csv')
print(t[['outcome','sample','coef','ci_low','ci_high','pvalue','n_obs']].to_string(index=False))
print(d[['outcome','sample','crowd_effect','ci_low','ci_high','pvalue','n_obs']].to_string(index=False))
"
```

Expected: 6a and 6b agree in **sign** and land within roughly 10–25% of each other, as they do for NFL and NBA (DiD slightly larger is normal — raw vs Elo/rest/travel-adjusted). A sign flip between them is a red flag worth reporting, not smoothing over.

⚠️ **Wide, zero-crossing CIs are the expected result, not a failure.** Per spec §2, NHL is reported regardless of sign, magnitude, or significance. Do not drop it, re-specify it, or tune it if the estimate is null.

- [ ] **Step 5: Confirm the full suite is still green**

Run: `.venv/bin/pytest -q`
Expected: **122 passed** (104 existing + 16 loader + 2 diagnostic), 0 failed.

- [ ] **Step 6: Update CLAUDE.md**

Add a session section following the existing per-phase format. It must record:
- NHL added as a 4th sport; spec and plan paths.
- The settled decisions: final scores unchanged for OT/SO (with the 538 "no predictive power" quote as justification); `treated_seasons: [2021]`; modal-venue `relocated_home`; whitelist over blacklist; Elo k=6/hfa=50/carryover=0.70 with the 1505→1500 deviation noted.
- **Measured** numbers from this build: row count, per-season `crowd_pct` means, Elo accuracy, the one-goal share, and the new four-sport headline estimates.
- The travel-diagnostic result and what it implies.
- The §2 pre-commitments, so a future session cannot quietly drop NHL.
- Update the **Status** section: NHL complete, Phase 7 cancelled (bubble → Phase 8 subsection), Phase 8 is next.
- Remove the now-obsolete "Maybe-later: Add NHL as a 4th sport" block, since it is done.

- [ ] **Step 7: Stop and report for review**

Report every headline number produced. Do NOT commit — the user commits their own history.

---

## Notes for the executing agent

**What is genuinely new here** (everything else is a mirror of `src/data/nba.py`):
1. `_relocated_home` modal-venue rule — the only novel logic.
2. `NHL_TEAMS` whitelist replacing the all-star blacklist.
3. Date-based `is_bubble`.
4. The widened `_season_window` tail.
5. The `drop_controls=()` parameter on `twfe.fit()` (symmetric counterpart to the existing `extra_controls`) and the travel diagnostic in `twfe.main()` that uses it. The diagnostic records `n_obs` for both fits because a dropped control also leaves the `dropna()` column set — an unequal sample would let a sample shift masquerade as a coefficient shift. Measured as zero for nfl/mlb/nba on real data; the check exists so NHL is verified rather than assumed.

**Traps that have already bitten this project:**
- All-Star games typed `season_type=2` (leaked into MLB and NBA, forced a parquet regen). The whitelist in Task 1 is the fix.
- YAML bare `NO` parsing as boolean `false` (dropped New Orleans coords). All NHL keys are quoted.
- ESPN ids needing clean string conversion — `walk_scoreboard` already returns `str(ev["id"])`, so no float-suffix bug here.
- Reading a subagent report before it returns clean DONE.
