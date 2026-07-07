"""Shared ESPN data-access helpers for the per-sport loaders (NFL/MLB/NBA).

Single source of truth for the sport-blind capacity/coverage math so every sport
computes crowd_pct the same way, plus the cached ESPN fetch + scoreboard walk used
by the ESPN-sourced loaders (MLB, NBA; NFL keeps its own fetch).
"""
from __future__ import annotations

import datetime as dt
import json
import random
import time
from pathlib import Path
from typing import Iterator

import requests

_RAW_ROOT = Path("data/raw")
SPORT_PATH = {"nfl": "football/nfl", "mlb": "baseball/mlb", "nba": "basketball/nba"}
_SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/{path}/summary?event={eid}"
_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/{path}/scoreboard?dates={d}"

_MAX_RETRIES = 6
_RETRYABLE = (requests.ConnectionError, requests.Timeout)


def _espn_dir(sport: str) -> Path:
    return _RAW_ROOT / sport / "espn"


def _cached_get(cache: Path, url: str, throttle: float = 0.7) -> dict:
    """GET `url` as JSON, cached write-once to `cache`. Retries transient failures
    (HTTP 5xx, connection errors, timeouts) with capped exponential backoff + jitter —
    ESPN soft-rate-limits sustained bulk pulls, so a short retry window is not enough.
    A cache hit never touches the network; 4xx and persistent 5xx still raise."""
    if cache.exists():
        return json.loads(cache.read_text())
    resp = None
    for attempt in range(_MAX_RETRIES):
        try:
            resp = requests.get(url, timeout=30)
            if resp.status_code < 500:
                break
        except _RETRYABLE:
            if attempt == _MAX_RETRIES - 1:
                raise
        if attempt < _MAX_RETRIES - 1:
            time.sleep(min(2 ** attempt, 30) + random.uniform(0, 1))  # backoff + jitter
    resp.raise_for_status()        # final 5xx or any 4xx still raises
    data = resp.json()
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(data))
    time.sleep(throttle)
    return data


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


def fetch_summary(sport: str, event_id: str, throttle: float = 0.7) -> int | None:
    """Attendance for one game via the ESPN summary endpoint, cached (write-once)
    to data/raw/<sport>/espn/<event_id>.json. Returns None if ESPN has no
    attendance field. `event_id` must already be a clean string id."""
    cache = _espn_dir(sport) / f"{event_id}.json"
    url = _SUMMARY_URL.format(path=SPORT_PATH[sport], eid=event_id)
    try:
        data = _cached_get(cache, url, throttle)
    except requests.RequestException:
        # game summary temporarily unavailable (transient ESPN 5xx that outlasted
        # retries) -> treat as missing attendance; the loader's >5% coverage gate
        # guards against systemic loss.
        return None
    return data.get("gameInfo", {}).get("attendance")


def _to_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _fetch_scoreboard(sport: str, day: dt.date, throttle: float = 0.7) -> dict:
    cache = _espn_dir(sport) / "scoreboard" / f"{day:%Y%m%d}.json"
    url = _SCOREBOARD_URL.format(path=SPORT_PATH[sport], d=f"{day:%Y%m%d}")
    return _cached_get(cache, url, throttle)


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
