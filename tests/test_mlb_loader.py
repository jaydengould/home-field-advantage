import pandas as pd
import pytest
from src.data.mlb import _select_games, _build_panel
from src.schema import validate, COLUMNS


def _game(event_id, home="NYY", away="BOS", hs=5, as_=3, season=2019,
          stype=2, venue_id="10", venue="Yankee Stadium", neutral=False,
          status="STATUS_FINAL", date="2019-06-15T20:00Z"):
    return {"event_id": event_id, "date": date, "season_year": season,
            "season_type": stype, "home_abbr": home, "away_abbr": away,
            "home_score": hs, "away_score": as_, "venue_id": venue_id,
            "venue_name": venue, "neutral_site": neutral, "status": status}


def test_select_drops_preseason_allstar_and_unplayed():
    events = [
        _game("1", stype=1),                         # spring training -> drop
        _game("2", stype=4),                         # all-star -> drop
        _game("3", stype=2),                         # regular -> keep
        _game("4", stype=3),                         # postseason -> keep
        _game("5", stype=2, status="STATUS_SCHEDULED"),  # unplayed -> drop
        _game("6", stype=2, hs=None),                # missing score -> drop
    ]
    kept = {g["event_id"] for g in _select_games(events)}
    assert kept == {"3", "4"}


def _panel_of(games, treated=(2020, 2021)):
    att = {g["event_id"]: 40000 for g in games}
    cap_df = pd.DataFrame({"stadium_id": [g["venue_id"] for g in games],
                           "season": [g["season_year"] for g in games],
                           "attendance": list(att.values())})
    from src.data._espn import derive_capacity
    cap = derive_capacity(cap_df, list(treated))
    return _build_panel(games, att, cap, list(treated))


def test_build_panel_validates_and_columns_exact():
    panel = _panel_of([_game("1"), _game("2", home="LAD", venue_id="11")])
    validate(panel)
    assert list(panel.columns) == list(COLUMNS)
    assert (panel["sport"] == "mlb").all()
    assert panel["game_id"].tolist() == ["mlb_1", "mlb_2"]


def test_home_margin_and_win():
    panel = _panel_of([_game("1", hs=5, as_=3), _game("2", hs=2, as_=6)])
    assert panel["home_margin"].tolist() == [2, -4]
    assert panel["home_win"].tolist() == [True, False]


def test_is_playoff_from_season_type():
    panel = _panel_of([_game("1", stype=2), _game("2", stype=3)])
    assert panel["is_playoff"].tolist() == [False, True]


def test_is_dome_only_permanent_dome():
    panel = _panel_of([_game("1", venue_id="31"),   # Tropicana -> dome
                       _game("2", venue_id="10")])  # open -> not dome
    assert panel["is_dome"].tolist() == [True, False]
    assert panel.loc[panel["is_dome"], ["temp_f", "wind_mph", "precip"]].isna().all().all()


def test_blue_jays_2020_relocated_home():
    panel = _panel_of([_game("1", home="TOR", season=2020, venue_id="99"),
                       _game("2", home="TOR", season=2019, venue_id="12"),
                       _game("3", home="NYY", season=2020, venue_id="10")])
    reloc = dict(zip(panel["game_id"], panel["relocated_home"]))
    assert reloc == {"mlb_1": True, "mlb_2": False, "mlb_3": False}


def test_doubleheader_game_ids_unique():
    # same date/teams/venue, two distinct ESPN ids -> two unique game_ids
    panel = _panel_of([_game("100"), _game("101")])
    assert panel["game_id"].is_unique


def test_neutral_site_from_espn_flag():
    panel = _panel_of([_game("1", neutral=True), _game("2", neutral=False)])
    assert panel["neutral_site"].tolist() == [True, False]


def test_crowd_pct_and_placeholders():
    panel = _panel_of([_game("1")])
    row = panel.iloc[0]
    assert row["crowd_pct"] == 1.0            # 40000/40000
    assert row["home_elo"] == 1500.0 and row["away_elo"] == 1500.0
    assert pd.isna(row["closing_spread"]) and pd.isna(row["away_travel_km"])
    assert pd.isna(row["home_rest_days"]) and pd.isna(row["temp_f"])
    assert bool(row["is_bubble"]) is False


def test_missing_capacity_raises():
    game = _game("1", venue_id="77", season=2019)
    with pytest.raises(ValueError):
        _build_panel([game], {"1": 40000}, capacity={}, treated_seasons=[2020, 2021])


def test_empty_stadium_crowd_pct_zero_not_null():
    # attendance=0 must yield crowd_pct 0.0 (a REAL value), never NaN. Capacity comes
    # from the same venue-season's non-empty game (30000 full house).
    games = [_game("1", venue_id="20", season=2019, hs=1, as_=0),
             _game("2", venue_id="20", season=2019, hs=5, as_=3)]
    att = {"1": 0, "2": 30000}
    cap_df = pd.DataFrame({"stadium_id": ["20", "20"], "season": [2019, 2019],
                           "attendance": [0, 30000]})
    from src.data._espn import derive_capacity
    cap = derive_capacity(cap_df, [2020, 2021])
    panel = _build_panel(games, att, cap, [2020, 2021])
    row = panel.set_index("game_id").loc["mlb_1"]
    assert row["crowd_pct"] == 0.0
    assert pd.notna(row["crowd_pct"])


def test_load_orchestrates_walk_fetch_and_coverage(monkeypatch):
    # two 2019 games at the same venue + one unplayed; attendance fetched per id.
    events = [
        _game("1", venue_id="10", hs=5, as_=3),
        _game("2", venue_id="10", hs=1, as_=0),
        _game("9", venue_id="10", status="STATUS_SCHEDULED"),  # dropped by _select
    ]
    from src.data import mlb
    monkeypatch.setattr(mlb, "walk_scoreboard", lambda sport, s, e: iter(events))
    monkeypatch.setattr(mlb, "fetch_summary",
                        lambda sport, eid: {"1": 30000, "2": 40000}.get(eid))
    panel, dropped = mlb.load([2019], treated_seasons=[2020, 2021])
    assert len(panel) == 2
    assert panel["game_id"].tolist() == ["mlb_1", "mlb_2"]
    # capacity = venue's 2019 max (40000); crowd_pct is dose vs full house
    assert panel.set_index("game_id").loc["mlb_1", "crowd_pct"] == 30000 / 40000
    assert dropped == []
