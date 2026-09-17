"""Phase 7 — sensitivity and pooling tables for the write-up.

Every number the paper cites that is NOT the frozen 6a/6b headline lives here,
as a CSV in results/tables/ rather than as prose. No new OUTCOME model: every
crowd-effect refit goes through twfe.fit. The only estimation here that is not
twfe.fit is the auxiliary collinearity regression in _collinearity_r2 (a plain
statsmodels OLS of crowd_pct on the FE, whose R^2 ships in a CSV) and the
pooling arithmetic in _meta. dose_overlap is pure description of the treatment
variable (no outcome touched at all); noise_floor is arithmetic over
season_effects' already-estimated coefficients.

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
  - The treatment is ~SEASON-level, so the effective number of independent
    treatment draws is the number of SEASONS (6), not the number of games.
    SEs clustered by home_team assume teams are independent WITHIN a season,
    which the treatment violates (one league-wide policy shock). season_effects
    and noise_floor exist to say what inference looks like once that is
    admitted. Clustering by season instead is NOT the fix (6 clusters is far
    below the ~40 cluster-robust variance estimation needs; the two-way attempt
    returns SMALLER SEs, which is the estimator breaking, not a correction).
"""
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy.stats import chi2

from src.features.build import _zero_config, null_reporting_zeros
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
    missing elo/rest/travel; null crowd_pct rows are dropped here too). Measured
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


def dose_overlap(panels=None) -> pd.DataFrame:
    """How separated is the treated crowd dose from ordinary-season variation?

    OUTCOME-BLIND BY CONSTRUCTION: reads crowd_pct and season only, never
    home_margin/home_win. That is what makes it a legitimate basis for treating
    a sport differently — the same standard the sport roster was closed on.

    `control_overlap` is the share of CONTROL-season games whose crowd_pct falls
    inside the treated 5-95% range. Near zero == a clean empty-vs-full natural
    experiment. Large == the treated dose is indistinguishable from ordinary
    demand variation, so the coefficient is identified off the endogenous
    channel the design exists to dodge (good teams draw crowds AND win).

    Measured (post zero-attendance fix): nfl 0.0%, nba 0.2%, nhl 0.4%, MLB 74.6%.
    MLB is the outlier, and the contamination is entirely 2021 (progressive
    reopening, mean .436): MLB 2020 alone is 100% empty and overlaps 0.0%. Per-year rows
    are emitted whenever a sport has >1 treated season, so the split is visible.

    CAVEAT that must travel with the MLB per-year rows: 2020 buys dose
    cleanliness and pays in confounding — it is also the ghost-runner /
    universal-DH / 7-inning-doubleheader / 60-game-regional season, several of
    which push HFA the home team's way. There is no MLB definition that is clean
    on both. See mlb_treated_split.

    NOTE (operationalisation): the design specifies the treatment as identified
    off POLICY CAPACITY CAPS; the code uses realised attendance / empirical
    capacity. Those coincide where caps bound (nfl/nba/nhl) and diverge where
    they do not (mlb, where realised attendance is mostly demand). This table is
    that gap made visible."""
    panels = panels if panels is not None else _load_panels()
    cfg = _cfg()
    rows = []
    for s in SPORTS:
        treated = cfg[s]["treated_seasons"]
        d = _prep(panels[s]).dropna(subset=["crowd_pct"])
        control = d[~d["season"].isin(treated)]["crowd_pct"]
        # "all_treated" is the headline definition; per-year rows only when the
        # sport has more than one treated season (otherwise they'd be duplicates).
        scopes = [("all_treated", treated)]
        if len(treated) > 1:
            scopes += [(str(y), [y]) for y in treated]
        for scope, yrs in scopes:
            trt = d[d["season"].isin(yrs)]["crowd_pct"]
            lo, hi = float(trt.quantile(0.05)), float(trt.quantile(0.95))
            rows.append({
                "sport": s, "scope": scope,
                "treated_mean": float(trt.mean()),
                "treated_p05": lo, "treated_p95": hi,
                "treated_share_zero": float((trt == 0).mean()),
                "control_mean": float(control.mean()),
                "control_p10": float(control.quantile(0.10)),
                "control_overlap": float(((control >= lo) & (control <= hi)).mean()),
                "n_treated": int(len(trt)), "n_control": int(len(control)),
            })
    out = pd.DataFrame(rows)
    TABLES.mkdir(parents=True, exist_ok=True)
    out.to_csv(TABLES / "dose_overlap.csv", index=False)
    return out


