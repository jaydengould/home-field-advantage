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
