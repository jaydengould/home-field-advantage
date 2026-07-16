import datetime as dt

import pandas as pd
import pytest

from src.data import nba
from src.data.nba import _build_panel, _select_games, _season_window, BUBBLE_VENUE_ID
from src.schema import COLUMNS, validate


def _game(event_id, home="LAL", away="BOS", hs=110, as_=100, season=2019,
          stype=2, venue_id="10", venue="Crypto.com Arena", neutral=False,
          status="STATUS_FINAL", date="2019-01-15T20:00Z"):
    return {"event_id": event_id, "date": date, "season_year": season,
            "season_type": stype, "home_abbr": home, "away_abbr": away,
            "home_score": hs, "away_score": as_, "venue_id": venue_id,
            "venue_name": venue, "neutral_site": neutral, "status": status}


def test_select_drops_preseason_allstar_and_unplayed():
    events = [
        _game("1", stype=1),                              # preseason -> drop
        _game("2", stype=4),                              # all-star -> drop
        _game("3", stype=2),                              # regular -> keep
        _game("4", stype=3),                              # postseason -> keep
        _game("5", stype=2, status="STATUS_POSTPONED"),   # postponed -> drop
        _game("6", stype=2, hs=None),                     # missing score -> drop
    ]
    kept = {g["event_id"] for g in _select_games(events)}
    assert kept == {"3", "4"}


