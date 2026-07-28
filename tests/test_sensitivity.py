import numpy as np
import pytest

from src.models.sensitivity import (_collinearity_r2, _meta, season_fe_sensitivity,
                                    trend_sensitivity)
from tests.test_twfe import _synth


def test_meta_homogeneous_case_collapses_re_to_fe():
    # Hand-worked: theta=[0,1], se=[1,1] -> w=[1,1], FE=0.5, SE=1/sqrt(2)
    # Q = 1*(0.5)^2 + 1*(0.5)^2 = 0.5 < df=1 -> tau2 = 0 -> RE must equal FE.
    m = _meta(np.array([0.0, 1.0]), np.array([1.0, 1.0]))
    assert m["fe_coef"] == pytest.approx(0.5)
    assert m["fe_se"] == pytest.approx(1 / np.sqrt(2))
    assert m["q"] == pytest.approx(0.5)
    assert m["df"] == 1
    assert m["tau2"] == pytest.approx(0.0)
    assert m["i2"] == pytest.approx(0.0)
    assert m["re_coef"] == pytest.approx(m["fe_coef"])
    assert m["re_se"] == pytest.approx(m["fe_se"])


def test_meta_heterogeneous_case_matches_hand_worked_dl():
    # theta=[0,4], se=[1,1]: FE=2, Q=4+4=8, df=1,
    # tau2 = (Q-df)/(sum_w - sum_w2/sum_w) = 7/(2 - 2/2) = 7
    # w* = 1/(1+7) = 0.125 each -> RE=2, RE_SE = 1/sqrt(0.25) = 2
    # I2 = (8-1)/8 = 0.875
    m = _meta(np.array([0.0, 4.0]), np.array([1.0, 1.0]))
    assert m["fe_coef"] == pytest.approx(2.0)
    assert m["q"] == pytest.approx(8.0)
    assert m["tau2"] == pytest.approx(7.0)
    assert m["re_coef"] == pytest.approx(2.0)
    assert m["re_se"] == pytest.approx(2.0)
    assert m["i2"] == pytest.approx(0.875)
    assert m["re_se"] > m["fe_se"]      # RE is wider when tau2 > 0
    # Upper tail (chi2.sf), not cdf: swapping tails would give 0.9953, which
    # is a perfectly plausible-looking number too — pin the correct one.
    assert m["q_pvalue"] == pytest.approx(0.004678, rel=1e-3)


def test_meta_unequal_weights_favour_the_precise_estimate():
    # The precise study (se=0.1) must dominate the imprecise one (se=1.0).
    # w = [100, 1] -> fe = 100*0/101 + 1*1/101 = 1/101 exactly.
    m = _meta(np.array([0.0, 1.0]), np.array([0.1, 1.0]))
    assert m["fe_coef"] == pytest.approx(1 / 101)
    assert m["k"] == 2


def test_meta_single_estimate_i2_is_nan_not_one():
    # k=1 -> df=0 -> I^2 is undefined (not the misleading "100% heterogeneity").
    # q_pvalue is already nan at df=0; i2 must match that convention.
    m = _meta(np.array([2.5]), np.array([0.7]))
    assert m["k"] == 1
    assert m["df"] == 0
    assert np.isnan(m["i2"])
    assert np.isnan(m["q_pvalue"])
    assert m["re_coef"] == pytest.approx(m["fe_coef"])  # tau2=0 -> RE collapses to FE


def test_meta_perfect_homogeneity_i2_is_zero_not_nan():
    # df>=1 and q==0 exactly (two identical estimates, identical SEs) is the
    # degenerate case the (q>0) guard mishandled: limit of (Q-df)/Q as Q->0 is 0,
    # not nan. q_pvalue must correspondingly be a real 1.0 (chi2.sf(0, df)).
    m = _meta(np.array([1.0, 1.0]), np.array([0.5, 0.5]))
    assert m["q"] == pytest.approx(0.0)
    assert m["df"] == 1
    assert m["i2"] == pytest.approx(0.0)
    assert m["q_pvalue"] == pytest.approx(1.0)


