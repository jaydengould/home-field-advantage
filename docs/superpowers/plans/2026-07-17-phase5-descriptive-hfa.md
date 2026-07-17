# Phase 5 — Descriptive HFA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a sport-blind descriptive HFA table (home win % + mean scoring margin, with SEs, by sport × season + pooled) and a 2-panel figure, doubling as a data-sanity gate before modeling.

**Architecture:** One sport-blind module `src/viz/descriptive.py`, mirroring `src/features/build.py`: a pure `summarize(panel)` (fully unit-tested), a `plot_hfa(table)` figure builder, and a `main()` that reads the three processed parquets, writes `results/tables/descriptive_hfa.csv` + `results/figures/hfa_by_season.png`, and prints a PASS/CHECK sanity gate.

**Tech Stack:** Python 3.11, pandas, numpy, matplotlib, pytest.

## Global Constraints

- Sport is a parameter: `src/viz/descriptive.py` is sport-blind — no sport-specific branching. (CLAUDE.md core principle 1.)
- Input is `data/processed/{sport}.parquet` (Phase 4 output, 29-col validated schema). Output is `results/{tables,figures}/` (generated, safe to regenerate).
- Clean home game = `is_playoff == False` AND NOT (`neutral_site` | `relocated_home` | `is_bubble`).
- `home_win` is nullable boolean (ties → null); `home_margin` for a tie is 0.
- SEs are naive iid (proportion SE for win%, sample-mean SE for margin) — a guard against over-reading a noisy season, NOT the causal CIs. Do not present them as inferential.
- Git is user-owned. Do NOT run `git commit`/`push`/`branch` — leave changes in the working tree. (The commit steps below are for the human; the implementer stages nothing and runs no git command.)

---

### Task 1: `summarize(panel)` — pure descriptive aggregation

**Files:**
- Create: `src/viz/descriptive.py`
- Test: `tests/test_descriptive.py`

**Interfaces:**
- Consumes: a processed panel `DataFrame` (29-col schema) for one sport.
- Produces: `summarize(panel: pd.DataFrame) -> pd.DataFrame` with columns
  `["sport", "season", "n_games", "n_games_raw", "home_win_pct", "home_win_se", "mean_home_margin", "home_margin_se"]`.
  Per-season rows have integer `season`; one pooled row has `season == "pooled_fullcrowd"` computed over `covid_era == False` seasons only. `n_games` includes ties; win% and its SE use only decided (non-null `home_win`) games; margin and its SE use all clean-home games.

- [ ] **Step 1: Write the failing test**

Create `tests/test_descriptive.py`. Build a tiny hand-computed panel: 2 seasons (2019 full-crowd `covid_era=False`, 2020 `covid_era=True`), including one neutral-site game, one playoff game, and one tie — all in season 2019 — plus two clean games in 2020.

