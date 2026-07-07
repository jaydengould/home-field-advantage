"""NFL pilot loader → unified panel. Sport-specific logic lives here only.

Pipeline: nfl_data_py.import_schedules -> join ESPN attendance (cached) ->
derive per-(stadium, season) full-house capacity -> _build_panel -> validate ->
data/interim/nfl.parquet.

Capacity note: ESPN reports ANNOUNCED attendance, which exceeds seated capacity for
most NFL stadiums (units mismatch, not error). So capacity is an EMPIRICAL full-house
reference derived from the same announced series (see _derive_capacity), keeping
crowd_pct = attendance / capacity a clean "fraction of a normal full house" in [0, ~1].
"""
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import yaml

from src.schema import COLUMNS, validate

# derive_capacity/check_coverage now live in _espn.py (shared with MLB/NBA) so all
# sports compute crowd_pct identically. Keep the old private names for local use.
from src.data._espn import derive_capacity as _derive_capacity
from src.data._espn import check_coverage as _check_coverage

RAW_DIR = Path("data/raw/nfl/espn")
INTERIM = Path("data/interim/nfl.parquet")
CONFIG_FILE = Path("config/sports.yaml")
ESPN_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={eid}"

# roof states with no live weather: fixed dome or retractable roof closed for the game.
DOME_ROOFS = frozenset({"dome", "closed"})


def _build_panel(schedule: pd.DataFrame, attendance: dict, capacity: dict,
                 treated_seasons: list) -> pd.DataFrame:
    """Pure transform: schedule + attendance/capacity dicts -> validated panel.

    Assumes `schedule` holds only PLAYED games whose `espn` id is present in
    `attendance` (the load() orchestrator guarantees this). `capacity` is keyed by
    (stadium_id, season) tuples. Raises ValueError if any (stadium_id, season) is
    missing from `capacity`, or if the result fails validate().
    """
    df = schedule.reset_index(drop=True)

    att = df["espn"].astype(str).map(attendance)
    keys = list(zip(df["stadium_id"].astype(str), df["season"].astype(int)))
    missing_cap = sorted({k for k in keys if k not in capacity})
    if missing_cap:
        raise ValueError(f"(stadium_id, season) missing from capacity: {missing_cap}")
    cap = pd.Series([capacity[k] for k in keys], index=df.index)

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


def load(seasons: list, treated_seasons: list):
    """Full pipeline for the given seasons. Returns (validated_panel, dropped_espn_ids).

    Drops unplayed games and games ESPN has no attendance for. Hard-fails if any
    season loses >5% of its played games to missing attendance (ESPN coverage broke).
    """
    import nfl_data_py as nfl  # heavy import — keep out of module load (fast tests)

    sched = nfl.import_schedules(list(seasons))
    played = sched[sched["home_score"].notna() & sched["away_score"].notna()].copy()
    # coverage denominator counts ALL played games, before any drops.
    total = played["season"].astype(int).value_counts().to_dict()

    attendance: dict = {}
    dropped: list = []
    miss = defaultdict(int)

    # espn id is float64 (holds NaNs) -> str() would give "401030693.0" and 400 the URL.
    # null-espn games can't be fetched -> count them as missing, not silent drops.
    for season in played.loc[played["espn"].isna(), "season"]:
        dropped.append("<null-espn>")
        miss[int(season)] += 1
    played = played.dropna(subset=["espn"]).copy()
    played["espn"] = played["espn"].astype("int64").astype(str)

    for eid, season in zip(played["espn"], played["season"]):
        a = _fetch_attendance(eid)
        if a is None:
            dropped.append(eid)
            miss[int(season)] += 1
        else:
            attendance[eid] = int(a)

    _check_coverage(miss, total)

    played = played[played["espn"].isin(attendance)].copy()
    played["attendance"] = played["espn"].map(attendance).astype(int)
    capacity = _derive_capacity(played, treated_seasons)
    panel = _build_panel(played, attendance, capacity, treated_seasons)
    return panel, dropped


def _config_nfl() -> dict:
    return yaml.safe_load(CONFIG_FILE.read_text())["nfl"]


def main(smoke: bool = False) -> None:
    cfg = _config_nfl()
    treated = cfg["treated_seasons"]
    lo, hi = cfg["load_seasons"]
    panel, dropped = load(range(lo, hi + 1), treated)

    if smoke:
        sub = panel[panel["season"] == 2020]
        cols = ["game_id", "home_team", "away_team", "attendance", "capacity", "crowd_pct"]
        print(sub[cols].to_string(index=False))
        print(f"\n2020 rows={len(sub)} total_rows={len(panel)} dropped={len(dropped)}")
        # 2020 was capped: empties exist and nothing is full. A broken join would show
        # ~1.0 everywhere or NaN. Spike reference attendances: 15895 / 10166 / 0 / 0.
        assert (sub["crowd_pct"] == 0).any(), "expected empty-stadium 2020 games"
        assert sub["crowd_pct"].max() < 0.6, "2020 was capped — no full crowds expected"
        assert panel["attendance"].le(panel["capacity"]).all(), "attendance exceeds capacity"
        print("SMOKE OK")
        return

    INTERIM.parent.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(INTERIM)
    print(f"wrote {INTERIM} rows={len(panel)} seasons={lo}-{hi} "
          f"dropped_missing_attendance={len(dropped)}")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true",
                    help="run the 2020 assertions and exit (no parquet write)")
    main(smoke=ap.parse_args().smoke)
