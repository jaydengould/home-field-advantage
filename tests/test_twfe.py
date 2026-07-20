import numpy as np
import pandas as pd
import pytest

from src.models.twfe import fit, _prep, _restricted_seasons


def _synth(beta=3.0, n_teams=8, seasons=(2018, 2019, 2020, 2021), games=14, seed=0):
    """Synthetic panel with a PLANTED crowd effect the estimator must recover.

    home_margin = beta*crowd_pct + team_effect + season_effect + 0.04*elo_diff + noise.
    Treated seasons 2020/2021 are lower on average, but crowd_pct carries a wide
    per-game jitter around the season base so its variation is NOT collinear with
    the season fixed effects — that within-FE variation is what identifies beta.
    (A season-locked crowd would be absorbed by the season FE, leaving a
    high-variance, unrecoverable estimate — a flaky test, not a real effect.)
    All exclusion flags False so nothing is dropped by _prep.
    """
    rng = np.random.default_rng(seed)
    rows = []
    team_fx = {f"T{i}": rng.normal(0, 2) for i in range(n_teams)}
    season_fx = {s: (s - 2018) * 0.5 for s in seasons}
    for i in range(n_teams):
        team = f"T{i}"
        # better teams (higher team_fx) draw persistently bigger crowds, so
        # crowd's team-mean correlates with margin -> entity FE genuinely matters
        # (omitting entity_effects biases the crowd coef out of tolerance).
        team_crowd = 0.05 * team_fx[team]
        for s in seasons:
            base = 0.30 if s in (2020, 2021) else 0.85
            for _ in range(games):
                crowd = float(np.clip(base + team_crowd + rng.uniform(-0.5, 0.5), 0.0, 1.0))
                elo_diff = rng.normal(0, 60)
                margin = (beta * crowd + team_fx[team] + season_fx[s]
                          + 0.04 * elo_diff + rng.normal(0, 0.5))
                rows.append(dict(
                    sport="nfl", season=s, home_team=team,
                    home_margin=margin, home_win=margin > 0, crowd_pct=crowd,
                    home_elo=1500 + elo_diff, away_elo=1500.0,
                    # rest/travel carry real variance so they aren't zero-variance
                    # controls (a constant regressor is rank-deficient under FE)
                    home_rest_days=int(rng.integers(3, 10)),
                    away_rest_days=int(rng.integers(3, 10)),
                    away_travel_km=float(rng.uniform(100, 3000)),
                    neutral_site=False, relocated_home=False,
                    is_bubble=False, is_playoff=False,
                ))
    df = pd.DataFrame(rows)
    df["home_win"] = df["home_win"].astype("boolean")
    df["home_rest_days"] = df["home_rest_days"].astype("Int64")
    df["away_rest_days"] = df["away_rest_days"].astype("Int64")
    return df


def test_restricted_seasons_brackets_treated():
    assert _restricted_seasons([2020]) == {2019, 2020, 2021}
    assert _restricted_seasons([2020, 2021]) == {2019, 2020, 2021, 2022}
    assert _restricted_seasons([2021]) == {2020, 2021, 2022}


def test_prep_drops_excluded_rows():
    df = _synth(games=2)
    n_before = len(df)
    df.loc[df.index[0], "neutral_site"] = True
    df.loc[df.index[1], "is_bubble"] = True
    df.loc[df.index[2], "is_playoff"] = True
    df.loc[df.index[3], "relocated_home"] = True
    out = _prep(df)
    assert len(out) == n_before - 4
    assert {"elo_diff", "rest_diff"}.issubset(out.columns)


def test_fit_recovers_planted_margin_effect():
    res = fit(_synth(beta=3.0), "home_margin", "pooled", treated_seasons=[2020, 2021])
    assert res["coef"] == pytest.approx(3.0, abs=0.5)   # planted beta recovered
    assert res["ci_low"] < res["coef"] < res["ci_high"]
    assert res["n_obs"] > 0 and res["n_entities"] == 8
    assert res["sport"] == "nfl" and res["outcome"] == "home_margin"


def test_fit_restricted_sample_keeps_only_bracket_seasons():
    df = _synth(seasons=(2017, 2018, 2019, 2020, 2021, 2022, 2023))
    full = fit(df, "home_margin", "pooled", treated_seasons=[2020, 2021])
    restr = fit(df, "home_margin", "restricted", treated_seasons=[2020, 2021])
    assert restr["n_obs"] < full["n_obs"]               # dropped 2017 & 2023
    # 4 kept seasons {2019,2020,2021,2022} * 8 teams * 14 games
    assert restr["n_obs"] == 4 * 8 * 14


def test_fit_lpm_outcome_runs_on_binary():
    res = fit(_synth(), "home_win", "pooled", treated_seasons=[2020, 2021])
    assert -1.0 <= res["coef"] <= 1.0                   # a win-probability slope
    assert res["outcome"] == "home_win"


def test_plot_effect_returns_figure():
    from src.models.twfe import plot_effect
    rows = pd.DataFrame([
        dict(sport="nfl", outcome="home_margin", sample="pooled",
             coef=1.5, ci_low=0.5, ci_high=2.5),
        dict(sport="mlb", outcome="home_win", sample="restricted",
             coef=0.03, ci_low=-0.01, ci_high=0.07),
    ])
    fig = plot_effect(rows)
    assert fig is not None
    assert len(fig.axes) >= 1
