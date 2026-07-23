import numpy as np
import pandas as pd
import pytest

from src.models.did import fit


def _panel(rows):
    """rows: list of (season, home_team, home_margin, home_win, flags...).
    Returns a minimal panel with the columns fit() touches."""
    df = pd.DataFrame(rows, columns=[
        "season", "home_team", "home_margin", "home_win",
        "neutral_site", "relocated_home", "is_bubble", "is_playoff",
    ])
    df["sport"] = "nfl"
    df["home_win"] = df["home_win"].astype("boolean")
    return df


def _clean_rows():
    """Full seasons 2019 & 2021 (margins [2,4] mean 3, both wins);
    treated 2020 (margins [-1,3] mean 1, win rate 0.5). 4 teams."""
    rows = []
    for team in ["A", "B", "C", "D"]:
        for season in (2019, 2021):
            for m in (2, 4):
                rows.append([season, team, m, m > 0, False, False, False, False])
        for m in (-1, 3):
            rows.append([2020, team, m, m > 0, False, False, False, False])
    return rows


def test_crowd_effect_recovers_full_minus_reduced_and_is_positive():
    panel = _panel(_clean_rows())
    r = fit(panel, "home_margin", sample="pooled", treated_seasons=[2020])
    assert r["hfa_full"] == pytest.approx(3.0)
    assert r["hfa_reduced"] == pytest.approx(1.0)
    assert r["crowd_effect"] == pytest.approx(2.0)   # 3 - 1, positive = crowd helps home
    assert r["ci_low"] < r["ci_high"]                # CI bounds ordered after the sign flip
    assert r["n_obs"] == 24 and r["n_full"] == 16 and r["n_reduced"] == 8


def test_excluded_games_are_dropped():
    rows = _clean_rows()
    rows.append([2020, "A", 100, True, False, False, True, False])   # bubble, absurd margin
    rows.append([2019, "B", 100, True, True, False, False, False])   # neutral site
    panel = _panel(rows)
    r = fit(panel, "home_margin", sample="pooled", treated_seasons=[2020])
    assert r["n_obs"] == 24                          # the 2 flagged rows excluded
    assert r["crowd_effect"] == pytest.approx(2.0)   # unaffected by the excluded outliers


def test_restricted_sample_keeps_only_adjacent_seasons():
    rows = _clean_rows()
    for team in ["A", "B", "C", "D"]:                # far full season, huge margin
        for m in (48, 52):
            rows.append([2015, team, m, m > 0, False, False, False, False])
    panel = _panel(rows)
    pooled = fit(panel, "home_margin", "pooled", treated_seasons=[2020])
    restr = fit(panel, "home_margin", "restricted", treated_seasons=[2020])
    assert pooled["hfa_full"] > restr["hfa_full"]        # 2015 inflates pooled only
    assert restr["hfa_full"] == pytest.approx(3.0)       # restricted = {2019,2020,2021}
    assert restr["crowd_effect"] == pytest.approx(2.0)


def test_win_outcome_runs_as_lpm():
    panel = _panel(_clean_rows())
    r = fit(panel, "home_win", sample="pooled", treated_seasons=[2020])
    assert r["hfa_full"] == pytest.approx(1.0)       # both full margins > 0
    assert r["hfa_reduced"] == pytest.approx(0.5)    # treated: one loss, one win
    assert r["crowd_effect"] == pytest.approx(0.5)


def test_plot_slope_returns_figure():
    from src.models.did import plot_slope
    panel = _panel(_clean_rows())
    rows = [
        fit(panel, oc, "pooled", treated_seasons=[2020])
        for oc in ("home_margin", "home_win")
    ]
    fig = plot_slope(pd.DataFrame(rows))
    # one panel per outcome
    assert len(fig.axes) == 2
