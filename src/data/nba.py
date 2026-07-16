"""NBA loader → unified panel. Single-source from ESPN (schedule/scores via the
scoreboard walk, attendance via the summary endpoint). Sport-specific logic only.

NBA is all-indoor (is_dome=True everywhere, weather null). Two NBA-specific wrinkles
vs. MLB: (1) ESPN labels seasons by END year and the 2019-20 season's play spills
into Aug-Oct 2020, so games are gathered with one continuous scoreboard walk and
filtered by ESPN's season_year rather than MLB's per-year date windows; (2) the 2020
Orlando bubble is flagged via venue+season (ESPN's neutral flag misses it) so
downstream can exclude it from the pooled model while Phase 7 mines it.
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

INTERIM = Path("data/interim/nba.parquet")
CONFIG_FILE = Path("config/sports.yaml")

# ESPN season.type: 2 = regular, 3 = postseason (1 = preseason, 4 = all-star).
PLAYED_TYPES = frozenset({2, 3})
FINAL = "STATUS_FINAL"
# 2020 Orlando bubble venue ("ESPN Wide World of Sports Complex"). ESPN's neutralSite
# flag is False here, so the bubble is detected by venue+season, not that flag.
BUBBLE_VENUE_ID = "4066"
BUBBLE_SEASON = 2020
# TOR played 2020-21 (season 2021) "home" games in Tampa; ESPN neutralSite is False.
RELOCATED = frozenset({("TOR", 2021)})


def _select_games(events: Iterable[dict]) -> list[dict]:
    """Keep only played regular-season + postseason games (drop preseason, all-star,
    postponed/unplayed, and score-less rows)."""
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
    home_win[home_margin < 0] = False   # ties (impossible in NBA) stay <NA>

    season = df["season_year"].astype(int)
    venue_id = df["venue_id"].astype(str)
    is_bubble = ((venue_id == BUBBLE_VENUE_ID) & (season == BUBBLE_SEASON)).to_numpy()
    relocated = [(t, s) in RELOCATED for t, s in zip(df["home_abbr"], season)]

    nan = lambda: pd.Series(np.nan, index=df.index, dtype=float)
    panel = pd.DataFrame({
        "sport": "nba",
        "game_id": "nba_" + df["event_id"].astype(str),
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
        "closing_spread": nan(),          # NBA has spreads, but not in ESPN; Elo controls quality
        "home_rest_days": pd.Series(pd.NA, index=df.index, dtype="Int64"),  # Phase 4
        "away_rest_days": pd.Series(pd.NA, index=df.index, dtype="Int64"),  # Phase 4
        "away_travel_km": nan(),          # Phase 4
        "venue": df["venue_name"].astype(str),
        "is_dome": True,                  # NBA is all-indoor
        "temp_f": nan(),                  # no NBA weather (indoor)
        "wind_mph": nan(),
        "precip": nan(),
        "neutral_site": df["neutral_site"].to_numpy(dtype=bool),
        "relocated_home": np.array(relocated, dtype=bool),
        "is_bubble": is_bubble,
    })

    panel = panel[list(COLUMNS)]
    validate(panel)
    return panel


def _season_window(seasons) -> tuple[dt.date, dt.date]:
    """One continuous calendar range covering every requested (end-year-labeled) NBA
    season: Sept 1 of the year before the earliest season through Nov 30 of the latest
    — captures October openers and the Aug-Oct 2020 bubble tail alike. The walk yields
    each event once (one date per event); the caller filters by ESPN season_year."""
    lo, hi = min(seasons), max(seasons)
    return dt.date(int(lo) - 1, 9, 1), dt.date(int(hi), 11, 30)


def load(seasons, treated_seasons):
    """Full pipeline for the given (end-year) seasons. Returns (validated_panel,
    dropped_ids). One continuous scoreboard walk, filtered to the requested season_year
    set; drops preseason/all-star/unplayed games and games ESPN has no attendance for.
    Hard-fails if any season loses >5% of its played games to missing attendance."""
    seasons = [int(s) for s in seasons]
    wanted = set(seasons)
    start, end = _season_window(seasons)
    games = [g for g in _select_games(walk_scoreboard("nba", start, end))
             if g["season_year"] in wanted]

    total = defaultdict(int)
    for g in games:
        total[int(g["season_year"])] += 1

    attendance: dict = {}
    dropped: list = []
    miss = defaultdict(int)
    for g in games:
        a = fetch_summary("nba", g["event_id"])
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


def _config_nba() -> dict:
    return yaml.safe_load(CONFIG_FILE.read_text())["nba"]


def main(smoke: bool = False) -> None:
    cfg = _config_nba()
    treated = cfg["treated_seasons"]
    lo, hi = cfg["load_seasons"]

    if smoke:
        panel, dropped = load([2020, 2021], treated)
        bubble = panel[panel["is_bubble"]]
        s21 = panel[panel["season"] == 2021]
        print(f"bubble rows={len(bubble)} bubble_crowd_max={bubble['crowd_pct'].max():.3f} "
              f"2021 rows={len(s21)} 2021_crowd_pct min={s21['crowd_pct'].min():.3f} "
              f"max={s21['crowd_pct'].max():.3f} empties={(s21['crowd_pct'] == 0).sum()} "
              f"dropped={len(dropped)}")
        # The 2020 bubble was 100% no-fans; every flagged bubble game is crowd_pct==0.
        assert len(bubble) > 0, "expected 2020 bubble games"
        assert (bubble["crowd_pct"] == 0).all(), "bubble games must be empty (no-fans)"
        # 2021 (2020-21) is the treatment: empty->partial reopening. The robust signal
        # is a dose that is present (some empties) and restricted on average — NOT that
        # no single late-playoff game ever reached a full house.
        assert (s21["crowd_pct"] == 0).any(), "expected some empty 2021 games"
        assert s21["crowd_pct"].mean() < 0.7, "2021 should be restricted on average (staggered reopen)"
        # attendance<=capacity everywhere except the two documented inert artifacts
        # (bubble venue + Tampa relocation, both anchored only in a treated year).
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
