import numpy as np
import pandas as pd
import pytest

from src.features.build import _haversine_km, load_coords, add_travel, add_rest, add_elo, _elo_params, build, elo_accuracy
from src.schema import COLUMNS


def _row(**kw):
    """Minimal schema-complete row; override fields via kwargs."""
    base = {c: None for c in COLUMNS}
    base.update(dict(
        sport="nba", game_id="x", season=2019, date=pd.Timestamp("2019-01-01"),
        is_playoff=False, home_team="BOS", away_team="LAL",
        home_score=100, away_score=90, home_margin=10, home_win=True,
        attendance=1, capacity=1, crowd_pct=1.0, covid_era=False,
        home_elo=1500.0, away_elo=1500.0, closing_spread=np.nan,
        home_rest_days=pd.NA, away_rest_days=pd.NA, away_travel_km=np.nan,
        venue="v", is_dome=True, temp_f=np.nan, wind_mph=np.nan, precip=np.nan,
        neutral_site=False, relocated_home=False, is_bubble=False,
    ))
    base.update(kw)
    return base


def test_haversine_known_distance():
    # NYC -> LA is ~3940 km; allow 2% slack for city-center choice.
    km = _haversine_km(40.71, -74.01, 34.05, -118.24)
    assert 3860 < km < 4020


def test_haversine_symmetric():
    a = _haversine_km(40.71, -74.01, 34.05, -118.24)
    b = _haversine_km(34.05, -118.24, 40.71, -74.01)
    assert a == pytest.approx(b)


def test_travel_normal_game_positive():
    coords = {("nba", "BOS"): (42.37, -71.06), ("nba", "LAL"): (34.04, -118.27)}
    out = add_travel(pd.DataFrame([_row()]), coords)
    assert out["away_travel_km"].iloc[0] == pytest.approx(4150, rel=0.03)


def test_travel_bubble_is_zero():
    coords = {}  # bubble path must not need coords
    out = add_travel(pd.DataFrame([_row(is_bubble=True)]), coords)
    assert out["away_travel_km"].iloc[0] == 0.0


def test_travel_neutral_and_relocated_are_null():
    coords = {}
    out = add_travel(pd.DataFrame([
        _row(neutral_site=True), _row(relocated_home=True),
    ]), coords)
    assert out["away_travel_km"].isna().all()


def test_travel_missing_coords_raises():
    with pytest.raises(ValueError, match="missing"):
        add_travel(pd.DataFrame([_row()]), coords={})


def test_load_coords_shape():
    coords = load_coords()
    assert coords[("nfl", "OAK")] != coords[("nfl", "LV")]  # relocation kept distinct
    assert isinstance(coords[("mlb", "NYY")], tuple)


def test_coords_cover_every_panel_team():
    coords = load_coords()
    for sport in ("nfl", "mlb", "nba"):
        d = pd.read_parquet(f"data/interim/{sport}.parquet")
        teams = set(d["home_team"]) | set(d["away_team"])
        missing = sorted(t for t in teams if (sport, t) not in coords)
        assert not missing, f"{sport} teams missing coords: {missing}"


def test_rest_first_game_of_season_is_null():
    rows = [
        _row(sport="nba", game_id="g1", season=2019, date=pd.Timestamp("2019-01-01"),
             home_team="BOS", away_team="LAL"),
        _row(sport="nba", game_id="g2", season=2019, date=pd.Timestamp("2019-01-04"),
             home_team="LAL", away_team="BOS"),
    ]
    out = add_rest(pd.DataFrame(rows)).sort_values("game_id").reset_index(drop=True)
    # g1: both teams' first game of the season -> NA/NA
    assert pd.isna(out.loc[0, "home_rest_days"]) and pd.isna(out.loc[0, "away_rest_days"])
    # g2: both played g1 three days earlier
    assert out.loc[1, "home_rest_days"] == 3 and out.loc[1, "away_rest_days"] == 3


def test_rest_resets_across_seasons():
    rows = [
        _row(sport="nba", game_id="a", season=2019, date=pd.Timestamp("2019-04-01"),
             home_team="BOS", away_team="LAL"),
        _row(sport="nba", game_id="b", season=2020, date=pd.Timestamp("2019-10-25"),
             home_team="BOS", away_team="LAL"),
    ]
    out = add_rest(pd.DataFrame(rows)).sort_values("game_id").reset_index(drop=True)
    # 'b' is the first 2020 game for both teams -> NA despite a prior 2019 game
    assert pd.isna(out.loc[1, "home_rest_days"]) and pd.isna(out.loc[1, "away_rest_days"])


def test_rest_dtype_is_int64():
    out = add_rest(pd.DataFrame([_row()]))
    assert out["home_rest_days"].dtype == "Int64"


