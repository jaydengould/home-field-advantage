import pandas as pd
import pytest

from src.schema import COLUMNS, validate


def valid_panel() -> pd.DataFrame:
    """One correct row, every column at its proper dtype."""
    return pd.DataFrame({
        "sport": pd.Series(["nfl"], dtype="object"),
        "game_id": ["2020_07_KC_DEN"],
        "season": [2020],
        "date": pd.to_datetime(["2020-10-25"]),
        "is_playoff": [False],
        "home_team": ["DEN"], "away_team": ["KC"],
        "home_score": [16], "away_score": [43],
        "home_margin": [-27],
        "home_win": pd.array([False], dtype="boolean"),
        "attendance": [5314], "capacity": [76125],
        "crowd_pct": [5314 / 76125],
        "covid_era": [True],
        "home_elo": [1500.0], "away_elo": [1600.0],
        "closing_spread": [7.0],
        "home_rest_days": pd.array([7], dtype="Int64"),
        "away_rest_days": pd.array([6], dtype="Int64"),
        "away_travel_km": [1500.0],
        "venue": ["Empower Field at Mile High"],
        "is_dome": [False],
        "temp_f": [14.0], "wind_mph": [11.0], "precip": [0.0],
        "neutral_site": [False], "relocated_home": [False], "is_bubble": [False],
    })


def test_valid_panel_passes():
    validate(valid_panel())  # must not raise


def test_columns_count_is_locked():
    assert len(COLUMNS) == 29


def test_missing_column_raises():
    df = valid_panel().drop(columns=["venue"])
    with pytest.raises(ValueError, match="venue"):
        validate(df)


def test_crowd_pct_out_of_range_raises():
    df = valid_panel()
    df["crowd_pct"] = [2.0]
    with pytest.raises(ValueError, match="crowd_pct"):
        validate(df)


def test_null_in_non_nullable_raises():
    df = valid_panel()
    df["venue"] = [None]
    with pytest.raises(ValueError, match="venue"):
        validate(df)


def test_bad_sport_value_raises():
    df = valid_panel()
    df["sport"] = ["xfl"]
    with pytest.raises(ValueError, match="sport"):
        validate(df)


def test_home_margin_must_equal_score_diff():
    df = valid_panel()
    df["home_margin"] = [99]
    with pytest.raises(ValueError, match="home_margin"):
        validate(df)


def test_weather_on_domed_game_raises():
    df = valid_panel()
    df["is_dome"] = [True]          # weather columns still populated -> leak
    with pytest.raises(ValueError, match="weather"):
        validate(df)


def test_dome_with_null_weather_passes():
    df = valid_panel()
    df["is_dome"] = [True]
    df["temp_f"] = [float("nan")]   # stay float64; pd.NA would flip dtype to object
    df["wind_mph"] = [float("nan")]
    df["precip"] = [float("nan")]
    validate(df)  # must not raise


def test_crowd_pct_must_match_attendance_over_capacity():
    df = valid_panel()
    df["crowd_pct"] = [0.5]         # inconsistent with 5314/76125
    with pytest.raises(ValueError, match="crowd_pct"):
        validate(df)


def test_home_win_must_match_margin_sign():
    df = valid_panel()
    df["home_win"] = pd.array([True], dtype="boolean")  # but margin is -27
    with pytest.raises(ValueError, match="home_win"):
        validate(df)


def test_tie_requires_null_home_win():
    df = valid_panel()
    df["home_score"] = [20]
    df["away_score"] = [20]
    df["home_margin"] = [0]
    df["home_win"] = pd.array([True], dtype="boolean")  # tie must be null
    with pytest.raises(ValueError, match="home_win"):
        validate(df)


def test_empty_stadium_crowd_pct_zero_is_valid():
    df = valid_panel()
    df["attendance"] = [0]
    df["crowd_pct"] = [0.0]
    validate(df)  # 0 is a real value, must not raise