def leave_one_season_out(panels=None) -> pd.DataFrame:
    """Frozen spec, refit with one CONTROL season removed at a time.

    NOT a re-specification and NOT a search: the specification is untouched, only
    the sample varies, and every control season is dropped exactly once —
    exhaustively, with no choice to make and therefore nothing to fit to. The
    headline stays the all-seasons estimate in twfe_*.csv. Treated seasons are
    never dropped (that would change the treatment definition, not test
    stability).

    Measured: NFL is the fragile one — dropping 2018 alone takes win% +0.046 ->
    +0.010 and margin +1.71 -> +0.68, while no other season moves it by much.
    2018 is also NFL's largest season deviation in season_effects (+3.70 margin,
    double the treated season's -1.80), so the headline leans on an unusually
    high-HFA control year. mlb/nhl are stable; nba wobbles modestly on 2023.

    Read it with BOTH halves: this is partly genuine fragility and partly the
    mechanical property that dropping an endpoint of a 6-season panel tilts the
    linear trend (2018 is an endpoint). It does not make the NFL result "fake";
    it removes the last basis for calling it suggestive evidence.

    `delta_over_se_base` scales the movement by the headline SE, which stays
    interpretable where the base coefficient is ~0 (nhl) and a percent change
    would not."""
    panels = panels if panels is not None else _load_panels()
    cfg = _cfg()
    rows = []
    for s in SPORTS:
        treated = cfg[s]["treated_seasons"]
        panel = panels[s]
        for outcome in OUTCOMES:
            base = fit(panel, outcome, "pooled", treated)
            for s0 in sorted(panel["season"].unique()):
                if s0 in treated:
                    continue
                r = fit(panel[panel["season"] != s0], outcome, "pooled", treated)
                rows.append({
                    "sport": s, "outcome": outcome, "dropped_season": int(s0),
                    "coef": r["coef"], "se": r["se"],
                    "coef_base": base["coef"], "se_base": base["se"],
                    "delta": r["coef"] - base["coef"],
                    "delta_over_se_base": (r["coef"] - base["coef"]) / base["se"],
                    "n_obs": r["n_obs"], "n_obs_base": base["n_obs"],
                })
    out = pd.DataFrame(rows)
    TABLES.mkdir(parents=True, exist_ok=True)
    out.to_csv(TABLES / "leave_one_season_out.csv", index=False)
    return out


def _season_effect_fits(panel: pd.DataFrame, outcome: str, treated: list[int]) -> list[dict]:
    """One fit per season: that season's deviation from the team-FE + linear-trend
    baseline. crowd_pct is DROPPED (a full season dummy and a ~season-level dose
    are the same regressor twice), and seasons enter ONE AT A TIME (all of them
    at once is full season FE, which is collinear with the trend and is the
    degenerate spec 6a already rejected).

    The dummy is never null, so all seasons share one listwise sample and the
    coefficients are mutually comparable."""
    out = []
    for s0 in sorted(panel["season"].unique()):
        col = f"szn_{s0}"
        p = panel.copy()
        p[col] = (p["season"] == s0).astype(float)
        r = fit(p, outcome, "pooled", treated,
                drop_controls=["crowd_pct"], extra_controls=[col], report=col)
        out.append({"season": int(s0), "is_treated": s0 in treated,
                    "coef": r["coef"], "se": r["se"], "n_obs": r["n_obs"]})
    return out


def season_effects(panels=None) -> pd.DataFrame:
    """Every season's deviation from trend, plus a randomization-inference p.

    This is the honest inference for a treatment that varies at the season level
    (module docstring). Rather than trusting a game-clustered SE, ask directly:
    how unusual is the treated season among the seasons we observe? Each season
    in turn wears the treatment dummy; the real one either stands out or it does
    not.

    ri_pvalue = share of placebo seasons whose |deviation| is at least the
    treated season's (the more extreme of the two, for a sport with two treated
    seasons), with the standard +1/+1 correction.

    ⚠️ ri_pvalue_floor = 1/(1 + n_placebo) — with 6 seasons the SMALLEST
    achievable p-value is 0.167, so NO result this design can produce is capable
    of reaching 0.05 under randomization inference. That is not a defect of the
    calculation; it states how much information a 6-season panel holds about a
    season-level treatment. The consequence for the paper: report intervals and
    magnitudes, not p-values against a bar they cannot clear.

    Measured: nothing lands below 0.33. NFL 2018 (+3.70 margin) deviates twice
    as far as treated NFL 2020 (-1.80) — the ordinary season-to-season noise
    floor in home advantage exceeds the COVID signal.

    Two caveats: the permuted object is a season DUMMY, not the continuous dose
    (a continuous treatment cannot be meaningfully permuted across seasons), and
    the placebo distribution and the real estimate come from the same series.
    For a sport with 2 treated seasons the exact test would permute over all
    C(n,2) assignments; the reported value compares the more extreme treated
    year against the single-season placebo distribution."""
    panels = panels if panels is not None else _load_panels()
    cfg = _cfg()
    rows = []
    for s in SPORTS:
        treated = cfg[s]["treated_seasons"]
        for outcome in OUTCOMES:
            fits = _season_effect_fits(panels[s], outcome, treated)
            trt = [abs(f["coef"]) for f in fits if f["is_treated"]]
            plac = [abs(f["coef"]) for f in fits if not f["is_treated"]]
            ri = ((1 + sum(x >= max(trt) for x in plac)) / (1 + len(plac))
                  if trt and plac else float("nan"))
            for f in fits:
                rows.append({"sport": s, "outcome": outcome, **f,
                             "ri_pvalue": ri,
                             "ri_pvalue_floor": 1.0 / (1 + len(plac)) if plac else float("nan")})
    out = pd.DataFrame(rows)
    TABLES.mkdir(parents=True, exist_ok=True)
    out.to_csv(TABLES / "season_effects.csv", index=False)
    return out