def test_rest_does_not_conflate_same_abbrev_across_sports():
    # "SF" is both NFL (49ers) and MLB (Giants). A shared abbrev in one season
    # must not chain one sport's game onto the other's.
    rows = [
        _row(sport="nfl", game_id="n1", season=2019, date=pd.Timestamp("2019-09-08"),
             home_team="SF", away_team="DAL"),
        _row(sport="mlb", game_id="m1", season=2019, date=pd.Timestamp("2019-09-10"),
             home_team="SF", away_team="LAD"),
    ]
    out = add_rest(pd.DataFrame(rows)).set_index("game_id")
    # Each SF game is that sport's FIRST SF game of the season -> NA, not 2 days.
    assert pd.isna(out.loc["n1", "home_rest_days"])
    assert pd.isna(out.loc["m1", "home_rest_days"])


def _elo_row(gid, date, home, away, hs, as_, season=2019, sport="nba"):
    return _row(sport=sport, game_id=gid, date=pd.Timestamp(date), season=season,
                home_team=home, away_team=away, home_score=hs, away_score=as_,
                home_margin=hs - as_, home_win=(hs > as_))


def test_elo_pregame_ratings_start_at_1500():
    out = add_elo(pd.DataFrame([_elo_row("g1", "2019-01-01", "BOS", "LAL", 110, 100)]),
                  {"k": 20, "hfa": 0, "carryover": 0.75})
    assert out["home_elo"].iloc[0] == 1500.0 and out["away_elo"].iloc[0] == 1500.0


def test_elo_winner_gains_rating_next_game():
    # BOS beats LAL in g1; in g2 (BOS home again vs NYK) BOS's pre-game elo > 1500.
    rows = [
        _elo_row("g1", "2019-01-01", "BOS", "LAL", 110, 100),
        _elo_row("g2", "2019-01-03", "BOS", "NY", 100, 99),
    ]
    out = add_elo(pd.DataFrame(rows), {"k": 20, "hfa": 0, "carryover": 0.75})
    out = out.sort_values("game_id").reset_index(drop=True)
    assert out.loc[1, "home_elo"] > 1500.0  # BOS carried its g1 win forward


def test_elo_is_pregame_not_contaminated():
    # A team's stored elo for a game must NOT include that game's own result.
    row = _elo_row("g1", "2019-01-01", "BOS", "LAL", 150, 50)  # blowout
    out = add_elo(pd.DataFrame([row]), {"k": 20, "hfa": 0, "carryover": 0.75})
    assert out["home_elo"].iloc[0] == 1500.0  # pre-game, blowout not yet applied


def test_elo_preserves_row_order():
    rows = [
        _elo_row("g2", "2019-01-03", "BOS", "NY", 100, 99),
        _elo_row("g1", "2019-01-01", "BOS", "LAL", 110, 100),
    ]
    out = add_elo(pd.DataFrame(rows), {"k": 20, "hfa": 0, "carryover": 0.75})
    assert list(out["game_id"]) == ["g2", "g1"]  # original order preserved


def test_elo_accuracy_reasonable_on_synthetic():
    # Strong home team always wins big -> higher-elo side wins -> accuracy high.
    rows, elo = [], None
    for n in range(20):
        rows.append(_elo_row(f"g{n:02d}", f"2019-02-{n+1:02d}", "BOS", "LAL", 120, 100))
    out = add_elo(pd.DataFrame(rows), {"k": 20, "hfa": 100, "carryover": 0.75})
    acc, brier = elo_accuracy(out, hfa=100)
    assert acc > 0.8 and 0.0 <= brier <= 0.25


def test_build_writes_processed_and_validates(tmp_path, monkeypatch):
    # Smoke on real interim data for one sport; validate() must pass and file appears.
    import src.features.build as b
    panel = b.build("nfl")
    from src.schema import validate
    validate(panel)  # raises if bad
    assert (b.PROCESSED / "nfl.parquet").exists()
    assert panel["home_elo"].notna().all() and panel["away_elo"].notna().all()
    assert panel["away_travel_km"].notna().any()


from src.features.build import null_reporting_zeros


def _zpanel(rows):
    return pd.DataFrame(rows, columns=["season", "date", "home_team", "attendance", "crowd_pct"]).assign(
        date=lambda d: pd.to_datetime(d["date"], format="ISO8601"))


def test_zero_outside_every_window_is_nulled():
    p = _zpanel([(2019, "2019-05-01", "BOS", 0, 0.0)])
    out, n = null_reporting_zeros(p, [{"seasons": [2020]}])
    assert n == 1 and out["crowd_pct"].isna().all()


def test_zero_inside_season_window_stays_zero():
    p = _zpanel([(2020, "2020-08-01", "BOS", 0, 0.0)])
    out, n = null_reporting_zeros(p, [{"seasons": [2020]}])
    assert n == 0 and (out["crowd_pct"] == 0.0).all()


def test_nonzero_attendance_never_nulled():
    p = _zpanel([(2019, "2019-05-01", "BOS", 30000, 0.8)])
    out, n = null_reporting_zeros(p, [])
    assert n == 0 and out["crowd_pct"].iloc[0] == 0.8


