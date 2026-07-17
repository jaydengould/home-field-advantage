import numpy as np
import pandas as pd
import pytest

from src.viz.descriptive import summarize, _print_gate


def _panel():
    # season 2019 (covid_era=False): 3 clean regular-season home games
    #   win (+7), loss (-3), tie (0, home_win=NA)
    #   + 1 neutral-site game (excluded), + 1 playoff game (excluded)
    # season 2020 (covid_era=True): 2 clean games: win (+1), loss (-6)
    rows = [
        dict(season=2019, is_playoff=False, neutral_site=False, relocated_home=False,
             is_bubble=False, home_win=True,  home_margin=7,  covid_era=False),
        dict(season=2019, is_playoff=False, neutral_site=False, relocated_home=False,
             is_bubble=False, home_win=False, home_margin=-3, covid_era=False),
        dict(season=2019, is_playoff=False, neutral_site=False, relocated_home=False,
             is_bubble=False, home_win=pd.NA, home_margin=0,  covid_era=False),
        dict(season=2019, is_playoff=False, neutral_site=True,  relocated_home=False,
             is_bubble=False, home_win=True,  home_margin=10, covid_era=False),
        dict(season=2019, is_playoff=True,  neutral_site=False, relocated_home=False,
             is_bubble=False, home_win=True,  home_margin=14, covid_era=False),
        dict(season=2020, is_playoff=False, neutral_site=False, relocated_home=False,
             is_bubble=False, home_win=True,  home_margin=1,  covid_era=True),
        dict(season=2020, is_playoff=False, neutral_site=False, relocated_home=False,
             is_bubble=False, home_win=False, home_margin=-6, covid_era=True),
    ]
    df = pd.DataFrame(rows)
    df["sport"] = "nfl"
    df["home_win"] = df["home_win"].astype("boolean")
    return df


def test_exclusions_and_counts():
    out = summarize(_panel())
    r19 = out[out["season"] == 2019].iloc[0]
    assert r19["n_games"] == 3          # neutral + playoff excluded, tie kept
    assert r19["n_games_raw"] == 4      # regular-season games before exclusions (excl playoff)


def test_win_pct_and_margin_2019():
    out = summarize(_panel())
    r19 = out[out["season"] == 2019].iloc[0]
    # decided games = win, loss -> 0.5; tie excluded from win%
    assert r19["home_win_pct"] == pytest.approx(0.5)
    assert r19["home_win_se"] == pytest.approx(0.3535533905932738)
    # margin over win/loss/tie = (7 - 3 + 0)/3
    assert r19["mean_home_margin"] == pytest.approx(1.3333333333333333)
    assert r19["home_margin_se"] == pytest.approx(2.96273147243853)


def test_2020_values():
    out = summarize(_panel())
    r20 = out[out["season"] == 2020].iloc[0]
    assert r20["mean_home_margin"] == pytest.approx(-2.5)
    assert r20["home_margin_se"] == pytest.approx(3.5)


def test_pooled_fullcrowd_uses_only_noncovid():
    out = summarize(_panel())
    pooled = out[out["season"] == "pooled_fullcrowd"].iloc[0]
    # only 2019 is covid_era False -> pooled == 2019 numbers
    assert pooled["mean_home_margin"] == pytest.approx(1.3333333333333333)
    assert pooled["home_win_pct"] == pytest.approx(0.5)
    assert pooled["n_games"] == 3


def test_covid_era_flag_per_season():
    out = summarize(_panel())
    assert out[out["season"] == 2019].iloc[0]["covid_era"] == False  # noqa: E712
    assert out[out["season"] == 2020].iloc[0]["covid_era"] == True   # noqa: E712
    # pooled_fullcrowd is the full-crowd baseline -> not treated
    assert out[out["season"] == "pooled_fullcrowd"].iloc[0]["covid_era"] == False  # noqa: E712


def test_gate_keys_off_treated_season_not_hardcoded_2020(capsys):
    # NBA-style: the treated season is 2021 (not 2020). 2020 is full-crowd and
    # does NOT dip; the real dip is in 2021. The gate must PASS off 2021, which a
    # hardcoded-2020 check would miss (it would see 2020's non-dip and CHECK).
    table = pd.DataFrame([
        dict(sport="nba", season=2019, covid_era=False, home_win_pct=0.60, mean_home_margin=3.0),
        dict(sport="nba", season=2020, covid_era=False, home_win_pct=0.60, mean_home_margin=3.0),
        dict(sport="nba", season=2021, covid_era=True,  home_win_pct=0.55, mean_home_margin=0.9),
        dict(sport="nba", season="pooled_fullcrowd", covid_era=False,
             home_win_pct=0.59, mean_home_margin=2.5),
    ])
    _print_gate(table)
    out = capsys.readouterr().out
    assert "[PASS] nba" in out
    assert "treated=[2021]" in out


def test_gate_checks_reports_no_dip(capsys):
    # Treated season margin ABOVE pooled -> no dip -> CHECK (MLB-style).
    table = pd.DataFrame([
        dict(sport="mlb", season=2020, covid_era=True, home_win_pct=0.55, mean_home_margin=0.18),
        dict(sport="mlb", season="pooled_fullcrowd", covid_era=False,
             home_win_pct=0.53, mean_home_margin=0.04),
    ])
    _print_gate(table)
    out = capsys.readouterr().out
    assert "[CHECK] mlb" in out