def _panels():
    """Two-sport synthetic stand-in for the real processed parquets.

    Injects 40 NaNs into nfl's away_travel_km: _synth is otherwise NaN-free, and
    fit()'s dropna column set doesn't depend on `trend`, so on a clean fixture
    the n_obs.nunique()==1 sample-integrity check below would pass under ANY
    implementation (even a broken one) — vacuous. The injected NaNs give the
    listwise dropna something to actually drop consistently across trend specs,
    matching the standard tests/test_twfe.py:146-158 already sets."""
    a = _synth(beta=3.0, seed=0); a["sport"] = "nfl"
    a.loc[a.index[:40], "away_travel_km"] = np.nan
    b = _synth(beta=1.0, seed=1); b["sport"] = "nba"
    return {"nfl": a, "nba": b}


def test_trend_sensitivity_covers_every_sport_outcome_and_trend(monkeypatch, tmp_path):
    import src.models.sensitivity as sens
    monkeypatch.setattr(sens, "SPORTS", ["nfl", "nba"])
    monkeypatch.setattr(sens, "TABLES", tmp_path)
    monkeypatch.setattr(sens, "_cfg", lambda: {"nfl": {"treated_seasons": [2020, 2021]},
                                               "nba": {"treated_seasons": [2020, 2021]}})
    panels = _panels()
    out = sens.trend_sensitivity(panels)
    assert set(out["trend"]) == {"none", "linear", "quadratic"}
    assert len(out) == 2 * 2 * 3                     # sport x outcome x trend
    assert (tmp_path / "trend_sensitivity.csv").exists()
    # sample integrity: the three trend specs must use the SAME rows, or the
    # coefficient comparison is not a comparison of specifications. Relative
    # (nunique==1) alone is insufficient -- a uniform dropna bug would still
    # pass it -- so also pin the absolute count, matching the standard
    # tests/test_twfe.py:131-133 sets (n_obs == fixture rows minus injected NaNs).
    expected_n_obs = {"nfl": len(panels["nfl"]) - 40, "nba": len(panels["nba"])}
    for (sport, outcome), g in out.groupby(["sport", "outcome"]):
        assert g["n_obs"].nunique() == 1, (sport, outcome)
        assert g["n_obs"].iloc[0] == expected_n_obs[sport], (sport, outcome)


def test_season_fe_sensitivity_reports_coef_and_collinearity_r2(monkeypatch, tmp_path):
    import src.models.sensitivity as sens
    monkeypatch.setattr(sens, "SPORTS", ["nfl", "nba"])
    monkeypatch.setattr(sens, "TABLES", tmp_path)
    monkeypatch.setattr(sens, "_cfg", lambda: {"nfl": {"treated_seasons": [2020, 2021]},
                                               "nba": {"treated_seasons": [2020, 2021]}})
    out = sens.season_fe_sensitivity(_panels())
    assert len(out) == 2 * 2                          # sport x outcome
    assert {"coef_season_fe", "coef_shipped", "collinearity_r2"} <= set(out.columns)
    assert out["collinearity_r2"].between(0, 1).all()
    assert (tmp_path / "season_fe_sensitivity.csv").exists()
    # between(0, 1) is satisfied by a `return 1.0` stub -- pin a real, non-trivial
    # value: unmodified _synth's season-locked-ish base + per-team jitter measures
    # ~0.4869, well clear of both endpoints.
    assert _collinearity_r2(_synth()) < 0.9


def test_collinearity_r2_is_one_when_crowd_is_season_locked():
    # A crowd dose that is a pure function of season is perfectly explained by
    # season dummies -> R^2 == 1. This is the degenerate case the 6a design
    # argues NFL is close to (measured .974).
    df = _synth(games=3)
    df["crowd_pct"] = df["season"].map({2018: 0.9, 2019: 0.9, 2020: 0.1, 2021: 0.1})
    assert _collinearity_r2(df) == pytest.approx(1.0, abs=1e-6)


