"""Phase 5 — sport-blind descriptive home-field advantage.

Reads processed panels, emits an HFA summary table (win% + margin with naive
SEs, by season + pooled) and a 2-panel figure. The season slice doubles as a
data-sanity gate: HFA must be positive in full-crowd seasons and dip in COVID.
"""
from pathlib import Path

import numpy as np
import pandas as pd

import matplotlib

matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt  # noqa: E402

SPORTS = ["nfl", "mlb", "nba"]

# dataviz skill categorical slots 1-3 (blue/green/magenta), validated colorblind-safe
# via scripts/validate_palette.js (worst adjacent CVD ΔE 17.6, normal-vision ΔE 29.0).
# Magenta sits below the 3:1 contrast floor -> relief rule -> legend + markers below.
SPORT_COLORS = {"nfl": "#2a78d6", "mlb": "#008300", "nba": "#e87ba4"}


def _clean_home(panel: pd.DataFrame) -> pd.DataFrame:
    """Regular-season true-home games (drop neutral/relocated/bubble)."""
    excl = (
        panel["neutral_site"].fillna(False)
        | panel["relocated_home"].fillna(False)
        | panel["is_bubble"].fillna(False)
    )
    return panel[(~panel["is_playoff"].fillna(False)) & (~excl)]


def _agg(games: pd.DataFrame) -> dict:
    """HFA stats for a set of clean-home games."""
    n_games = len(games)
    decided = games["home_win"].dropna()
    n_dec = len(decided)
    p = float(decided.mean()) if n_dec else np.nan
    win_se = np.sqrt(p * (1 - p) / n_dec) if n_dec else np.nan
    margin = games["home_margin"]
    return {
        "n_games": n_games,
        "home_win_pct": p,
        "home_win_se": win_se,
        "mean_home_margin": margin.mean() if n_games else np.nan,
        "home_margin_se": margin.std(ddof=1) / np.sqrt(n_games) if n_games > 1 else np.nan,
    }


def summarize(panel: pd.DataFrame) -> pd.DataFrame:
    """Per-season + pooled-full-crowd descriptive HFA for one sport."""
    sport = panel["sport"].iloc[0]
    clean = _clean_home(panel)
    reg = panel[~panel["is_playoff"].fillna(False)]
    rows = []
    for season, g in clean.groupby("season"):
        rows.append({
            "sport": sport,
            "season": season,
            # covid_era is constant within a season (loader sets it from
            # treated_seasons); .any() collapses it. Drives the sanity gate.
            "covid_era": bool(g["covid_era"].fillna(False).any()),
            "n_games_raw": int((reg["season"] == season).sum()),
            **_agg(g),
        })
    full = clean[~clean["covid_era"].fillna(False)]
    rows.append({
        "sport": sport,
        "season": "pooled_fullcrowd",
        "covid_era": False,  # the full-crowd baseline is by definition untreated
        "n_games_raw": np.nan,
        **_agg(full),
    })
    cols = ["sport", "season", "covid_era", "n_games", "n_games_raw", "home_win_pct",
            "home_win_se", "mean_home_margin", "home_margin_se"]
    return pd.DataFrame(rows)[cols]


def plot_hfa(table: pd.DataFrame) -> plt.Figure:
    """Two-panel HFA-by-season figure (win%, margin), COVID band shaded."""
    per = table[table["season"] != "pooled_fullcrowd"].copy()
    per["season"] = per["season"].astype(int)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 8), sharex=True)
    for sport, g in per.groupby("sport"):
        g = g.sort_values("season")
        c = SPORT_COLORS.get(sport)
        ax1.errorbar(g["season"], g["home_win_pct"], yerr=g["home_win_se"],
                     label=sport, color=c, marker="o", capsize=3)
        ax2.errorbar(g["season"], g["mean_home_margin"], yerr=g["home_margin_se"],
                     label=sport, color=c, marker="o", capsize=3)
    ax1.axhline(0.5, ls="--", color="gray", lw=1)
    ax2.axhline(0.0, ls="--", color="gray", lw=1)
    for ax in (ax1, ax2):
        ax.axvspan(2019.5, 2021.5, color="gray", alpha=0.12)  # COVID 2020-21 band
        ax.legend()
    ax1.set_ylabel("Home win %")
    ax2.set_ylabel("Mean home margin")
    ax2.set_xlabel("Season")
    fig.suptitle("Home-field advantage by season")
    fig.tight_layout()
    return fig


def _print_gate(table: pd.DataFrame) -> None:
    """Sanity gate per sport: positive pooled HFA + a margin dip in the sport's
    treated (policy-restricted) seasons vs the full-crowd baseline. Data-driven
    off `covid_era` — no hardcoded season, so each sport checks its own real
    treatment years (NFL 2020, MLB 2020-21, NBA 2021). Prints, never raises."""
    for sport in table["sport"].unique():
        rows = table[table["sport"] == sport]
        pooled = rows[rows["season"] == "pooled_fullcrowd"].iloc[0]
        treated = rows[(rows["season"] != "pooled_fullcrowd") & rows["covid_era"]]
        win_ok = pooled["home_win_pct"] > 0.5
        margin_ok = pooled["mean_home_margin"] > 0
        dip = (not treated.empty) and (treated["mean_home_margin"].min() < pooled["mean_home_margin"])
        status = "PASS" if (win_ok and margin_ok and dip) else "CHECK"
        seasons = sorted(int(s) for s in treated["season"])
        print(f"[{status}] {sport}: pooled win%={pooled['home_win_pct']:.3f} "
              f"margin={pooled['mean_home_margin']:.2f}  treated={seasons} margin dip={dip}")


def main() -> None:
    table = pd.concat([summarize(pd.read_parquet(f"data/processed/{s}.parquet"))
                       for s in SPORTS], ignore_index=True)
    Path("results/tables").mkdir(parents=True, exist_ok=True)
    Path("results/figures").mkdir(parents=True, exist_ok=True)
    table.to_csv("results/tables/descriptive_hfa.csv", index=False)
    plot_hfa(table).savefig("results/figures/hfa_by_season.png", dpi=150, bbox_inches="tight")
    _print_gate(table)


if __name__ == "__main__":
    main()
