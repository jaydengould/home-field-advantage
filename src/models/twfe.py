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

SPORTS = ["nfl", "mlb", "nba"]
TREATMENT = "crowd_pct"
CONTROLS = ["crowd_pct", "elo_diff", "rest_diff", "away_travel_km"]
# dataviz skill categorical slots 1-3, matches src/viz/descriptive.py
SPORT_COLORS = {"nfl": "#2a78d6", "mlb": "#008300", "nba": "#e87ba4"}


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


def fit(panel, outcome, sample="pooled", treated_seasons=None, extra_controls=()):
    """Fit the TWFE spec for one sport/outcome/sample. Pure (no disk/net).

    outcome in {"home_margin", "home_win"}; home_win runs as a linear
    probability model (0/1). Returns a flat dict of the crowd_pct coefficient
    with cluster-robust SE/CI plus the control coefficients.
    """
    sport = panel["sport"].iloc[0]
    df = _prep(panel)
    if sample == "restricted":
        df = df[df["season"].isin(_restricted_seasons(treated_seasons))]

    controls = list(CONTROLS) + list(extra_controls)
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
    regressors = controls + ["season_trend"]

    d = d.set_index(["home_team", "season"])
    res = PanelOLS(
        d[outcome], d[regressors], entity_effects=True, time_effects=False
    ).fit(cov_type="clustered", cluster_entity=True)
    ci = res.conf_int()
    out = {
        "sport": sport, "outcome": outcome, "sample": sample,
        "coef": float(res.params[TREATMENT]),
        "se": float(res.std_errors[TREATMENT]),
        "ci_low": float(ci.loc[TREATMENT, "lower"]),
        "ci_high": float(ci.loc[TREATMENT, "upper"]),
        "pvalue": float(res.pvalues[TREATMENT]),
        "n_obs": int(res.nobs),
        "n_dropped": int(n_dropped),
        "n_entities": int(d.index.get_level_values(0).nunique()),
    }
    out.update({f"coef_{c}": float(res.params[c]) for c in controls if c != TREATMENT})
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
                fmt="o", color=SPORT_COLORS.get(r["sport"], "gray"), capsize=3,
            )
        ax.set_yticks(range(len(sub)))
        ax.set_yticklabels([f"{r['sport']}·{r['sample']}" for _, r in sub.iterrows()])
        ax.axvline(0, ls="--", color="gray", lw=1)
        ax.set_title(outcome)
        ax.set_xlabel("crowd_pct coefficient (empty→full)")
    fig.suptitle("Crowd effect on home advantage (TWFE, 95% CI)")
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

    plot_effect(results).savefig(
        "results/figures/twfe_crowd_effect.png", dpi=150, bbox_inches="tight")

    for _, r in results.iterrows():
        print(f"{r['sport']:3} {r['outcome']:11} {r['sample']:10} "
              f"crowd={r['coef']:+.3f} [{r['ci_low']:+.3f},{r['ci_high']:+.3f}] "
              f"p={r['pvalue']:.3f} n={r['n_obs']}")


if __name__ == "__main__":
    main()
