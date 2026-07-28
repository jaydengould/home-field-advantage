"""Phase 7 — sensitivity and pooling tables for the write-up.

Every number the paper cites that is NOT the frozen 6a/6b headline lives here,
as a CSV in results/tables/ rather than as prose. No new OUTCOME model: every
crowd-effect refit goes through twfe.fit. The only estimation here that is not
twfe.fit is the auxiliary collinearity regression in _collinearity_r2 (a plain
statsmodels OLS of crowd_pct on the FE, whose R^2 ships in a CSV) and the
pooling arithmetic in _meta.

READ BEFORE INTERPRETING (spec §6):
  - The four sports share a BIAS, not just independent noise. Each estimate is
    "crowd effect + that league's 2020-21 non-crowd home-specific shift".
    Inverse-variance pooling shrinks SAMPLING error as 1/sqrt(k) and does
    nothing to a common bias, so the pooled SE is a LOWER BOUND on real
    uncertainty. Never write "the pooled CI rules out effects larger than X".
  - At k=4 the heterogeneity test has no power (rejecting needs Q > 7.81).
    Absence of heterogeneity is NOT evidence of homogeneity.
  - RE intervals use the plain 1.96 normal approximation, which is known to be
    ANTICONSERVATIVE at small k (the Hartung-Knapp correction exists precisely
    for this) — another reason the pooled SE is a lower bound, not a real CI.
  - These are reported sensitivities. The main model is not re-specified.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy.stats import chi2

from src.models.twfe import CONTROLS, SPORTS, _prep, fit

OUTCOMES = ["home_margin", "home_win"]
TABLES = Path("results/tables")


def _cfg() -> dict:
    return yaml.safe_load(Path("config/sports.yaml").read_text())


def _load_panels() -> dict:
    return {s: pd.read_parquet(f"data/processed/{s}.parquet") for s in SPORTS}


def _meta(coefs: np.ndarray, ses: np.ndarray) -> dict:
    """Fixed-effect (inverse-variance) and random-effects (DerSimonian-Laird)
    pooling of k independent estimates. Returns a flat dict."""
    coefs, ses = np.asarray(coefs, float), np.asarray(ses, float)
    k = len(coefs)
    w = 1.0 / ses**2
    fe = float((w * coefs).sum() / w.sum())
    fe_se = float(np.sqrt(1.0 / w.sum()))
    q = float((w * (coefs - fe) ** 2).sum())
    df = k - 1
    tau2 = max(0.0, (q - df) / (w.sum() - (w**2).sum() / w.sum())) if df else 0.0
    ws = 1.0 / (ses**2 + tau2)
    return {
        "k": k,
        "fe_coef": fe,
        "fe_se": fe_se,
        "re_coef": float((ws * coefs).sum() / ws.sum()),
        "re_se": float(np.sqrt(1.0 / ws.sum())),
        "tau2": tau2,
        "q": q,
        "df": df,
        "q_pvalue": float(chi2.sf(q, df)) if df else float("nan"),
        # df==0 -> I^2 undefined (nan). df>=1 and q==0 exactly (perfect
        # homogeneity) -> I^2 = 0, the limit of (Q-df)/Q as Q->0; the bare
        # formula would ZeroDivisionError at q==0.0, hence the branch.
        "i2": float("nan") if not df else (0.0 if q == 0.0 else max(0.0, (q - df) / q)),
    }


def meta_cross_sport(panels=None) -> pd.DataFrame:
    """Pooled win-probability (LPM) crowd effect across sports, FE and RE.

    Two sets: all four sports, and the pre-NHL three-sport set, so the precision
    change from adding a sport is visible rather than asserted — sampling error
    only; see the module docstring on the shared bias. Per-sport input rows
    carry the 80%-power minimum detectable effect (2.8*SE), which is what the
    literature power comparison needs."""
    panels = panels if panels is not None else _load_panels()
    cfg = _cfg()
    per = [fit(panels[s], "home_win", "pooled", cfg[s]["treated_seasons"])
           for s in SPORTS]
    rows = [{"scope": "input", "sport": r["sport"], "coef": r["coef"], "se": r["se"],
             "mde_80": 2.8 * r["se"], "n_obs": r["n_obs"]} for r in per]

    sets = {"4sport": SPORTS, "3sport_ex_nhl": [s for s in SPORTS if s != "nhl"]}
    for name, members in sets.items():
        sub = [r for r in per if r["sport"] in members]
        m = _meta(np.array([r["coef"] for r in sub]),
                  np.array([r["se"] for r in sub]))
        for method in ("fe", "re"):
            rows.append({
                "scope": name, "method": method,
                "sport": "+".join(members),
                "coef": m[f"{method}_coef"], "se": m[f"{method}_se"],
                # 1.96 = normal-approx 95% CI; see module docstring (RE anticonservative at small k).
                "ci_low": m[f"{method}_coef"] - 1.96 * m[f"{method}_se"],
                "ci_high": m[f"{method}_coef"] + 1.96 * m[f"{method}_se"],
                "k": m["k"], "q": m["q"], "df": m["df"],
                "q_pvalue": m["q_pvalue"], "i2": m["i2"], "tau2": m["tau2"],
                "n_obs": sum(r["n_obs"] for r in sub),
            })
    out = pd.DataFrame(rows)
    TABLES.mkdir(parents=True, exist_ok=True)
    out.to_csv(TABLES / "meta_cross_sport.csv", index=False)
    return out


def trend_sensitivity(panels=None) -> pd.DataFrame:
    """Crowd coefficient under no / linear (shipped) / quadratic season trend.

    Pre-empts the first objection a referee raises: is the linear season_trend
    absorbing the treatment? Reported for every sport and both outcomes."""
    panels = panels if panels is not None else _load_panels()
    cfg = _cfg()
    rows = []
    for s in SPORTS:
        for outcome in OUTCOMES:
            for trend in ("none", "linear", "quadratic"):
                r = fit(panels[s], outcome, "pooled",
                        cfg[s]["treated_seasons"], trend=trend)
                rows.append({k: r[k] for k in
                             ("sport", "outcome", "trend", "coef", "se",
                              "ci_low", "ci_high", "pvalue", "n_obs")})
    out = pd.DataFrame(rows)
    TABLES.mkdir(parents=True, exist_ok=True)
    out.to_csv(TABLES / "trend_sensitivity.csv", index=False)
    return out


def _collinearity_r2(panel: pd.DataFrame) -> float:
    """R^2 of crowd_pct ~ C(season) + C(home_team) on the estimation sample.

    The rebuttal that must sit NEXT TO the season-FE coefficient: the higher
    this is, the more of the crowd dose full season dummies absorb, and the
    less the season-FE coefficient means.

    Computed on the exclusion-filtered panel (_prep output), NOT on the same
    listwise-dropna sample `fit()` estimates on (that sample also drops rows
    missing elo/rest/travel, which crowd_pct itself never is). Measured
    difference is <=0.003 R^2 for all four sports -- invisible at the two
    decimals the paper cites, and it doesn't disturb the NFL > NBA > NHL > MLB
    ordering the argument relies on. An exact match isn't achievable anyway:
    a single sport's two outcomes already have different fit samples (NFL
    home_margin n=1463 vs home_win n=1459), so there is no one "the" fit
    sample for this function to match."""
    import statsmodels.formula.api as smf

    d = _prep(panel)[["crowd_pct", "season", "home_team"]].dropna()
    return float(smf.ols("crowd_pct ~ C(season) + C(home_team)", data=d).fit().rsquared)


def season_fe_sensitivity(panels=None) -> pd.DataFrame:
    """Crowd coefficient under FULL season FE, beside the shipped spec and the
    collinearity R^2.

    NOT an alternative headline. Under full season FE the coefficient is
    identified off WITHIN-normal-season crowd variation, which is demand-driven
    (good teams draw crowds AND win) — precisely the endogeneity the design
    exists to dodge. Report the sensitivity WITH this rebuttal, never alone."""
    panels = panels if panels is not None else _load_panels()
    cfg = _cfg()
    rows = []
    for s in SPORTS:
        r2 = _collinearity_r2(panels[s])
        for outcome in OUTCOMES:
            base = fit(panels[s], outcome, "pooled", cfg[s]["treated_seasons"])
            fe = fit(panels[s], outcome, "pooled", cfg[s]["treated_seasons"],
                     season_fe=True, trend="none")
            rows.append({
                "sport": s, "outcome": outcome,
                "coef_shipped": base["coef"], "se_shipped": base["se"],
                "coef_season_fe": fe["coef"], "se_season_fe": fe["se"],
                "ci_low_season_fe": fe["ci_low"], "ci_high_season_fe": fe["ci_high"],
                "pvalue_season_fe": fe["pvalue"],
                "collinearity_r2": r2,
                "n_obs": fe["n_obs"],
            })
    out = pd.DataFrame(rows)
    TABLES.mkdir(parents=True, exist_ok=True)
    out.to_csv(TABLES / "season_fe_sensitivity.csv", index=False)
    return out


def _dose_fit_sample(panel: pd.DataFrame, outcome: str, treated: list[int],
                      extra_controls: tuple) -> pd.DataFrame:
    """Rebuild the exact row set `fit()` estimates on: _prep + treated-season
    filter + listwise dropna over outcome/CONTROLS/extra_controls, mirroring
    fit()'s own sample construction verbatim (not a second estimator, just the
    same row-selection resolved twice, same as fit() already does internally).

    Basis note (mirrors the pattern _collinearity_r2 documents above): the raw
    empty/fans means exist to be compared against the adjusted coefficient, so
    they must sit on the SAME sample fit() used, not the broader exclusion-only
    sample -- otherwise the "raw vs adjusted" comparison isn't attributable to
    adjustment. crowd_min/max/p99 intentionally stay on the broader exclusion-
    only sample (the support range question is "what doses exist at all",
    independent of which controls happen to be non-null that game)."""
    controls = list(dict.fromkeys(CONTROLS + list(extra_controls)))
    d = _prep(panel)
    d = d[d["season"].isin(treated)]
    d = d[[outcome] + controls].copy()
    d[outcome] = d[outcome].astype(float)
    d[controls] = d[controls].astype(float)
    return d.dropna()


def within_season_dose(panels=None) -> pd.DataFrame:
    """Crowd dose estimated WITHIN the treated season(s) only, all four sports.

    This design is endogenous and uninformative, and that is the finding: in
    2020-21 within-team fan access is confounded with calendar time (venues
    reopened progressively, so "more fans" ~= "later in the season"), and the
    fitted support is far short of 1.0, so a crowd_pct slope extrapolates. In
    BOTH NHL and MLB the raw means run one way and the team-FE estimate the
    other (NHL raw +0.297 vs coef -1.414; MLB raw +0.020 vs coef -0.350) — that
    sign opposition reproducing across two sports IS the endogeneity lesson, not
    two anomalies. Reported for all four sports so it is a comparison rather
    than an anecdote. Every row carries its support range.

    raw_empty_mean/raw_fans_mean/n_empty/n_fans are computed on fit()'s own
    estimation sample (see _dose_fit_sample), not the broader exclusion-only
    sample, so n_empty + n_fans == n_obs and the raw contrast is comparable to
    the adjusted coefficient. crowd_min/max/p99 stay on the broader sample."""
    panels = panels if panels is not None else _load_panels()
    cfg = _cfg()
    rows = []
    for s in SPORTS:
        treated = cfg[s]["treated_seasons"]
        panel = panels[s].copy()
        extra = ()
        if len(treated) > 1:
            # pool the treated seasons but let each have its own level
            panel["treated_season_dummy"] = (panel["season"] != min(treated)).astype(float)
            extra = ("treated_season_dummy",)
        d = _prep(panel)
        d = d[d["season"].isin(treated)]
        for outcome in OUTCOMES:
            r = fit(panel, outcome, "treated", treated, trend="none",
                    extra_controls=extra)
            fit_d = _dose_fit_sample(panel, outcome, treated, extra)
            empty = fit_d[fit_d["crowd_pct"] == 0]
            fans = fit_d[fit_d["crowd_pct"] > 0]
            rows.append({
                "sport": s, "outcome": outcome,
                "coef": r["coef"], "se": r["se"], "ci_low": r["ci_low"],
                "ci_high": r["ci_high"], "pvalue": r["pvalue"],
                "n_obs": r["n_obs"], "n_entities": r["n_entities"],
                "n_treated_seasons": len(treated),
                "coef_treated_season_dummy": r.get("coef_treated_season_dummy", float("nan")),
                "crowd_min": float(d["crowd_pct"].min()),
                "crowd_max": float(d["crowd_pct"].max()),
                "crowd_p99": float(d["crowd_pct"].quantile(0.99)),
                "raw_empty_mean": float(empty[outcome].mean()) if len(empty) else float("nan"),
                "n_empty": int(len(empty)),
                "raw_fans_mean": float(fans[outcome].mean()) if len(fans) else float("nan"),
                "n_fans": int(len(fans)),
            })
    out = pd.DataFrame(rows)
    TABLES.mkdir(parents=True, exist_ok=True)
    out.to_csv(TABLES / "within_season_dose.csv", index=False)
    return out


def mlb_treated_split(panels=None) -> pd.DataFrame:
    """MLB 2020 and 2021 as separate treatment indicators.

    2020 carried more home-relevant rule changes than any other season (extra-
    innings ghost runner, universal DH, seven-inning doubleheaders, regional
    60-game schedule), several pushing HFA the home team's way. If MLB's faint
    wrong sign lives entirely in 2020, that points at a rule artifact rather
    than a crowd effect. Suggestive only — it cannot separate the two.

    Sign convention: NOT 6b's `crowd_effect` convention (did.py negates the
    reduced-season coefficient so positive == crowd helps the home team). This
    table reports the raw treated-year level, unnegated. Positive here means
    home margin was HIGHER that year, i.e. the crowd effect implied is
    NEGATIVE -- the opposite reading from 6b's sign."""
    panels = panels if panels is not None else _load_panels()
    treated = _cfg()["mlb"]["treated_seasons"]
    panel = panels["mlb"].copy()
    indicators = []
    for y in treated:
        col = f"treated_{y}"
        panel[col] = (panel["season"] == y).astype(float)
        indicators.append(col)

    rows = []
    for outcome in OUTCOMES:
        for y, col in zip(treated, indicators):
            # Two fit() calls, ONE regression: both year indicators are in the
            # regressor set every time (crowd_pct dropped, both dummies added),
            # so the two calls estimate the identical model -- report= just
            # selects which of the two already-estimated coefficients comes
            # back as `coef`. Not a redundant refit of two different specs.
            r = fit(panel, outcome, "pooled", treated,
                    drop_controls=["crowd_pct"], extra_controls=indicators,
                    report=col)
            rows.append({
                "sport": "mlb", "outcome": outcome, "treated_year": y,
                "coef": r["coef"], "se": r["se"], "ci_low": r["ci_low"],
                "ci_high": r["ci_high"], "pvalue": r["pvalue"], "n_obs": r["n_obs"],
            })
    out = pd.DataFrame(rows)
    TABLES.mkdir(parents=True, exist_ok=True)
    out.to_csv(TABLES / "mlb_treated_split.csv", index=False)
    return out


def main() -> None:
    panels = _load_panels()
    meta = meta_cross_sport(panels)
    trend = trend_sensitivity(panels)
    season_fe = season_fe_sensitivity(panels)
    within = within_season_dose(panels)
    split = mlb_treated_split(panels)

    print("\n=== pooled cross-sport (win%, LPM) ===")
    print(meta[meta["scope"] != "input"][
        ["scope", "method", "coef", "se", "ci_low", "ci_high", "q", "q_pvalue", "i2", "tau2"]
    ].to_string(index=False))
    print("NOTE: the sports share a bias, not just noise — this SE is a lower bound.")
    print("\n=== trend sensitivity ===")
    print(trend.to_string(index=False))
    print("\n=== full season FE (with the collinearity rebuttal alongside) ===")
    print(season_fe.to_string(index=False))
    print("\n=== within-treated-season dose (endogenous; note the support range) ===")
    print(within.to_string(index=False))
    print("\n=== MLB treated-season split ===")
    print(split.to_string(index=False))
    print("NOTE: suggestive only -- cannot separate 2020's rule changes from crowd effects.")


if __name__ == "__main__":
    main()
