"""Phase 6b — sport-blind on/off 2x2 DiD (the intuitive companion to 6a).

Raw, unadjusted before/after: home-field advantage in full-crowd seasons vs
treated (empty-crowd) seasons. The outcome (home_margin) is already home-away,
so the away team is the implicit control group and other seasons are the
control period; crowd_effect = HFA_full - HFA_reduced.

This is deliberately NOT a controlled model (that is 6a/twfe.py). It shares 6a's
confound (crowd + any home-specific pandemic shift); Phase 7's bubble is the
disentangler. See docs/superpowers/specs/2026-07-22-phase6b-did-design.md.
"""
from pathlib import Path

import pandas as pd
import statsmodels.formula.api as smf
import yaml

import matplotlib

matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt  # noqa: E402

from src.models.twfe import _exclusion_mask, _restricted_seasons, SPORT_COLORS

SPORTS = ["nfl", "mlb", "nba"]


def fit(panel, outcome, sample="pooled", treated_seasons=None):
    """Raw before/after crowd effect for one sport/outcome/sample. Pure (no disk/net).

    outcome in {"home_margin", "home_win"} (home_win as a 0/1 LPM).
    Returns a flat dict; crowd_effect = HFA_full - HFA_reduced (positive = crowd
    helps the home team, matching 6a's sign).
    """
    sport = panel["sport"].iloc[0]
    df = panel[~_exclusion_mask(panel)].copy()
    if sample == "restricted":
        df = df[df["season"].isin(_restricted_seasons(treated_seasons))]

    d = df[[outcome, "season", "home_team"]].copy()
    d[outcome] = d[outcome].astype(float)               # bool/Int64 -> float (LPM safe)
    d["reduced"] = d["season"].isin(treated_seasons).astype(int)
    d = d.dropna(subset=[outcome])                       # null home_win ties dropped

    res = smf.ols(f"{outcome} ~ reduced", data=d).fit(
        cov_type="cluster", cov_kwds={"groups": d["home_team"]}
    )
    # reduced coef is measured full->empty; crowd_effect flips it to empty->full.
    coef = res.params["reduced"]
    lo, hi = res.conf_int().loc["reduced"]               # CI of the reduced coef
    hfa_full = float(res.params["Intercept"])
    return {
        "sport": sport, "outcome": outcome, "sample": sample,
        "hfa_full": hfa_full,
        "hfa_reduced": hfa_full + float(coef),
        "crowd_effect": -float(coef),
        "se": float(res.bse["reduced"]),
        "ci_low": -float(hi),                            # negate AND swap bounds
        "ci_high": -float(lo),
        "pvalue": float(res.pvalues["reduced"]),
        "n_full": int((d["reduced"] == 0).sum()),
        "n_reduced": int((d["reduced"] == 1).sum()),
        "n_obs": int(len(d)),
        "n_entities": int(d["home_team"].nunique()),
    }


def plot_slope(results: pd.DataFrame) -> plt.Figure:
    """Dumbbell/slope: per sport, HFA_reduced (empty) -> HFA_full (with fans),
    so the SHRINK is the subject. Uses the pooled rows; one panel per outcome."""
    pooled = results[results["sample"] == "pooled"]
    outcomes = list(pooled["outcome"].unique())
    fig, axes = plt.subplots(1, len(outcomes), figsize=(5 * len(outcomes), 4), squeeze=False)
    for ax, outcome in zip(axes[0], outcomes):
        sub = pooled[pooled["outcome"] == outcome].sort_values("sport").reset_index(drop=True)
        for y, r in sub.iterrows():
            color = SPORT_COLORS.get(r["sport"], "gray")
            ax.plot([r["hfa_reduced"], r["hfa_full"]], [y, y], color=color, lw=2, zorder=1)
            ax.scatter([r["hfa_reduced"]], [y], color=color, marker="o",
                       facecolors="white", edgecolors=color, zorder=2)
            ax.scatter([r["hfa_full"]], [y], color=color, marker="o", zorder=2)
        ax.set_yticks(range(len(sub)))
        ax.set_yticklabels(list(sub["sport"]))
        ax.axvline(0, ls="--", color="gray", lw=1)
        ax.set_title(outcome)
        ax.set_xlabel("home-field advantage")
    # neutral-gray proxy handles: the hollow/filled shape carries the meaning, not color
    legend_handles = [
        plt.Line2D([], [], marker="o", ls="", markerfacecolor="white",
                   markeredgecolor="gray", color="gray", label="empty"),
        plt.Line2D([], [], marker="o", ls="", color="gray", label="with fans"),
    ]
    axes[0][0].legend(handles=legend_handles, loc="best", fontsize=8)
    fig.suptitle("HFA shrinks when the crowd leaves (raw before/after)")
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
        results[results["sport"] == s].to_csv(f"results/tables/did_{s}.csv", index=False)
    # cross-sport = win-prob effect (margin isn't cross-sport comparable), same rule as 6a
    results[results["outcome"] == "home_win"].to_csv(
        "results/tables/did_cross_sport.csv", index=False)

    plot_slope(results).savefig(
        "results/figures/did_hfa_shrink.png", dpi=150, bbox_inches="tight")

    for _, r in results.iterrows():
        print(f"{r['sport']:3} {r['outcome']:11} {r['sample']:10} "
              f"full={r['hfa_full']:+.3f} reduced={r['hfa_reduced']:+.3f} "
              f"crowd={r['crowd_effect']:+.3f} [{r['ci_low']:+.3f},{r['ci_high']:+.3f}] "
              f"p={r['pvalue']:.3f} n={r['n_obs']}")


if __name__ == "__main__":
    main()