def noise_floor(panels=None) -> pd.DataFrame:
    """The precision ceiling: how good could this design EVER get?

    Answers "would more control seasons buy a significant result?" — no. Two
    variance components bind, and NEITHER shrinks when control seasons are added:

      1. `treated_se` — the treated season's own sampling noise. 2020 happened
         once; you cannot collect more of it. (Inverse-variance combined when a
         sport has two treated seasons.)
      2. `sd_true` — genuine season-to-season variation in home advantage. Even
         knowing the long-run mean exactly, the treated season deviates from it
         at random, exactly as every other season does. Recovered by removing
         average sampling variance from the observed spread of season_effects:
         sd_true^2 = var(season coefs) - mean(se^2).

    floor = hypot(the two); mde_floor = 2.8 * floor (80% power, alpha .05);
    `ratio_floor` = mde_floor / that sport's total HFA. ratio >= 1 means an
    effect accounting for ALL of home advantage would still be undetectable.

    ⚠️ UNITS: everything here is on the SEASON-DUMMY (outcome-level) basis —
    margin points, or win-probability points — the same units as HFA. It is NOT
    the per-unit-crowd_pct basis that meta_cross_sport's `mde_80` uses. The two
    ratios are not interchangeable and must not be quoted side by side without
    saying which is which (that scaling confusion has bitten this project once).

    `mde_naive` is the same quantity computed as the shipped clustered SE would
    have it, i.e. ignoring sd_true. floor >= naive ALWAYS: admitting season-level
    shocks makes honest inference WORSE than the reported SE, which is the point
    of the module docstring's clustering note. `floor_over_naive` is how much.

    Measured: nfl's true between-season SD is 1.73 margin points — essentially
    the whole of its 1.75 average HFA — giving ratio_floor 3.23x (margin) /
    3.77x (win%). Extending the panel changes no conclusion, and would likely WORSEN
    randomization inference: more seasons lowers the 1/k floor but enlarges the
    reference distribution the treated season must beat, and NFL 2018 already
    out-deviates NFL 2020 two-to-one.

    `sd_true_censored` marks cells where observed spread fell below average
    sampling noise, so the decomposition clamped at zero. Read those as
    "between-season variation undetectably small", NOT "literally zero" — nhl
    and mlb are the sports where extra seasons would help most, and they are
    still at ~1.0.

    Conservative by construction: se(season dummy) includes uncertainty in the
    counterfactual as well as the treated season's own, so the floor is if
    anything overstated as achievable — i.e. the real ceiling is no better.

    HFA denominators come from viz.descriptive.summarize's pooled_fullcrowd row
    (one definition of HFA across the project). That row is not listwise-dropped
    on controls the way the fits are; the difference is immaterial at the two
    decimals the ratio is read to. This is the only function here that reaches
    outside src/models, so it needs a schema-complete panel — `covid_era` in
    particular, which summarize uses to choose the full-crowd seasons."""
    from src.viz.descriptive import summarize

    panels = panels if panels is not None else _load_panels()
    cfg = _cfg()
    rows = []
    for s in SPORTS:
        treated = cfg[s]["treated_seasons"]
        pooled = summarize(panels[s])
        hfa_row = pooled[pooled["season"] == "pooled_fullcrowd"].iloc[0]
        for outcome in OUTCOMES:
            fits = _season_effect_fits(panels[s], outcome, treated)
            coefs = np.array([f["coef"] for f in fits], float)
            ses = np.array([f["se"] for f in fits], float)
            sd_season = float(coefs.std(ddof=1))
            samp_var = float((ses**2).mean())
            sd_true = float(np.sqrt(max(sd_season**2 - samp_var, 0.0)))
            trt_ses = np.array([f["se"] for f in fits if f["is_treated"]], float)
            treated_se = float(np.sqrt(1.0 / (1.0 / trt_ses**2).sum()))
            floor = float(np.hypot(treated_se, sd_true))
            hfa = (float(hfa_row["mean_home_margin"]) if outcome == "home_margin"
                   else float(hfa_row["home_win_pct"]) - 0.5)
            rows.append({
                "sport": s, "outcome": outcome,
                "sd_season": sd_season, "mean_sampling_se": float(np.sqrt(samp_var)),
                "sd_true": sd_true, "sd_true_censored": sd_true == 0.0,
                "treated_se": treated_se, "floor": floor, "hfa": hfa,
                # naive == what the shipped clustered SE implies, ignoring
                # season-level shocks entirely. floor == the same thing once
                # sd_true is admitted. floor >= naive ALWAYS, by construction.
                "mde_naive": 2.8 * treated_se, "ratio_naive": 2.8 * treated_se / hfa,
                "mde_floor": 2.8 * floor, "ratio_floor": 2.8 * floor / hfa,
                "floor_over_naive": floor / treated_se,
            })
    out = pd.DataFrame(rows)
    TABLES.mkdir(parents=True, exist_ok=True)
    out.to_csv(TABLES / "noise_floor.csv", index=False)
    return out


