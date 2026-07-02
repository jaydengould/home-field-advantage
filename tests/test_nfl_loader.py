import json
import pandas as pd
from src.data import nfl
from src.data.nfl import _build_panel, _derive_capacity, _check_coverage
from src.schema import validate, COLUMNS


def _fake_schedule():
    return pd.DataFrame([
        # normal outdoor home win, margin +7
        dict(game_id="2019_01_A_B", season=2019, gameday="2019-09-08", game_type="REG",
             home_team="A", away_team="B", home_score=24, away_score=17,
             spread_line=-3.0, home_rest=7, away_rest=7, stadium="Field A",
             stadium_id="AAA00", roof="outdoors", temp=70, wind=5, location="Home", espn="1001"),
        # 2020 empty stadium, away win, margin -10
        dict(game_id="2020_01_C_D", season=2020, gameday="2020-09-13", game_type="REG",
             home_team="C", away_team="D", home_score=10, away_score=20,
             spread_line=2.5, home_rest=7, away_rest=10, stadium="Field C",
             stadium_id="CCC00", roof="outdoors", temp=65, wind=8, location="Home", espn="1002"),
        # tie, margin 0
        dict(game_id="2019_10_E_F", season=2019, gameday="2019-11-10", game_type="REG",
             home_team="E", away_team="F", home_score=13, away_score=13,
             spread_line=0.0, home_rest=7, away_rest=7, stadium="Field E",
             stadium_id="EEE00", roof="outdoors", temp=55, wind=3, location="Home", espn="1003"),
        # dome with junk temp/wind that must be nulled
        dict(game_id="2019_05_G_H", season=2019, gameday="2019-10-06", game_type="REG",
             home_team="G", away_team="H", home_score=31, away_score=28,
             spread_line=-6.5, home_rest=7, away_rest=7, stadium="Dome G",
             stadium_id="GGG00", roof="dome", temp=68, wind=0, location="Home", espn="1004"),
    ])


_ATT = {"1001": 62000, "1002": 0, "1003": 61000, "1004": 65000}
# capacity is keyed by (stadium_id, season) under Option A (empirical full-house ref)
_CAP = {("AAA00", 2019): 70000, ("CCC00", 2020): 65000,
        ("EEE00", 2019): 70000, ("GGG00", 2019): 70000}


def _panel():
    return _build_panel(_fake_schedule(), _ATT, _CAP, treated_seasons=[2020])


def test_build_panel_validates():
    validate(_panel())  # raises if the panel violates the schema


def test_columns_exact():
    assert list(_panel().columns) == list(COLUMNS)


def test_empty_stadium_crowd_pct_zero():
    row = _panel().set_index("game_id").loc["2020_01_C_D"]
    assert row["attendance"] == 0
    assert row["crowd_pct"] == 0.0
    assert row["covid_era"] == True


def test_tie_home_win_null():
    row = _panel().set_index("game_id").loc["2019_10_E_F"]
    assert row["home_margin"] == 0
    assert pd.isna(row["home_win"])


def test_dome_weather_null():
    row = _panel().set_index("game_id").loc["2019_05_G_H"]
    assert row["is_dome"] == True
    assert pd.isna(row["temp_f"])
    assert pd.isna(row["wind_mph"])
    assert pd.isna(row["precip"])


def test_home_win_sign():
    p = _panel().set_index("game_id")
    assert p.loc["2019_01_A_B", "home_win"] == True
    assert p.loc["2019_01_A_B", "home_margin"] == 7
    assert p.loc["2020_01_C_D", "home_win"] == False
    assert p.loc["2020_01_C_D", "home_margin"] == -10


def test_missing_capacity_raises():
    cap = dict(_CAP); del cap[("GGG00", 2019)]
    try:
        _build_panel(_fake_schedule(), _ATT, cap, [2020])
        assert False, "expected ValueError for missing (stadium_id, season)"
    except ValueError as e:
        assert "GGG00" in str(e)


def test_derive_capacity_self_reference_and_borrow():
    # Stadium X: normal 2019/2022 seasons + a TREATED 2020 that stayed ~full anyway.
    # The treated season must STILL borrow (not self-reference), even though its own
    # max (69000) exceeds 50% of the all-time max — proving suppression is decided by
    # treated_seasons, not a magnitude threshold.
    df = pd.DataFrame([
        ("X", 2019, 70000), ("X", 2019, 65000),   # 2019 full house = 70000
        ("X", 2020, 69000), ("X", 2020, 3000),     # treated; own max 69000 but must borrow
        ("X", 2022, 68000), ("X", 2022, 66000),   # 2022 full house = 68000
    ], columns=["stadium_id", "season", "attendance"])
    cap = _derive_capacity(df, treated_seasons=[2020])
    assert cap[("X", 2019)] == 70000          # normal -> self-references its own max
    assert cap[("X", 2022)] == 68000          # normal -> self-references its own max
    assert cap[("X", 2020)] == 70000          # treated -> borrows non-treated max (not 69000)


def test_derive_capacity_single_season_and_all_zero():
    # Y: one NORMAL season only -> self-references its own max.
    # Z: only ever a TREATED season with all-zero attendance -> floored to >=1.
    df = pd.DataFrame([
        ("Y", 2021, 0), ("Y", 2021, 500),
        ("Z", 2020, 0), ("Z", 2020, 0),
    ], columns=["stadium_id", "season", "attendance"])
    cap = _derive_capacity(df, treated_seasons=[2020])
    assert cap[("Y", 2021)] == 500
    assert cap[("Z", 2020)] >= 1


def test_check_coverage_trips_above_5pct():
    _check_coverage({2019: 1}, {2019: 100})   # 1% missing -> fine, no raise
    try:
        _check_coverage({2020: 2}, {2020: 10})   # 20% missing -> must hard-fail
        assert False, "expected ValueError when >5% of a season is missing"
    except ValueError as e:
        assert "2020" in str(e)


def test_fetch_uses_cache_no_network(tmp_path, monkeypatch):
    monkeypatch.setattr(nfl, "RAW_DIR", tmp_path)
    (tmp_path / "999.json").write_text(json.dumps({"gameInfo": {"attendance": 54321}}))

    def _boom(*a, **k):
        raise AssertionError("network was hit despite cache present")

    monkeypatch.setattr(nfl.requests, "get", _boom)
    assert nfl._fetch_attendance("999") == 54321


def test_fetch_missing_attendance_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(nfl, "RAW_DIR", tmp_path)
    (tmp_path / "888.json").write_text(json.dumps({"gameInfo": {}}))
    monkeypatch.setattr(nfl.requests, "get", lambda *a, **k: (_ for _ in ()).throw(AssertionError()))
    assert nfl._fetch_attendance("888") is None
