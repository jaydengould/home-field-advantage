"""Phase 6a — sport-blind TWFE dose-response causal engine.

Estimates the crowd-attributable slice of home-field advantage:
    outcome ~ crowd_pct + elo_diff + rest_diff + away_travel_km + season_trend
             + EntityEffects(home_team)
run per sport, for two outcomes (home_margin, home_win-as-LPM) and two samples
(pooled headline, restricted robustness check). SEs clustered by home_team.

NOTE (identification): the COVID crowd shock is ~a pure season-level treatment
(crowd_pct ~0.97 every normal season, ~0.07 in the treated one), so FULL season
fixed effects are near-collinear with crowd_pct and absorb the between-season
contrast that IS the natural experiment -> the coef inverts to a meaningless
large negative. We therefore use team (entity) FE only, plus a LINEAR season
trend to guard secular league drift while leaving the sharp COVID contrast to
identify crowd_pct. See docs/superpowers/specs/2026-07-20-phase6a-twfe-design.md.
"""
from pathlib import Path

import pandas as pd
import yaml
from linearmodels import PanelOLS

import matplotlib

matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt  # noqa: E402

SPORTS = ["nfl", "mlb", "nba", "nhl"]
TREATMENT = "crowd_pct"
CONTROLS = ["crowd_pct", "elo_diff", "rest_diff", "away_travel_km"]
# Custom categorical palette, validator-checked for contrast + CVD pairwise
# separation (not the dataviz skill's documented slots — see the comment in
# src/viz/descriptive.py for why). Must stay identical to that module's
# SPORT_COLORS. MARKERS gives each sport a distinct shape too.
SPORT_COLORS = {"nfl": "#2a78d6", "mlb": "#008300", "nba": "#a4036f", "nhl": "#e42800"}
MARKERS = {"nfl": "o", "mlb": "s", "nba": "^", "nhl": "D"}


def _restricted_seasons(treated: list[int]) -> set[int]:
    """Treated window bracketed by one adjacent season each side (baseline +
    reversion anchor). e.g. [2020,2021] -> {2019,2020,2021,2022}."""
    return set(treated) | {min(treated) - 1, max(treated) + 1}


def _exclusion_mask(panel: pd.DataFrame) -> pd.Series:
    """Games dropped from every causal model: neutral/relocated/bubble/playoff.
    Single source of truth shared by 6a (twfe) and 6b (did)."""
    return (
        panel["neutral_site"].fillna(False)
        | panel["relocated_home"].fillna(False)
        | panel["is_bubble"].fillna(False)
        | panel["is_playoff"].fillna(False)
    )


def _prep(panel: pd.DataFrame) -> pd.DataFrame:
    """Drop excluded games and add the two derived diff controls. Sport-blind."""
    df = panel[~_exclusion_mask(panel)].copy()
    df["elo_diff"] = df["home_elo"] - df["away_elo"]
    # rest_days are nullable Int64 (first game of season = NA) -> Float64, listwise-dropped in fit
    df["rest_diff"] = df["home_rest_days"] - df["away_rest_days"]
    return df


