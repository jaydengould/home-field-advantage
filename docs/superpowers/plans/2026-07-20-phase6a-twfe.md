# Phase 6a — TWFE dose-response Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A sport-blind two-way fixed-effects estimator of the crowd-attributable slice of home-field advantage, run per sport on two outcomes (scoring margin + win LPM) and two samples (pooled + restricted), emitting per-sport and cross-sport coefficient tables plus a forest-plot figure.

**Architecture:** One new module `src/models/twfe.py` mirroring the `src/viz/descriptive.py` pattern — a pure, tested `fit()` core (no disk/net) plus a `main()` that reads the three processed panels and writes artifacts. `fit()` filters exclusions, builds `elo_diff`/`rest_diff`, and runs `linearmodels.PanelOLS` with `home_team` entity effects + `season` time effects and home-team-clustered SEs.

**Tech Stack:** pandas, numpy, `linearmodels.PanelOLS` (v7.0, installed), matplotlib (Agg), PyYAML (installed), pytest.

> **⚠️ Build-time correction (2026-07-20):** the shipped estimator uses **team (entity) FE only + a linear `season_trend`**, NOT the two-way `entity+time` FE this plan's code blocks show. Full season FE proved near-collinear with the time-clustered COVID crowd shock and inverted every coefficient (NFL margin −8.75, opposite the descriptive dip). See the spec's "⚠️ Correction adopted at build time" for the diagnosis. Where a code block below says `time_effects=True`, the shipped `fit()` uses `time_effects=False` and adds `season_trend = season − min(season)` to the regressors. Everything else (controls, two outcomes, samples, clustering, exclusions, outputs, tests) is unchanged.

## Global Constraints

