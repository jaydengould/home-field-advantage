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


def test_drop_controls_removes_only_the_named_control():
    # The NHL travel diagnostic refits dropping away_travel_km. In _synth, travel is
    # independent noise, so dropping it must NOT move the planted beta=3.0 much.
    # Also pins the property the diagnostic depends on: dropping a control must not
    # silently change the estimation sample (see below).
    import src.models.twfe as twfe

    panel = _synth(beta=3.0)
    base = twfe.fit(panel, "home_margin", "pooled", [2020, 2021])
    reduced = twfe.fit(panel, "home_margin", "pooled", [2020, 2021],
                       drop_controls=["away_travel_km"])

    assert "coef_away_travel_km" in base                 # present in the full spec
    assert "coef_away_travel_km" not in reduced          # genuinely dropped
    assert "coef_elo_diff" in reduced                    # other controls survive
    assert twfe.CONTROLS == ["crowd_pct", "elo_diff", "rest_diff", "away_travel_km"]
    assert abs(reduced["coef"] - base["coef"]) < 0.5     # independent control -> small move


def test_n_obs_tracks_estimation_sample_when_dropped_control_has_nans():
    # A dropped control also leaves fit()'s dropna() column set, so the reduced fit
    # CAN run on more rows — which would let a sample shift masquerade as a
    # coefficient shift and silently invalidate the NHL travel diagnostic. That is
    # why the diagnostic records n_obs for BOTH fits and warns when they differ.
    #
    # Asserting equality on _synth would be VACUOUS: the fixture has no NaNs, so
    # n_obs matches under any implementation. Inject NaNs so the assertion can fail
    # if n_obs ever stops reflecting the true estimation sample.
    panel = _synth(beta=3.0)
    panel.loc[panel.index[:40], "away_travel_km"] = np.nan

    base = fit(panel, "home_margin", "pooled", [2020, 2021])
    reduced = fit(panel, "home_margin", "pooled", [2020, 2021],
                  drop_controls=["away_travel_km"])

    assert base["n_obs"] == len(panel) - 40      # the 40 NaN rows are listwise-dropped
    assert reduced["n_obs"] == len(panel)        # dropping the control restores them
    assert reduced["n_obs"] > base["n_obs"]      # the hazard the diagnostic guards against


def test_defaults_unchanged_by_new_params():
    # The 6a spec is frozen: the default call path must be byte-identical.
    panel = _synth(beta=3.0)
    a = fit(panel, "home_margin", "pooled", [2020, 2021])
    b = fit(panel, "home_margin", "pooled", [2020, 2021],
            trend="linear", season_fe=False, report=None)
    assert a == b
    assert a["trend"] == "linear" and a["season_fe"] is False


def test_trend_options_change_the_fit_but_not_the_sample():
    # Asserting n_obs equality on a NaN-free _synth would be VACUOUS (same
    # standard as test_n_obs_tracks_estimation_sample_when_dropped_control_has_nans
    # above): the trend columns are derived from "season", which is never NaN, so
    # any implementation would pass trivially. Inject NaNs into a base control so
    # the equality is a real claim about listwise dropna happening identically
    # across trend specs, not a coincidence of a clean fixture.
    panel = _synth(beta=3.0)
    panel.loc[panel.index[:40], "away_travel_km"] = np.nan
    fits = {t: fit(panel, "home_margin", "pooled", [2020, 2021], trend=t)
            for t in ("none", "linear", "quadratic")}
    assert len({f["n_obs"] for f in fits.values()}) == 1        # same rows, different spec
    assert fits["none"]["n_obs"] == len(panel) - 40             # the 40 NaN rows really are dropped
    assert fits["none"]["coef"] != fits["linear"]["coef"]        # trend actually enters
    assert "coef_season_trend_sq" not in fits["linear"]
    # Planted beta survives a season control: _synth's season_fx is exactly linear
    # in season, so trend="linear"/"quadratic" fully absorb it via season_trend.
    # trend="none" leaves season_fx unmodeled, and it correlates with crowd_pct's
    # season-varying base (0.85 pre-treatment -> 0.30 treated) -- exactly the
    # omitted-variable failure mode this module's own docstring warns about for
    # full season FE, just weaker. Verified empirically (not in this test): the
    # ~1.0 downward bias persists at 15x the sample size and across seeds, so it
    # is structural, not small-sample noise -- "none" is correctly expected to be
    # biased, not merely noisier.
    for t in ("linear", "quadratic"):
        assert fits[t]["coef"] == pytest.approx(3.0, abs=0.6)
    assert fits["none"]["coef"] < fits["linear"]["coef"] - 0.5


def test_season_fe_requires_no_trend():
    panel = _synth(beta=3.0)
    with pytest.raises(ValueError):
        fit(panel, "home_margin", "pooled", [2020, 2021], season_fe=True, trend="linear")
    res = fit(panel, "home_margin", "pooled", [2020, 2021], season_fe=True, trend="none")
    assert res["season_fe"] is True
    assert res["n_obs"] > 0
    # Pin that time_effects actually engages PanelOLS (not a no-op echoing the
    # input): full season FE must land on a materially different coefficient
    # than zero season control (measured 3.02 vs 1.98) — this fails if
    # twfe.py's `time_effects=season_fe` were hardcoded to False.
    no_control = fit(panel, "home_margin", "pooled", [2020, 2021],
                      season_fe=False, trend="none")
    assert abs(res["coef"] - no_control["coef"]) > 0.5


def test_invalid_trend_and_report_raise_value_error():
    panel = _synth(beta=3.0)
    with pytest.raises(ValueError):
        fit(panel, "home_margin", "pooled", [2020, 2021], trend="cubic")
    with pytest.raises(ValueError):
        fit(panel, "home_margin", "pooled", [2020, 2021], report="not_a_regressor")


def test_treated_sample_keeps_only_treated_seasons():
    panel = _synth(seasons=(2018, 2019, 2020, 2021))
    res = fit(panel, "home_margin", "treated", [2020, 2021], trend="none")
    assert res["n_obs"] == 2 * 8 * 14        # 2 treated seasons * 8 teams * 14 games


def test_report_selects_which_coefficient_is_headlined():
    panel = _synth(beta=3.0)
    base = fit(panel, "home_margin", "pooled", [2020, 2021])
    elo = fit(panel, "home_margin", "pooled", [2020, 2021], report="elo_diff")
    assert elo["coef"] == pytest.approx(base["coef_elo_diff"])
    assert elo["coef_crowd_pct"] == pytest.approx(base["coef"])   # roles swap
    assert elo["se"] > 0 and elo["ci_low"] < elo["coef"] < elo["ci_high"]


def test_extra_controls_duplicate_is_deduped():
    # C4: naming a control already in CONTROLS produced a duplicate column and
    # broke d[controls]. This phase adds callers, so it stops being latent.
    panel = _synth(beta=3.0)
    base = fit(panel, "home_margin", "pooled", [2020, 2021])
    dup = fit(panel, "home_margin", "pooled", [2020, 2021],
              extra_controls=["elo_diff"])
    assert dup["coef"] == pytest.approx(base["coef"])
    assert dup["n_obs"] == base["n_obs"]


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