def fit(panel, outcome, sample="pooled", treated_seasons=None, extra_controls=(),
        drop_controls=(), trend="linear", season_fe=False, report=None):
    """Fit the TWFE spec for one sport/outcome/sample. Pure (no disk/net).

    outcome in {"home_margin", "home_win"}; home_win runs as a linear
    probability model (0/1). Returns a flat dict of the reported coefficient
    with cluster-robust SE/CI plus the other regressors' coefficients.

    drop_controls removes named controls from the default set (the symmetric
    counterpart to extra_controls); used by the NHL travel-confound diagnostic.

    trend / season_fe / report / sample="treated" exist for Phase 7's
    sensitivity table. Their DEFAULTS reproduce the frozen 6a specification
    exactly — do not change the defaults.
    """
    if season_fe and trend != "none":
        raise ValueError("season_fe=True requires trend='none' (a linear trend "
                         "is collinear with full season dummies)")
    sport = panel["sport"].iloc[0]
    df = _prep(panel)
    if sample == "restricted":
        df = df[df["season"].isin(_restricted_seasons(treated_seasons))]
    elif sample == "treated":
        df = df[df["season"].isin(treated_seasons)]

    # dict.fromkeys de-dupes while preserving order: an extra_control naming an
    # existing control would otherwise duplicate the column and break d[controls].
    controls = list(dict.fromkeys(
        [c for c in CONTROLS if c not in drop_controls] + list(extra_controls)))
    d = df[[outcome, "home_team", "season"] + controls].copy()
    d[outcome] = d[outcome].astype(float)          # bool/int/Int64 -> float (LPM safe)
    d[controls] = d[controls].astype(float)
    n_pre = len(d)
    d = d.dropna()                                  # listwise: first-game rest, missing travel/spread
    n_dropped = n_pre - len(d)                       # visible sample loss (first-game rest, etc.)

    # Linear season trend instead of full season FE (see module docstring):
    # season dummies are near-collinear with the time-clustered crowd shock and
    # would absorb the natural experiment; a linear trend only nets out drift.
    d["season_trend"] = (d["season"] - d["season"].min()).astype(float)
    d["season_trend_sq"] = d["season_trend"] ** 2
    trend_map = {"none": [], "linear": ["season_trend"],
                 "quadratic": ["season_trend", "season_trend_sq"]}
    if trend not in trend_map:
        raise ValueError(f"trend must be one of {list(trend_map)}, got {trend!r}")
    regressors = controls + trend_map[trend]

    d = d.set_index(["home_team", "season"])
    res = PanelOLS(
        d[outcome], d[regressors], entity_effects=True, time_effects=season_fe
    ).fit(cov_type="clustered", cluster_entity=True)
    ci = res.conf_int()
    key = report or TREATMENT
    if key not in regressors:
        raise ValueError(f"report must be one of {regressors}, got {key!r}")
    out = {
        "sport": sport, "outcome": outcome, "sample": sample,
        "trend": trend, "season_fe": season_fe, "reported": key,
        "coef": float(res.params[key]),
        "se": float(res.std_errors[key]),
        "ci_low": float(ci.loc[key, "lower"]),
        "ci_high": float(ci.loc[key, "upper"]),
        "pvalue": float(res.pvalues[key]),
        "n_obs": int(res.nobs),
        "n_dropped": int(n_dropped),
        "n_entities": int(d.index.get_level_values(0).nunique()),
    }
    out.update({f"coef_{c}": float(res.params[c]) for c in regressors if c != key})
    return out


def plot_effect(results: pd.DataFrame) -> plt.Figure:
    """Forest plot of the crowd_pct coefficient (with CI) per sport, faceted by
    outcome, pooled vs restricted. One row of dots per (sport, outcome, sample)."""
    outcomes = list(results["outcome"].unique())
    fig, axes = plt.subplots(1, len(outcomes), figsize=(5 * len(outcomes), 5), squeeze=False)
    for ax, outcome in zip(axes[0], outcomes):
        sub = results[results["outcome"] == outcome].copy()
        sub = sub.sort_values(["sport", "sample"]).reset_index(drop=True)
        for y, r in sub.iterrows():
            ax.errorbar(
                r["coef"], y,
                xerr=[[r["coef"] - r["ci_low"]], [r["ci_high"] - r["coef"]]],
                marker=MARKERS.get(r["sport"], "o"), linestyle="none",
                color=SPORT_COLORS.get(r["sport"], "gray"), capsize=3,
            )
        ax.set_yticks(range(len(sub)))
        ax.set_yticklabels([f"{r['sport']}·{r['sample']}" for _, r in sub.iterrows()])
        ax.axvline(0, ls="--", color="gray", lw=1)
        ax.set_title(outcome)
        ax.set_xlabel("crowd_pct coefficient (empty→full)")
    fig.suptitle("Crowd effect on home advantage (team FE + linear trend, 95% CI)")
    fig.tight_layout()
    return fig


