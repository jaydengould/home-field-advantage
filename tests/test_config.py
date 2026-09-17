from pathlib import Path

import pandas as pd
import yaml

CONFIG = Path(__file__).resolve().parents[1] / "config" / "sports.yaml"


def test_config_has_four_sports_with_treated_seasons():
    cfg = yaml.safe_load(CONFIG.read_text())
    assert set(cfg) == {"nfl", "mlb", "nba", "nhl"}
    for sport, body in cfg.items():
        seasons = body["treated_seasons"]
        assert isinstance(seasons, list) and seasons, f"{sport}: empty treated_seasons"
        assert all(isinstance(y, int) for y in seasons), f"{sport}: non-int season"


def test_nfl_treated_seasons_is_2020_only():
    cfg = yaml.safe_load(CONFIG.read_text())
    assert cfg["nfl"]["treated_seasons"] == [2020]


def test_nfl_load_seasons():
    import yaml
    cfg = yaml.safe_load(open("config/sports.yaml"))
    lo, hi = cfg["nfl"]["load_seasons"]
    assert lo == 2018 and hi == 2023
    assert lo <= hi


def test_elo_params_present_for_all_sports():
    import yaml
    from pathlib import Path
    cfg = yaml.safe_load(Path("config/sports.yaml").read_text())
    for sport in ("nfl", "mlb", "nba", "nhl"):
        elo = cfg[sport]["elo"]
        assert {"k", "hfa", "carryover"} <= set(elo)
        assert 0.0 < elo["carryover"] <= 1.0


def test_every_sport_has_zero_attendance_windows():
    cfg = yaml.safe_load(CONFIG.read_text())
    for sport in ("nfl", "mlb", "nba", "nhl"):
        w = cfg[sport]["zero_attendance_windows"]
        assert isinstance(w, list) and w
        for win in w:
            assert ("seasons" in win) != ("start" in win)
            assert set(win) <= {"seasons", "start", "end", "home_teams"}


def test_reopening_config_keys_present_and_well_formed():
    cfg = yaml.safe_load(Path("config/sports.yaml").read_text())
    for sport in ("nfl", "mlb", "nba", "nhl"):
        c = cfg[sport]
        for f in c["fans_from"]:
            assert f["season"] in c["treated_seasons"] and f["source"].startswith("http")
            pd.Timestamp(f["date"])
        for r in c["reclosures"]:
            assert pd.Timestamp(r["start"]) <= pd.Timestamp(r["end"]) and r["source"].startswith("http")
