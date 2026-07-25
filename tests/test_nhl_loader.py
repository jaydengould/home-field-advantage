import datetime as dt

import pandas as pd
import pytest

from src.data import nhl
from src.data.nhl import _build_panel, _select_games, _season_window
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


def test_final_score_used_verbatim_no_ot_shootout_adjustment():
    # Guard: NHL margins come straight from ESPN's final score. If anyone later adds
    # shootout-zeroing or regulation-time logic, this test must fail first.
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
