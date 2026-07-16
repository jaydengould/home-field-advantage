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
# ponytail: ESPN types the All-Star game as season_type=2 (regular season), so
# the PLAYED_TYPES filter can't catch it. These abbrevs are the only non-franchise
# "teams" in the 2018-2023 window. Exclusion set (window is fixed) beats a 30-team
# allowlist.
ALLSTAR_ABBRS = frozenset({"AL", "NL"})


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
        if g["home_abbr"] in ALLSTAR_ABBRS or g["away_abbr"] in ALLSTAR_ABBRS:
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
        reg = sub[~sub["is_playoff"]]
        print(f"2020 rows={len(sub)} reg={len(reg)} reg_crowd_pct max={reg['crowd_pct'].max():.3f} "
              f"empties={(sub['crowd_pct'] == 0).sum()} dropped={len(dropped)}")
        # The dose signal: 2020 REGULAR season was 100% no-fans, so every regular game
        # must be crowd_pct==0. We assert on regular season only because this 2-season
        # smoke window ([2019,2020]) can't anchor a venue that first opened in a treated
        # year: Globe Life Field (2020 postseason bubble) has no non-treated season here,
        # so Option A falls back to its own max -> crowd_pct~1.0. That is a smoke-window
        # artifact, NOT a loader bug — the full [2018,2023] pull anchors it on 2022/23.
        # Those bubble games are postseason + neutral_site anyway (excluded downstream).
        assert (reg["crowd_pct"] == 0).all(), "2020 regular season must be 100% empty (no-fans)"
        assert len(reg) > 0, "expected 2020 regular-season games"
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