def _n_nulled(sport: str) -> tuple[int, int]:
    """(fix-1 nulls outside every window, reopening-rule nulls inside windows), from data/interim."""
    c = _zero_config(sport)
    p = pd.read_parquet(f"data/interim/{sport}.parquet")
    n1 = null_reporting_zeros(p, c["zero_attendance_windows"])[1]
    n_all = null_reporting_zeros(p, c["zero_attendance_windows"], c["treated_seasons"],
                                 c["fans_from"], c["reclosures"])[1]
    return n1, n_all - n1


def _fix_sensitivity(pre_dir: Path, post_dir: Path, which: int, out_name: str) -> pd.DataFrame:
    keep = ["sport", "outcome", "coef", "se", "ci_low", "ci_high", "n_obs"]
    rows = []
    for s in SPORTS:
        pre = pd.read_csv(pre_dir / f"twfe_{s}.csv")
        post = pd.read_csv(post_dir / f"twfe_{s}.csv")
        pre, post = (d[d["sample"] == "pooled"][keep] for d in (pre, post))
        m = pre.merge(post, on=["sport", "outcome"], suffixes=("_pre", "_post"))
        m["n_nulled"] = _n_nulled(s)[which]
        rows.append(m)
    out = pd.concat(rows, ignore_index=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    out.to_csv(TABLES / out_name, index=False)
    return out


def zero_attendance_sensitivity(pre_dir: Path | None = None, post_dir: Path | None = None) -> pd.DataFrame:
    """Frozen 6a pooled estimates before vs after fix 1 (spec 2026-09-15). "After" is the state
    archived before the reopening fix, so this table does not move when later fixes land."""
    return _fix_sensitivity(pre_dir or TABLES / "pre_zero_fix", post_dir or TABLES / "pre_reopen_fix",
                            0, "zero_attendance_sensitivity.csv")


def reopen_zero_sensitivity(pre_dir: Path | None = None) -> pd.DataFrame:
    """Frozen 6a pooled estimates before vs after the reopening rule (spec 2026-09-16)."""
    return _fix_sensitivity(pre_dir or TABLES / "pre_reopen_fix", TABLES, 1,
                            "reopen_zero_sensitivity.csv")


def main() -> None:
    panels = _load_panels()
    meta = meta_cross_sport(panels)
    trend = trend_sensitivity(panels)
    season_fe = season_fe_sensitivity(panels)
    within = within_season_dose(panels)
    split = mlb_treated_split(panels)
    overlap = dose_overlap(panels)
    loso = leave_one_season_out(panels)
    seasons = season_effects(panels)
    floor = noise_floor(panels)
    zero_fix = zero_attendance_sensitivity()
    reopen_fix = reopen_zero_sensitivity()

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
    print("\n=== treated-vs-control dose overlap (outcome-blind) ===")
    print(overlap.to_string(index=False))
    print("NOTE: large control_overlap == the natural experiment barely applies "
          "to that sport; its coefficient rides on endogenous demand variation.")
    print("\n=== leave-one-control-season-out (frozen spec, sample only) ===")
    print(loso.to_string(index=False))
    print("\n=== season effects + randomization inference ===")
    print(seasons.to_string(index=False))
    print("NOTE: ri_pvalue_floor is the SMALLEST p this design can produce. "
          "Report intervals and magnitudes, not significance.")
    print("\n=== irreducible noise floor (infinite control seasons) ===")
    print(floor.to_string(index=False))
    print("NOTE: ratio_floor >= 1 means an effect the size of ALL of that sport's "
          "home advantage stays undetectable no matter how many seasons are added.")
    print("\n=== zero-attendance data correction: 6a pooled, pre vs post ===")
    print(zero_fix.to_string(index=False))
    print("\n=== reopening-rule zero correction: 6a pooled, pre vs post ===")
    print(reopen_fix.to_string(index=False))


if __name__ == "__main__":
    main()
