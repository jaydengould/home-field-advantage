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


def add_rest(panel: pd.DataFrame) -> pd.DataFrame:
    df = panel.copy()
    day = df["date"].dt.normalize()

    # Long form: one entry per (team, side) with a stable pointer back to the row.
    long = pd.concat([
        pd.DataFrame({"row": df.index, "side": "home", "sport": df["sport"],
                      "team": df["home_team"], "season": df["season"], "day": day}),
        pd.DataFrame({"row": df.index, "side": "away", "sport": df["sport"],
                      "team": df["away_team"], "season": df["season"], "day": day}),
    ], ignore_index=True)

    long = long.sort_values(["sport", "team", "season", "day", "row"])
    prev = long.groupby(["sport", "team", "season"])["day"].shift(1)
    rest = (long["day"] - prev).dt.days
    long["rest"] = rest.astype("Int64")  # NA where prev is NaT (first game of season)

    home = long[long["side"] == "home"].set_index("row")["rest"]
    away = long[long["side"] == "away"].set_index("row")["rest"]
    df["home_rest_days"] = home.reindex(df.index).astype("Int64")
    df["away_rest_days"] = away.reindex(df.index).astype("Int64")
    return df


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


def elo_accuracy(panel: pd.DataFrame, hfa: float) -> tuple[float, float]:
    """Accuracy of the pre-game Elo expectation, including HFA (matches add_elo)."""
    exp = 1.0 / (1.0 + 10 ** (-((panel["home_elo"] + hfa) - panel["away_elo"]) / 400.0))
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
