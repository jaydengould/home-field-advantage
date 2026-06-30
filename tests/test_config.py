from pathlib import Path

import yaml

CONFIG = Path(__file__).resolve().parents[1] / "config" / "sports.yaml"


def test_config_has_three_sports_with_treated_seasons():
    cfg = yaml.safe_load(CONFIG.read_text())
    assert set(cfg) == {"nfl", "mlb", "nba"}
    for sport, body in cfg.items():
        seasons = body["treated_seasons"]
        assert isinstance(seasons, list) and seasons, f"{sport}: empty treated_seasons"
        assert all(isinstance(y, int) for y in seasons), f"{sport}: non-int season"


def test_nfl_treated_seasons_is_2020_only():
    cfg = yaml.safe_load(CONFIG.read_text())
    assert cfg["nfl"]["treated_seasons"] == [2020]