def test_date_window_is_inclusive_and_team_scoped():
    w = [{"start": "2021-12-16", "end": "2022-02-20", "home_teams": ["TOR"]}]
    p = _zpanel([
        (2022, "2021-12-16 23:00", "TOR", 0, 0.0),   # start day, in team -> real
        (2022, "2022-02-20", "TOR", 0, 0.0),         # end day -> real
        (2022, "2022-02-21", "TOR", 0, 0.0),         # after end -> artifact
        (2022, "2022-01-10", "BOS", 0, 0.0),         # wrong team -> artifact
    ])
    out, n = null_reporting_zeros(p, w)
    assert n == 2
    assert out["crowd_pct"].isna().tolist() == [False, False, True, True]


def test_helper_does_not_mutate_input():
    p = _zpanel([(2019, "2019-05-01", "BOS", 0, 0.0)])
    null_reporting_zeros(p, [])
    assert p["crowd_pct"].iloc[0] == 0.0


def _rpanel(rows):
    """Treated-season rows with the exclusion flags the reopening rule reads."""
    df = pd.DataFrame(rows, columns=["season", "date", "home_team", "attendance", "crowd_pct"])
    return df.assign(date=pd.to_datetime(df["date"], format="ISO8601"), is_playoff=False,
                     is_bubble=False, neutral_site=False, relocated_home=False)


W21 = [{"seasons": [2021]}]


def test_reopening_zero_after_first_nonzero_game_is_nulled():
    p = _rpanel([(2021, "2021-01-10", "CLE", 0, 0.0),      # before fans -> real
                 (2021, "2021-01-20", "CLE", 500, 0.03),   # first fans (data)
                 (2021, "2021-02-01", "CLE", 0, 0.0)])     # after -> artifact
    out, n = null_reporting_zeros(p, W21, treated_seasons=[2021])
    assert n == 1 and out["crowd_pct"].isna().tolist() == [False, False, True]


def test_configured_fans_from_nulls_all_zero_team_from_that_date_inclusive():
    p = _rpanel([(2021, "2021-01-20", "MIA", 0, 0.0),
                 (2021, "2021-01-29", "MIA", 0, 0.0),
                 (2021, "2021-02-05", "MIA", 0, 0.0)])
    ff = [{"season": 2021, "team": "MIA", "date": "2021-01-29", "source": "x"}]
    out, n = null_reporting_zeros(p, W21, [2021], ff)
    assert n == 2 and out["crowd_pct"].isna().tolist() == [False, True, True]


def test_earlier_of_data_and_configured_date_wins():
    p = _rpanel([(2021, "2021-01-10", "IND", 0, 0.0),
                 (2021, "2021-01-15", "IND", 0, 0.0),
                 (2021, "2021-01-20", "IND", 900, 0.05)])
    late = [{"season": 2021, "team": "IND", "date": "2021-01-30", "source": "x"}]
    early = [{"season": 2021, "team": "IND", "date": "2021-01-15", "source": "x"}]
    assert null_reporting_zeros(p, W21, [2021], late)[1] == 0      # data date 01-20 wins
    assert null_reporting_zeros(p, W21, [2021], early)[1] == 1     # config date 01-15 wins


def test_sourced_reclosure_keeps_zero_real():
    p = _rpanel([(2020, "2020-10-01", "BAL", 7000, 0.1),
                 (2020, "2020-12-08", "BAL", 0, 0.0),     # inside re-closure -> real
                 (2020, "2021-01-03", "BAL", 0, 0.0)])    # outside -> artifact
    rc = [{"team": "BAL", "start": "2020-11-20", "end": "2020-12-31", "source": "x"}]
    out, n = null_reporting_zeros(p, [{"seasons": [2020]}], [2020], (), rc)
    assert n == 1 and out["crowd_pct"].isna().tolist() == [False, False, True]


def test_no_fans_team_and_untreated_season_and_excluded_rows_untouched():
    p = _rpanel([(2021, "2021-02-01", "OKC", 0, 0.0),     # never fans -> real
                 (2022, "2021-11-01", "TOR", 900, 0.05),  # untreated season, Canadian window
                 (2022, "2022-01-05", "TOR", 0, 0.0)])
    w = W21 + [{"start": "2021-12-16", "end": "2022-02-20", "home_teams": ["TOR"]}]
    out, n = null_reporting_zeros(p, w, [2021])
    assert n == 0
    q = _rpanel([(2021, "2021-01-05", "LAL", 900, 0.05), (2021, "2021-01-09", "LAL", 0, 0.0)])
    q.loc[1, "is_playoff"] = True
    assert null_reporting_zeros(q, W21, [2021])[1] == 0


def test_windows_only_call_matches_fix_one():
    p = _rpanel([(2021, "2021-01-05", "CLE", 900, 0.05), (2021, "2021-01-09", "CLE", 0, 0.0),
                 (2019, "2019-05-01", "BOS", 0, 0.0)])
    out, n = null_reporting_zeros(p, W21)
    assert n == 1 and out["crowd_pct"].isna().tolist() == [False, False, True]