def test_within_season_dose_uses_only_treated_season_rows(monkeypatch, tmp_path):
    import src.models.sensitivity as sens
    monkeypatch.setattr(sens, "SPORTS", ["nfl"])
    monkeypatch.setattr(sens, "TABLES", tmp_path)
    monkeypatch.setattr(sens, "_cfg", lambda: {"nfl": {"treated_seasons": [2020]}})
    panel = _synth(beta=3.0); panel["sport"] = "nfl"
    out = sens.within_season_dose({"nfl": panel})

    # Sample integrity: n_obs must equal the directly-computed treated-season count.
    expected = int(((panel["season"] == 2020)).sum())
    assert set(out["n_obs"]) == {expected}
    assert set(out["outcome"]) == {"home_margin", "home_win"}
    # the support range must ship with the coefficient: a crowd_pct slope fitted
    # on 0-0.40 extrapolates 2.5x to reach 1.0, and the range is the caveat.
    assert (out["crowd_max"] <= 1.0).all() and (out["crowd_min"] >= 0.0).all()
    assert {"raw_empty_mean", "raw_fans_mean", "n_empty", "n_fans"} <= set(out.columns)
    assert (tmp_path / "within_season_dose.csv").exists()


def test_within_season_dose_pools_mlbs_two_treated_seasons_with_a_dummy(monkeypatch, tmp_path):
    import src.models.sensitivity as sens
    monkeypatch.setattr(sens, "SPORTS", ["mlb"])
    monkeypatch.setattr(sens, "TABLES", tmp_path)
    monkeypatch.setattr(sens, "_cfg", lambda: {"mlb": {"treated_seasons": [2020, 2021]}})
    panel = _synth(beta=3.0); panel["sport"] = "mlb"
    out = sens.within_season_dose({"mlb": panel})
    assert set(out["n_obs"]) == {int(panel["season"].isin([2020, 2021]).sum())}
    assert out["n_treated_seasons"].eq(2).all()      # dummy path taken
    # notna, not just "column exists": the column is inserted unconditionally
    # via r.get(..., nan), so an implementation that never builds a dummy would
    # still have the column (all-NaN) and pass a mere `in out.columns` check.
    assert out["coef_treated_season_dummy"].notna().all()


def test_within_season_dose_empty_plus_fans_reconciles_with_n_obs(monkeypatch, tmp_path):
    import src.models.sensitivity as sens
    monkeypatch.setattr(sens, "SPORTS", ["nfl"])
    monkeypatch.setattr(sens, "TABLES", tmp_path)
    monkeypatch.setattr(sens, "_cfg", lambda: {"nfl": {"treated_seasons": [2020]}})
    panel = _synth(beta=3.0); panel["sport"] = "nfl"
    # NaNs INSIDE the treated season. _synth is otherwise NaN-free, so with
    # nothing for the listwise dropna to remove the reconciliation below would
    # hold even under a _dose_fit_sample that skipped dropna entirely -- vacuous.
    treated_idx = panel.index[panel["season"] == 2020]
    panel.loc[treated_idx[:25], "away_travel_km"] = np.nan
    out = sens.within_season_dose({"nfl": panel})

    # THE INVARIANT: the raw empty/fans means must be computed on fit()'s own
    # estimation sample, or the "raw vs adjusted" contrast is a sample
    # difference rather than an adjustment effect. _dose_fit_sample
    # re-implements fit()'s row selection, so a future change to fit()'s dropna
    # set would silently desynchronise the two with a green suite otherwise.
    assert (out["n_empty"] + out["n_fans"] == out["n_obs"]).all()
    assert out["n_obs"].eq(int((panel["season"] == 2020).sum()) - 25).all()
    assert (out["n_empty"] > 0).all() and (out["n_fans"] > 0).all()   # both sides populated


def test_mlb_treated_split_reports_each_year_separately(monkeypatch, tmp_path):
    import src.models.sensitivity as sens
    monkeypatch.setattr(sens, "TABLES", tmp_path)
    monkeypatch.setattr(sens, "_cfg", lambda: {"mlb": {"treated_seasons": [2020, 2021]}})
    panel = _synth(beta=3.0); panel["sport"] = "mlb"
    out = sens.mlb_treated_split({"mlb": panel})
    assert set(out["treated_year"]) == {2020, 2021}
    assert len(out) == 4                              # 2 years x 2 outcomes
    assert out["se"].gt(0).all()
    assert (tmp_path / "mlb_treated_split.csv").exists()