def main() -> None:
    cfg = yaml.safe_load(Path("config/sports.yaml").read_text())
    panels = {s: pd.read_parquet(f"data/processed/{s}.parquet") for s in SPORTS}
    rows = []
    for s in SPORTS:
        treated = cfg[s]["treated_seasons"]
        for outcome in ["home_margin", "home_win"]:
            for sample in ["pooled", "restricted"]:
                rows.append(fit(panels[s], outcome, sample, treated))
    results = pd.DataFrame(rows)

    Path("results/tables").mkdir(parents=True, exist_ok=True)
    Path("results/figures").mkdir(parents=True, exist_ok=True)
    for s in SPORTS:
        results[results["sport"] == s].to_csv(f"results/tables/twfe_{s}.csv", index=False)
    # cross-sport comparison = the LPM win-probability effect (margin isn't cross-sport comparable)
    cross = results[results["outcome"] == "home_win"].copy()
    cross.to_csv("results/tables/twfe_cross_sport.csv", index=False)

    # NFL-only sensitivity: does adding the betting spread move the crowd coef?
    sens = fit(panels["nfl"], "home_margin", "pooled",
               cfg["nfl"]["treated_seasons"], extra_controls=["closing_spread"])
    base_mask = ((results["sport"] == "nfl") & (results["outcome"] == "home_margin")
                 & (results["sample"] == "pooled"))
    base_coef = results.loc[base_mask, "coef"].iloc[0]
    print(f"[NFL sensitivity] +closing_spread: crowd coef {sens['coef']:.3f} "
          f"(base {base_coef:.3f})")

    # NHL-only diagnostic: the 2020-21 season ran realigned regional divisions
    # (incl. an all-Canadian division), so crowd and travel fell together. Measure
    # the confound rather than assume away_travel_km absorbs it. Reported either way.
    nhl = _prep(panels["nhl"])
    treated_nhl = cfg["nhl"]["treated_seasons"]
    t = nhl[nhl["season"].isin(treated_nhl)][["crowd_pct", "away_travel_km"]].dropna()
    rho = float(t["crowd_pct"].corr(t["away_travel_km"])) if len(t) > 2 else float("nan")

    diag_rows = []
    for outcome in ["home_margin", "home_win"]:
        base = next(r for r in rows if r["sport"] == "nhl"
                    and r["outcome"] == outcome and r["sample"] == "pooled")
        drop = fit(panels["nhl"], outcome, "pooled", treated_nhl,
                   drop_controls=["away_travel_km"])
        diag_rows.append({
            "outcome": outcome,
            "corr_crowd_travel_treated": rho,
            "coef_with_travel": base["coef"],
            "coef_without_travel": drop["coef"],
            "delta": drop["coef"] - base["coef"],
            # n_obs for BOTH fits: dropping a control also drops it from dropna(), so
            # an unequal sample would let a sample shift masquerade as a coef shift.
            # These must match; if they do not, the diagnostic is not interpretable.
            "n_obs_with_travel": base["n_obs"],
            "n_obs_without_travel": drop["n_obs"],
        })
        print(f"[NHL travel diagnostic] {outcome}: corr(crowd,travel|treated)={rho:+.3f} "
              f"coef {base['coef']:+.3f} -> {drop['coef']:+.3f} "
              f"(delta {drop['coef'] - base['coef']:+.3f}) "
              f"n {base['n_obs']} -> {drop['n_obs']}")
        if base["n_obs"] != drop["n_obs"]:
            print("  ⚠️  sample changed when dropping travel — coef delta is NOT a "
                  "clean control effect; investigate before interpreting")
    pd.DataFrame(diag_rows).to_csv(
        "results/tables/twfe_nhl_travel_diagnostic.csv", index=False)

    plot_effect(results).savefig(
        "results/figures/twfe_crowd_effect.png", dpi=150, bbox_inches="tight")

    for _, r in results.iterrows():
        print(f"{r['sport']:3} {r['outcome']:11} {r['sample']:10} "
              f"crowd={r['coef']:+.3f} [{r['ci_low']:+.3f},{r['ci_high']:+.3f}] "
              f"p={r['pvalue']:.3f} n={r['n_obs']}")


if __name__ == "__main__":
    main()