```python
import numpy as np
import pandas as pd
import pytest

from src.viz.descriptive import summarize


def _panel():
    # season 2019 (covid_era=False): 3 clean regular-season home games
    #   win (+7), loss (-3), tie (0, home_win=NA)
    #   + 1 neutral-site game (excluded), + 1 playoff game (excluded)
    # season 2020 (covid_era=True): 2 clean games: win (+1), loss (-6)
    rows = [
        dict(season=2019, is_playoff=False, neutral_site=False, relocated_home=False,
             is_bubble=False, home_win=True,  home_margin=7,  covid_era=False),
        dict(season=2019, is_playoff=False, neutral_site=False, relocated_home=False,
             is_bubble=False, home_win=False, home_margin=-3, covid_era=False),
        dict(season=2019, is_playoff=False, neutral_site=False, relocated_home=False,
             is_bubble=False, home_win=pd.NA, home_margin=0,  covid_era=False),
        dict(season=2019, is_playoff=False, neutral_site=True,  relocated_home=False,
             is_bubble=False, home_win=True,  home_margin=10, covid_era=False),
        dict(season=2019, is_playoff=True,  neutral_site=False, relocated_home=False,
             is_bubble=False, home_win=True,  home_margin=14, covid_era=False),
        dict(season=2020, is_playoff=False, neutral_site=False, relocated_home=False,
             is_bubble=False, home_win=True,  home_margin=1,  covid_era=True),
        dict(season=2020, is_playoff=False, neutral_site=False, relocated_home=False,
             is_bubble=False, home_win=False, home_margin=-6, covid_era=True),
    ]
    df = pd.DataFrame(rows)
    df["sport"] = "nfl"
    df["home_win"] = df["home_win"].astype("boolean")
    return df


def test_exclusions_and_counts():
    out = summarize(_panel())
    r19 = out[out["season"] == 2019].iloc[0]
    assert r19["n_games"] == 3          # neutral + playoff excluded, tie kept
    assert r19["n_games_raw"] == 4      # regular-season games before exclusions (excl playoff)


def test_win_pct_and_margin_2019():
    out = summarize(_panel())
    r19 = out[out["season"] == 2019].iloc[0]
    # decided games = win, loss -> 0.5; tie excluded from win%
    assert r19["home_win_pct"] == pytest.approx(0.5)
    assert r19["home_win_se"] == pytest.approx(0.3535533905932738)
    # margin over win/loss/tie = (7 - 3 + 0)/3
    assert r19["mean_home_margin"] == pytest.approx(1.3333333333333333)
    assert r19["home_margin_se"] == pytest.approx(2.96273147243853)


def test_2020_values():
    out = summarize(_panel())
    r20 = out[out["season"] == 2020].iloc[0]
    assert r20["mean_home_margin"] == pytest.approx(-2.5)
    assert r20["home_margin_se"] == pytest.approx(3.5)


def test_pooled_fullcrowd_uses_only_noncovid():
    out = summarize(_panel())
    pooled = out[out["season"] == "pooled_fullcrowd"].iloc[0]
    # only 2019 is covid_era False -> pooled == 2019 numbers
    assert pooled["mean_home_margin"] == pytest.approx(1.3333333333333333)
    assert pooled["home_win_pct"] == pytest.approx(0.5)
    assert pooled["n_games"] == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_descriptive.py -v`
Expected: FAIL with `ImportError` / `cannot import name 'summarize'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/viz/descriptive.py`:

```python
"""Phase 5 — sport-blind descriptive home-field advantage.

Reads processed panels, emits an HFA summary table (win% + margin with naive
SEs, by season + pooled) and a 2-panel figure. The season slice doubles as a
data-sanity gate: HFA must be positive in full-crowd seasons and dip in COVID.
"""
from pathlib import Path

import numpy as np
import pandas as pd

SPORTS = ["nfl", "mlb", "nba"]


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
            "n_games_raw": int((reg["season"] == season).sum()),
            **_agg(g),
        })
    full = clean[~clean["covid_era"].fillna(False)]
    rows.append({
        "sport": sport,
        "season": "pooled_fullcrowd",
        "n_games_raw": np.nan,
        **_agg(full),
    })
    cols = ["sport", "season", "n_games", "n_games_raw", "home_win_pct",
            "home_win_se", "mean_home_margin", "home_margin_se"]
    return pd.DataFrame(rows)[cols]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_descriptive.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit** (human — implementer leaves the change in the working tree)

```bash
git add src/viz/descriptive.py tests/test_descriptive.py
git commit -m "feat(phase5): descriptive HFA summarize()"
```

---

### Task 2: `plot_hfa` + `main` + sanity gate

**Files:**
- Modify: `src/viz/descriptive.py`

**Interfaces:**
- Consumes: `summarize()` from Task 1; the concatenated table of all three sports.
- Produces:
  - `plot_hfa(table: pd.DataFrame) -> matplotlib.figure.Figure`
  - `main() -> None` — writes `results/tables/descriptive_hfa.csv`, `results/figures/hfa_by_season.png`, prints the gate.

- [ ] **Step 1: Load the dataviz skill**

Before writing chart code, invoke the `dataviz` skill for palette/accessibility. Apply its guidance to the colors and axes in `plot_hfa`. (The `SPORT_COLORS` below are placeholders to be reconciled with the skill's palette.)

- [ ] **Step 2: Add `plot_hfa`, `main`, and the gate to `src/viz/descriptive.py`**

Append to `src/viz/descriptive.py`:

```python
import matplotlib

matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt  # noqa: E402

# ponytail: placeholder palette — reconcile with dataviz skill's palette
SPORT_COLORS = {"nfl": "#4C78A8", "mlb": "#F58518", "nba": "#54A24B"}


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
    """Print PASS/CHECK per sport: positive HFA pooled + 2020 margin dip."""
    for sport in table["sport"].unique():
        pooled = table[(table["sport"] == sport) & (table["season"] == "pooled_fullcrowd")].iloc[0]
        s2020 = table[(table["sport"] == sport) & (table["season"] == 2020)]
        win_ok = pooled["home_win_pct"] > 0.5
        margin_ok = pooled["mean_home_margin"] > 0
        dip = (not s2020.empty) and (s2020.iloc[0]["mean_home_margin"] < pooled["mean_home_margin"])
        status = "PASS" if (win_ok and margin_ok and dip) else "CHECK"
        print(f"[{status}] {sport}: pooled win%={pooled['home_win_pct']:.3f} "
              f"margin={pooled['mean_home_margin']:.2f}  2020 margin dip={dip}")


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
```

- [ ] **Step 3: Confirm existing unit tests still pass**

Run: `.venv/bin/pytest tests/test_descriptive.py -v`
Expected: PASS (Task 1 tests unaffected).

- [ ] **Step 4: Real-data run (the verification for this task)**

Run: `.venv/bin/python -m src.viz.descriptive`
Expected:
- `results/tables/descriptive_hfa.csv` and `results/figures/hfa_by_season.png` exist.
- Gate prints three lines. Every sport should read `[PASS]` (pooled win% > 0.5, pooled margin > 0, 2020 margin dips below pooled). A `[CHECK]` line means investigate before Phase 6 — a real non-dip or a bug, not something to paper over.
- Open the PNG and eyeball: three sport lines, all dipping into the shaded 2020–21 band.

Verify files:
`ls -la results/tables/descriptive_hfa.csv results/figures/hfa_by_season.png`

- [ ] **Step 5: Commit** (human — implementer leaves the change in the working tree)

```bash
git add src/viz/descriptive.py results/
git commit -m "feat(phase5): HFA figure + sanity gate"
```

---

## Self-Review

**Spec coverage:**
- Clean-home filter (playoff + neutral/relocated/bubble) → `_clean_home`, Task 1. ✓
- win% + SE, margin + SE, per season → `_agg`, Task 1, tested. ✓
- pooled full-crowd headline over `covid_era == False` → Task 1, tested. ✓
- `n_games` (incl ties) vs decided-game denominator → `_agg`, tested (tie case). ✓
- 2-panel figure, COVID band, error bars, reference lines → `plot_hfa`, Task 2. ✓
- CSV + PNG outputs → `main`, Task 2. ✓
- Sanity gate (positive HFA + 2020 dip, PASS/FAIL, non-crashing) → `_print_gate`, Task 2. ✓
- dataviz skill before charting → Task 2 Step 1. ✓
- Playoff subsection excluded → no task (deliberate). ✓

**Placeholder scan:** `SPORT_COLORS` is flagged `ponytail:` and reconciled via the dataviz skill in Task 2 Step 1 — intentional, not a gap. No TBD/TODO left.

**Type consistency:** `summarize` return columns match what `plot_hfa`/`_print_gate` read (`season`, `sport`, `home_win_pct`, `home_win_se`, `mean_home_margin`, `home_margin_se`, `n_games`). `season` is int for per-season rows / str `"pooled_fullcrowd"` for pooled; every comparison guards for the string. Consistent. ✓