def test_select_drops_allstar_and_rising_stars():
    events = [
        _game("1", stype=2),                              # regular -> keep
        _game("2", home="LEB", away="DUR", stype=2),      # All-Star -> drop
        _game("3", home="USA", away="WORLD", stype=2),    # Rising Stars -> drop
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
    panel = _panel_of([_game("1"), _game("2", home="GSW", venue_id="11")])
    validate(panel)
    assert list(panel.columns) == list(COLUMNS)
    assert (panel["sport"] == "nba").all()
    assert panel["game_id"].tolist() == ["nba_1", "nba_2"]


def test_home_margin_and_win():
    panel = _panel_of([_game("1", hs=110, as_=100), _game("2", hs=95, as_=101)])
    assert panel["home_margin"].tolist() == [10, -6]
    assert panel["home_win"].tolist() == [True, False]


def test_is_playoff_from_season_type():
    panel = _panel_of([_game("1", stype=2), _game("2", stype=3)])
    assert panel["is_playoff"].tolist() == [False, True]


def test_all_games_indoor_dome_and_weather_null():
    panel = _panel_of([_game("1", venue_id="10"), _game("2", venue_id="11")])
    assert panel["is_dome"].all()
    assert panel[["temp_f", "wind_mph", "precip"]].isna().all().all()


def test_is_bubble_venue_and_season():
    panel = _panel_of([
        _game("1", venue_id=BUBBLE_VENUE_ID, season=2020),   # bubble
        _game("2", venue_id=BUBBLE_VENUE_ID, season=2021),   # not 2020 -> not bubble
        _game("3", venue_id="10", season=2020),              # not bubble venue
    ], treated=(2021,))
    bub = dict(zip(panel["game_id"], panel["is_bubble"]))
    assert bub == {"nba_1": True, "nba_2": False, "nba_3": False}


def test_bubble_playoff_game_is_both_flags():
    panel = _panel_of([_game("1", venue_id=BUBBLE_VENUE_ID, season=2020, stype=3)])
    row = panel.iloc[0]
    assert bool(row["is_bubble"]) is True
    assert bool(row["is_playoff"]) is True


def test_toronto_2021_relocated_home():
    panel = _panel_of([
        _game("1", home="TOR", season=2021, venue_id="1396"),  # Tampa relocation
        _game("2", home="TOR", season=2019, venue_id="12"),    # normal Toronto
        _game("3", home="LAL", season=2021, venue_id="10"),    # other team
    ], treated=(2021,))
    reloc = dict(zip(panel["game_id"], panel["relocated_home"]))
    assert reloc == {"nba_1": True, "nba_2": False, "nba_3": False}


def test_covid_era_only_2021():
    panel = _panel_of([_game("1", season=2020), _game("2", season=2021)],
                      treated=(2021,))
    era = dict(zip(panel["game_id"], panel["covid_era"]))
    assert era == {"nba_1": False, "nba_2": True}


def test_game_ids_unique_and_prefixed():
    panel = _panel_of([_game("100"), _game("101")])
    assert panel["game_id"].is_unique
    assert panel["game_id"].str.startswith("nba_").all()


def test_neutral_site_from_espn_flag():
    panel = _panel_of([_game("1", neutral=True), _game("2", neutral=False)])
    assert panel["neutral_site"].tolist() == [True, False]


def test_crowd_pct_and_placeholders():
    panel = _panel_of([_game("1")])
    row = panel.iloc[0]
    assert row["crowd_pct"] == 1.0            # 18000/18000
    assert row["home_elo"] == 1500.0 and row["away_elo"] == 1500.0
    assert pd.isna(row["closing_spread"]) and pd.isna(row["away_travel_km"])
    assert pd.isna(row["home_rest_days"]) and pd.isna(row["temp_f"])


def test_empty_arena_crowd_pct_zero_not_null():
    # attendance=0 -> crowd_pct 0.0 (REAL value), never NaN. Capacity from the same
    # venue-season's full-house game (19000).
    games = [_game("1", venue_id="20", season=2021, hs=1, as_=0),
             _game("2", venue_id="20", season=2021, hs=110, as_=95)]
    att = {"1": 0, "2": 19000}
    cap_df = pd.DataFrame({"stadium_id": ["20", "20"], "season": [2021, 2021],
                           "attendance": [0, 19000]})
    from src.data._espn import derive_capacity
    # 2021 is treated -> borrows non-treated; give a 2019 full house to anchor it.
    cap_df = pd.concat([cap_df, pd.DataFrame(
        {"stadium_id": ["20"], "season": [2019], "attendance": [19000]})])
    cap = derive_capacity(cap_df, [2021])
    panel = _build_panel(games, att, cap, [2021])
    row = panel.set_index("game_id").loc["nba_1"]
    assert row["crowd_pct"] == 0.0
    assert pd.notna(row["crowd_pct"])


def test_missing_capacity_raises():
    game = _game("1", venue_id="77", season=2019)
    with pytest.raises(ValueError):
        _build_panel([game], {"1": 18000}, capacity={}, treated_seasons=[2021])


def test_season_window_spans_two_calendar_years_incl_bubble_tail():
    start, end = _season_window([2020, 2021])
    # prior-year autumn openers through the final year's late (bubble) tail
    assert start <= dt.date(2019, 10, 22)          # 2019-20 opening night
    assert dt.date(2020, 8, 1) <= end              # Aug-2020 bubble is inside
    assert dt.date(2021, 6, 30) <= end


def test_load_single_walk_and_season_filter(monkeypatch):
    captured = {}
    events = [
        _game("1", season=2020, venue_id="10", hs=110, as_=100),
        _game("2", season=2021, venue_id="10", hs=95, as_=101),
        _game("9", season=2019, venue_id="10"),      # not requested -> filtered
    ]

    def fake_walk(sport, start, end):
        captured["sport"], captured["start"], captured["end"] = sport, start, end
        return iter(events)

    monkeypatch.setattr(nba, "walk_scoreboard", fake_walk)
    monkeypatch.setattr(nba, "fetch_summary", lambda sport, eid: 18000)
    panel, dropped = nba.load([2020, 2021], treated_seasons=[2021])
    assert captured["sport"] == "nba"
    assert captured["start"] <= dt.date(2020, 8, 1) <= captured["end"]   # one continuous walk
    assert set(panel["season"]) == {2020, 2021}                         # 2019 filtered
    assert panel["game_id"].tolist() == ["nba_1", "nba_2"]
    assert dropped == []