- **Sport-blind:** no sport branching inside `twfe.py`. Sport enters only as data (`config/sports.yaml` treated_seasons) — one estimator, run per sport. (CLAUDE.md core design principle #1.)
- **`src/` is a namespace package** — no `__init__.py`. Imports resolve via `pyproject.toml` `pythonpath = ["."]` (e.g. `from src.models.twfe import fit`).
- **Git is user-owned** — do NOT run `git commit`/`push`/`branch`. Tasks end by running tests, not committing; the user commits their own history. (CLAUDE.md.)
- **`crowd_pct == 0` is a REAL value** (empty stadium), never coerce to null. (Schema contract.)
- **PanelOLS index** = `(home_team, season)` MultiIndex; duplicate `(team, season)` pairs (many games per team-season) are expected and handled — verified 2026-07-20.
- **Controls (all sports):** `crowd_pct` (treatment), `elo_diff = home_elo − away_elo`, `rest_diff = home_rest_days − away_rest_days`, `away_travel_km`. `closing_spread`/weather are NFL-only → sensitivity check only.
- **Exclusions (both samples):** drop rows where any of `neutral_site | relocated_home | is_bubble | is_playoff` is True.
- **Restricted sample seasons:** `set(treated) ∪ {min(treated)−1, max(treated)+1}` → NFL `{2019,2020,2021}`, MLB `{2019,2020,2021,2022}`, NBA `{2020,2021,2022}`.

---

## File Structure

- **Create `src/models/twfe.py`** — the estimator + artifact writer. Public: `fit()`; helpers `_prep()`, `_restricted_seasons()`, `plot_effect()`, `main()`.
- **Create `tests/test_twfe.py`** — pure-function tests on synthetic panels (planted-effect recovery, exclusion filtering, restricted-season selection, LPM outcome).
- **Read-only inputs:** `data/processed/{nfl,mlb,nba}.parquet`, `config/sports.yaml`.
- **Generated outputs:** `results/tables/twfe_{nfl,mlb,nba}.csv`, `results/tables/twfe_cross_sport.csv`, `results/figures/twfe_crowd_effect.png`.

---

### Task 1: Estimator core (`fit` + helpers) with unit tests

**Files:**
- Create: `src/models/twfe.py`
- Test: `tests/test_twfe.py`

**Interfaces:**
- Consumes: processed-panel columns from `src/schema.py` (`sport`, `season`, `home_team`, `home_margin`, `home_win`, `crowd_pct`, `home_elo`, `away_elo`, `home_rest_days`, `away_rest_days`, `away_travel_km`, `neutral_site`, `relocated_home`, `is_bubble`, `is_playoff`).
- Produces (relied on by Task 2):
  - `_restricted_seasons(treated: list[int]) -> set[int]`
  - `_prep(panel: pd.DataFrame) -> pd.DataFrame` — exclusion-filtered copy with `elo_diff`, `rest_diff` added.
  - `fit(panel, outcome: str, sample: str = "pooled", treated_seasons: list[int] | None = None, extra_controls=()) -> dict` returning keys: `sport, outcome, sample, coef, se, ci_low, ci_high, pvalue, n_obs, n_entities` plus `coef_<control>` for each non-treatment control.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_twfe.py`:

```python
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
        for s in seasons:
            base = 0.30 if s in (2020, 2021) else 0.85
            for _ in range(games):
                crowd = float(np.clip(base + rng.uniform(-0.5, 0.5), 0.0, 1.0))
                elo_diff = rng.normal(0, 60)
                margin = (beta * crowd + team_fx[team] + season_fx[s]
                          + 0.04 * elo_diff + rng.normal(0, 0.5))
                rows.append(dict(
                    sport="nfl", season=s, home_team=team,
                    home_margin=margin, home_win=margin > 0, crowd_pct=crowd,
                    home_elo=1500 + elo_diff, away_elo=1500.0,
                    home_rest_days=7, away_rest_days=7, away_travel_km=500.0,
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && pytest tests/test_twfe.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.models.twfe'`.

- [ ] **Step 3: Write the estimator core**

Create `src/models/twfe.py`:

```python
"""Phase 6a — sport-blind TWFE dose-response causal engine.

Estimates the crowd-attributable slice of home-field advantage:
    outcome ~ crowd_pct + elo_diff + rest_diff + away_travel_km
             + EntityEffects(home_team) + TimeEffects(season)
run per sport, for two outcomes (home_margin, home_win-as-LPM) and two samples
(pooled headline, restricted robustness check). SEs clustered by home_team.
See docs/superpowers/specs/2026-07-20-phase6a-twfe-design.md.
"""
from pathlib import Path

import numpy as np
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


def _prep(panel: pd.DataFrame) -> pd.DataFrame:
    """Drop excluded games (neutral/relocated/bubble/playoff) and add the two
    derived diff controls. Sport-blind."""
    excl = (
        panel["neutral_site"].fillna(False)
        | panel["relocated_home"].fillna(False)
        | panel["is_bubble"].fillna(False)
        | panel["is_playoff"].fillna(False)
    )
    df = panel[~excl].copy()
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
    d = d.dropna()                                  # listwise: first-game rest, missing travel/spread

    d = d.set_index(["home_team", "season"])
    res = PanelOLS(
        d[outcome], d[controls], entity_effects=True, time_effects=True
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
        "n_entities": int(d.index.get_level_values(0).nunique()),
    }
    out.update({f"coef_{c}": float(res.params[c]) for c in controls if c != TREATMENT})
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && pytest tests/test_twfe.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Run the full suite (no regressions)**

Run: `source .venv/bin/activate && pytest -q`
Expected: prior 93 tests + 5 new = 98 pass. (Do NOT commit — git is user-owned; leave changes staged for the user.)

---

### Task 2: `main()` + forest plot + real-data artifacts

**Files:**
- Modify: `src/models/twfe.py` (add `plot_effect`, `main`, `__main__` guard)
- Test: `tests/test_twfe.py` (add a `plot_effect` smoke test)

**Interfaces:**
- Consumes: `fit()` and `SPORT_COLORS` from Task 1; `config/sports.yaml` `<sport>.treated_seasons`; `data/processed/<sport>.parquet`.
- Produces: `results/tables/twfe_<sport>.csv` (×3), `results/tables/twfe_cross_sport.csv`, `results/figures/twfe_crowd_effect.png`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_twfe.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_twfe.py::test_plot_effect_returns_figure -q`
Expected: FAIL — `ImportError: cannot import name 'plot_effect'`.

- [ ] **Step 3: Add `plot_effect`, `main`, and the `__main__` guard**

First, add the module-level imports and constants these functions need to the **top** of `src/models/twfe.py` (Task 1 deliberately left them out as unused — add them here where they are first used). The top of the file becomes:

```python
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
```

Then append the functions to `src/models/twfe.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `source .venv/bin/activate && pytest tests/test_twfe.py -q`
Expected: PASS (6 tests).

- [ ] **Step 5: Generate the real-data artifacts**

Run: `source .venv/bin/activate && python -m src.models.twfe`
Expected: prints 12 coefficient lines (3 sports × 2 outcomes × 2 samples) + the NFL sensitivity line; writes `results/tables/twfe_{nfl,mlb,nba}.csv`, `results/tables/twfe_cross_sport.csv`, `results/figures/twfe_crowd_effect.png`.

**Sanity read (not asserted — interpret, per the spec's identification honesty):**
- NFL & NBA `home_margin` `crowd_pct` coefficients should be **positive** (full crowd → bigger home margin); NBA the largest in raw points.
- MLB `home_margin` CI should be **wide / straddle 0** (Phase 5: MLB margin is noise-dominated) — expected, not a bug. MLB's signal is the `home_win` LPM.
- `home_win` LPM coefficients (the cross-sport unit) should be positive Δwin-prob for NFL/NBA; MLB smaller but this is baseball's real headline.
- pooled vs restricted should be **broadly similar** — large divergence flags that endogenous normal-season variation matters (a finding to report).

- [ ] **Step 6: Verify the full suite (no regressions)**

Run: `source .venv/bin/activate && pytest -q`
Expected: 99 tests pass (93 prior + 6 new). (Do NOT commit — git is user-owned.)

---

## Self-Review

**Spec coverage:**
- Model (`crowd_pct + elo_diff + rest_diff + away_travel_km` + home_team FE + season FE, clustered) → Task 1 `fit`. ✓
- Two outcomes (margin + home_win LPM) → Task 2 `main` loop; `fit` casts outcome to float. ✓
- Two samples (pooled + restricted, `treated ∪ {min−1,max+1}`) → `_restricted_seasons` + `fit(sample=...)`; tested. ✓
- Exclusions (neutral/relocated/bubble/playoff) → `_prep`; tested. ✓
- NFL-only sensitivity (+closing_spread) → `fit(extra_controls=...)` + `main` print. ✓
- Outputs: per-sport tables, cross-sport LPM table, forest plot → Task 2. ✓
- Planted-effect test → `test_fit_recovers_planted_margin_effect`. ✓
- Sport-specific identification honesty (NFL curve vs MLB/NBA on-off; MLB margin wide) → Task 2 Step 5 sanity read (for the write-up, not asserted). ✓
- Parked non-goals (playoff subsection→Phase 8, causal-playoff dropped, logit/bootstrap deferred) → not built, correct. ✓

**Placeholder scan:** none — every code step is complete.

**Type consistency:** `fit()` returns the dict keys Task 2's `main`/`plot_effect` consume (`coef`, `ci_low`, `ci_high`, `sport`, `outcome`, `sample`, `n_obs`); `_restricted_seasons`/`_prep` signatures match their call sites and tests. ✓

**Note:** `main()` prints a 12-line result summary and NFL sensitivity rather than a pass/fail gate — this is estimation output to interpret, not a sanity gate (that was Phase 5). Wide MLB-margin CIs are an expected finding, not a failure.
