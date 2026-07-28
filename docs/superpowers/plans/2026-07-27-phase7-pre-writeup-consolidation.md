# Phase 7 — Pre-Write-Up Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the five paper-destined numbers that currently live only as `CLAUDE.md` prose into a tested `src/models/sensitivity.py` emitting five CSVs, position the study's null against the published literature, and clear the paper-facing correctness/presentation blockers — so Phase 8 can be written entirely from `results/tables/` and a bibliography.

**Architecture:** No new estimator. `src/models/sensitivity.py` calls the existing `twfe.fit` for every refit; `twfe.fit` gains four behaviour-preserving optional parameters (`trend`, `season_fe`, `report`, and a `"treated"` sample) that are the only reason a refit needs new code. The meta-analysis is ~25 lines of inverse-variance / DerSimonian–Laird arithmetic on the four per-sport `home_win` coefficients. Literature work is documentation, not code.

**Tech Stack:** Python 3.11 (`.venv`), pandas, numpy, `linearmodels.PanelOLS`, `scipy.stats.chi2`, matplotlib, pytest, YAML config.

## Global Constraints

- **Git is user-owned.** NEVER run `git commit`, `git push`, `git branch`, or `git checkout`. The plan's task-final step is "verify", not "commit". Leave all changes uncommitted in the working tree.
- **The 6a specification is frozen by pre-commitment.** Every change to `src/models/twfe.py` must be behaviour-preserving at the defaults: after Task 2, `python -m src.models.twfe` must reproduce `results/tables/twfe_*.csv` **byte-identically**. This phase *reports* sensitivities; it does not adopt them.
- **Sport-blind.** `src/models/` and `src/viz/` must never branch on sport (`src/models/CLAUDE.md`). Per-sport parameters come from `config/sports.yaml` (`treated_seasons`, `load_seasons`, `elo`).
- **Four sports, in this order:** `SPORTS = ["nfl", "mlb", "nba", "nhl"]`. Treated seasons: nfl `[2020]`, mlb `[2020, 2021]`, nba `[2021]`, nhl `[2021]`.
- **Language bans in every artifact produced here** (spec §6): do not call any sport's result a "clean null"; do not write "the pooled CI rules out effects larger than X"; do not read absence of heterogeneity as evidence of homogeneity. Correct framing is *underpowered and centred near zero*, and the four estimates share a **bias**, not just independent noise.
- **Run everything from the repo root** with the venv active: `source .venv/bin/activate`. Tests: `pytest -q`. Baseline is **122 passing**.
- **Panels** are `data/processed/{sport}.parquet` (feature-complete, 4 files, already built). Never re-pull ESPN.

---

### Task 1: Literature review, claim verification, and `references.bib` (Workstream B + C3)

Runs first so its findings can shape the sensitivity module (spec §7).

**Files:**
- Create: `docs/literature-review.md`
- Modify: `paper/references.bib` (currently one comment line, zero entries)
- Read-only input: `results/tables/twfe_cross_sport.csv`, `results/tables/descriptive_hfa.csv`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: BibTeX keys that Task 6's C3 fixes and Phase 8 will cite. Use stable keys: `systematicreview_ghostgames`, `higgs2021nba`, `plosone_nhl_penalties`, `paine_nhl_elo`, `espn_data`. Additional keys are free-form but must be lowercase `authorYEARtopic`.

- [ ] **Step 1: Gather the sources**

Use `WebSearch` + `WebFetch`. Find and actually read (not just the search-result title):
1. The systematic review of COVID ghost-game studies in football reporting the 6 / 2 / 8 / 10 split (no change / slightly reduced / reduced / strongly reduced) and the claim that **no study reported increased home advantage**.
2. Higgs & Stavness (2021) — NBA home margin 2.13 with fans vs 0.44 without.
3. The PLOS One study on NHL **penalty calls** and fan absence.
4. A ghost-matches **referee bias** study (football).
5. Neil Paine / 538 NHL Elo (`https://neilpaine.substack.com/p/how-my-nhl-elo-ratings-and-forecast`) — the K=6 / hfa 50 / carryover 0.70 parameters **and** the "no predictive power differentiating one-goal regulation vs OT/shootout results" finding.
6. ESPN as the data source (site API), cited as a data reference.

For each: record the exact reported effect size, its unit (goals / points / win probability / percentage points), sample size, and sport. **If a source cannot be retrieved, say so in the review and do not create a bib entry for it** — every entry must correspond to a source actually read.

- [ ] **Step 2: Verify the three C3 claims**

These are currently stated as fact in `CLAUDE.md` and would ship into the paper unverified:
1. The **NHL 2020-21 four-division realignment** including the all-Canadian North Division — this is the entire justification for the NHL travel diagnostic.
2. Whether **Toronto and Edmonton played bubble qualifying-round games in their own arenas** (affects how the bubble subsection is worded).
3. The **bubble hub dates, 1 Aug – 28 Sep 2020** (the `is_bubble` date rule in `src/data/nhl.py` depends on this).

Each claim gets either a citation in `references.bib` or an explicit "unverified — remove from write-up" line in the review.

- [ ] **Step 3: Compute the power-comparison numbers**

Minimum detectable effect at 80% power, two-sided α=.05, is `MDE ≈ 2.8 × SE`. Run:

```bash
python -c "
import pandas as pd
d = pd.read_csv('results/tables/twfe_cross_sport.csv')
d = d[(d['outcome']=='home_win') & (d['sample']=='pooled')]
d['mde_80'] = 2.8 * d['se']
print(d[['sport','coef','se','mde_80']].to_string(index=False))
"
```

Expected: nhl `se` ≈ 0.02265 → MDE ≈ 0.063 (the ~6.3pp figure). Record all four.

- [ ] **Step 4: Write `docs/literature-review.md`**

Structure it so Phase 8 can lift sections directly. It must answer all four §4 questions, with these sections:

1. **What prior work found** — a table with columns `study | sport | outcome type (match result vs referee behaviour) | effect with fans | effect without fans | n | direction`. Split by outcome type is mandatory: conflating match results with referee behaviour is the main way this literature gets misread.
2. **Where our estimates sit** — the sharpest available comparison is Higgs & Stavness NBA 2.13 → 0.44 against our descriptive 2.26 → 0.92 (`results/tables/descriptive_hfa.csv`). State both as descriptive, not causal.
3. **Are we underpowered relative to studies that found effects?** — its own table: `sport | our pooled win% coef | SE | MDE at 80% power | prior effect sizes in the same unit | can we detect theirs?`. This is the question that could change the paper's conclusion. Convert prior point-margin effects to win-probability where a defensible conversion exists; where it does not, say so rather than inventing one.
4. **Mechanism vs outcome (the NHL case)** — the PLOS One penalty-call finding and our NHL outcome null are **compatible**: referee bias can shift without moving win probability. State this precisely; it is the difference between "our null contradicts published work" and "our null is consistent with it at the outcome level while their mechanism finding stands."
5. **Claim verification** — the three C3 claims, each marked verified (with citation) or unverified (with the recommendation to cut).

Honour the §6 language bans. Where the review says our result differs from the literature, the honest framing is that our per-sport CIs are wide enough to contain the published effect sizes — not that we contradict them.

- [ ] **Step 5: Write `paper/references.bib`**

Replace the comment line with real BibTeX entries for every source read in Steps 1–2, using the keys from **Interfaces** above. Include `doi` or `url` plus `urldate` for web sources.

- [ ] **Step 6: Verify**

Run: `grep -c '^@' paper/references.bib`
Expected: at least 6 entries. Then confirm every `@` key appears at least once in `docs/literature-review.md`:

```bash
python -c "
import re,pathlib
bib=pathlib.Path('paper/references.bib').read_text()
rev=pathlib.Path('docs/literature-review.md').read_text()
keys=re.findall(r'@\w+\{([^,]+),',bib)
missing=[k for k in keys if k not in rev]
print('keys:',keys); print('uncited in review:',missing)
assert not missing
"
```
Expected: `uncited in review: []`.

---

### Task 2: Extend `twfe.fit` with the sensitivity hooks (prerequisite for Workstream A + C4 fix)

`sensitivity.py` must reuse `twfe.fit` — "no new estimator" (spec §3). Four refit shapes are not currently expressible: no/quadratic trend, full season FE, treated-seasons-only sample, and reporting a coefficient other than `crowd_pct`. All four are optional parameters whose defaults reproduce today's output exactly.

**Files:**
- Modify: `src/models/twfe.py:61-108` (`fit` signature and body)
- Test: `tests/test_twfe.py` (append)

**Interfaces:**
- Consumes: existing `twfe.fit`, `twfe._prep`, `twfe.CONTROLS`, `twfe.TREATMENT`.
- Produces, for Tasks 3–5:
  ```python
  fit(panel, outcome, sample="pooled", treated_seasons=None, extra_controls=(),
      drop_controls=(), trend="linear", season_fe=False, report=None) -> dict
  ```
  - `sample` ∈ `{"pooled", "restricted", "treated"}` — `"treated"` keeps only `treated_seasons`.
  - `trend` ∈ `{"none", "linear", "quadratic"}` — regressors added: none / `season_trend` / `season_trend` + `season_trend_sq`.
  - `season_fe: bool` — `True` sets `PanelOLS(time_effects=True)`. **Caller must pass `trend="none"` with it** (a linear trend is collinear with full season dummies); the function raises `ValueError` if not.
  - `report: str | None` — which regressor's `coef/se/ci_low/ci_high/pvalue` fills the top-level keys. Defaults to `crowd_pct`. Every *other* regressor still appears as `coef_<name>`.
  - Return dict gains `"trend"` and `"season_fe"` keys so a stacked CSV is self-describing.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_twfe.py` (the `_synth` fixture already exists at the top of that file):

```python
def test_defaults_unchanged_by_new_params():
    # The 6a spec is frozen: the default call path must be byte-identical.
    panel = _synth(beta=3.0)
    a = fit(panel, "home_margin", "pooled", [2020, 2021])
    b = fit(panel, "home_margin", "pooled", [2020, 2021],
            trend="linear", season_fe=False, report=None)
    assert a == b
    assert a["trend"] == "linear" and a["season_fe"] is False


def test_trend_options_change_the_fit_but_not_the_sample():
    panel = _synth(beta=3.0)
    fits = {t: fit(panel, "home_margin", "pooled", [2020, 2021], trend=t)
            for t in ("none", "linear", "quadratic")}
    assert len({f["n_obs"] for f in fits.values()}) == 1        # same rows, different spec
    assert fits["none"]["coef"] != fits["linear"]["coef"]        # trend actually enters
    assert "coef_season_trend_sq" not in fits["linear"]
    # planted beta survives every trend spec (it is identified off within-team dose)
    for f in fits.values():
        assert f["coef"] == pytest.approx(3.0, abs=0.6)


def test_season_fe_requires_no_trend():
    panel = _synth()
    with pytest.raises(ValueError):
        fit(panel, "home_margin", "pooled", [2020, 2021], season_fe=True, trend="linear")
    res = fit(panel, "home_margin", "pooled", [2020, 2021], season_fe=True, trend="none")
    assert res["season_fe"] is True
    assert res["n_obs"] > 0


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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_twfe.py -q`
Expected: the six new tests FAIL with `TypeError: fit() got an unexpected keyword argument 'trend'` (and `test_extra_controls_duplicate_is_deduped` fails on the duplicate-column error).

- [ ] **Step 3: Implement**

In `src/models/twfe.py`, replace the `fit` signature and the body between the `controls = ...` line and the `return out`:

```python
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
    trend_cols = {"none": [], "linear": ["season_trend"],
                  "quadratic": ["season_trend", "season_trend_sq"]}[trend]
    regressors = controls + trend_cols

    d = d.set_index(["home_team", "season"])
    res = PanelOLS(
        d[outcome], d[regressors], entity_effects=True, time_effects=season_fe
    ).fit(cov_type="clustered", cluster_entity=True)
    ci = res.conf_int()
    key = report or TREATMENT
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
```

Note the last line now iterates `regressors`, not `controls`, so the trend coefficients are visible too.

- [ ] **Step 4: Run the tests**

Run: `pytest tests/test_twfe.py -q`
Expected: all PASS. Then `pytest -q` — expected 128 passed (122 baseline + 6).

⚠️ `test_defaults_unchanged_by_new_params` asserts `a == b`, and the dict now carries `trend`/`season_fe`/`reported` keys in both — that is intended; the assertion is that passing the defaults explicitly changes nothing.

- [ ] **Step 5: Prove the shipped 6a numbers did not move**

```bash
mkdir -p /tmp/phase7-baseline && cp results/tables/twfe_*.csv /tmp/phase7-baseline/
python -m src.models.twfe
for f in results/tables/twfe_*.csv; do diff -q "$f" "/tmp/phase7-baseline/$(basename $f)"; done
```
Expected: **no diff output at all**. Any difference is a regression — stop and fix before proceeding. (`twfe_*.csv` now includes the three new columns only if the CSV writer changes; it does not — `main()` builds rows from `fit`, so the new `trend`/`season_fe`/`reported` columns WILL appear. If `diff` reports only those three added columns and every pre-existing numeric column is identical, that is acceptable — verify with:)

```bash
python -c "
import pandas as pd
for s in ['nfl','mlb','nba','nhl']:
    a=pd.read_csv(f'/tmp/phase7-baseline/twfe_{s}.csv'); b=pd.read_csv(f'results/tables/twfe_{s}.csv')
    assert set(a.columns) <= set(b.columns), s
    pd.testing.assert_frame_equal(a, b[a.columns], check_dtype=False)
    print(s, 'identical on all pre-existing columns')
"
```
Expected: four `identical` lines.

---

### Task 3: `sensitivity.meta_cross_sport()` — the pooled estimate, FE and RE

**Files:**
- Create: `src/models/sensitivity.py`
- Test: `tests/test_sensitivity.py`
- Output: `results/tables/meta_cross_sport.csv`

**Interfaces:**
- Consumes: `twfe.fit`, `twfe.SPORTS`, `config/sports.yaml`.
- Produces:
  ```python
  _load_panels() -> dict[str, pd.DataFrame]      # sport -> processed parquet
  _cfg() -> dict                                  # parsed config/sports.yaml
  _meta(coefs: np.ndarray, ses: np.ndarray) -> dict
      # keys: k, fe_coef, fe_se, re_coef, re_se, tau2, q, df, q_pvalue, i2
  meta_cross_sport(panels=None) -> pd.DataFrame   # writes meta_cross_sport.csv
  ```

- [ ] **Step 1: Write the failing tests**

Create `tests/test_sensitivity.py`:

```python
import numpy as np
import pandas as pd
import pytest

from src.models.sensitivity import _meta


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


def test_meta_unequal_weights_favour_the_precise_estimate():
    # The precise study (se=0.1) must dominate the imprecise one (se=1.0).
    m = _meta(np.array([0.0, 1.0]), np.array([0.1, 1.0]))
    assert m["fe_coef"] < 0.02          # pulled hard toward the precise 0.0
    assert m["k"] == 2
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_sensitivity.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.models.sensitivity'`.

- [ ] **Step 3: Implement the module skeleton + `_meta` + `meta_cross_sport`**

Create `src/models/sensitivity.py`:

```python
"""Phase 7 — sensitivity and pooling tables for the write-up.

Every number the paper cites that is NOT the frozen 6a/6b headline lives here,
as a CSV in results/tables/ rather than as prose. No new estimator: every refit
goes through twfe.fit with non-default arguments.

READ BEFORE INTERPRETING (spec §6):
  - The four sports share a BIAS, not just independent noise. Each estimate is
    "crowd effect + that league's 2020-21 non-crowd home-specific shift".
    Inverse-variance pooling shrinks SAMPLING error as 1/sqrt(k) and does
    nothing to a common bias, so the pooled SE is a LOWER BOUND on real
    uncertainty. Never write "the pooled CI rules out effects larger than X".
  - At k=4 the heterogeneity test has no power (rejecting needs Q > 7.81).
    Absence of heterogeneity is NOT evidence of homogeneity.
  - These are reported sensitivities. The main model is not re-specified.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy.stats import chi2

from src.models.twfe import SPORTS, fit

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
        "i2": max(0.0, (q - df) / q) if q > 0 else 0.0,
    }


def meta_cross_sport(panels=None) -> pd.DataFrame:
    """Pooled win-probability (LPM) crowd effect across sports, FE and RE.

    Two sets: all four sports, and the pre-NHL three-sport set, so the precision
    change from adding a sport is visible rather than asserted. Per-sport input
    rows carry the 80%-power minimum detectable effect (2.8*SE), which is what
    the literature power comparison needs."""
    panels = panels or _load_panels()
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
```

- [ ] **Step 4: Run the tests**

Run: `pytest tests/test_sensitivity.py -q`
Expected: 3 PASS.

- [ ] **Step 5: Run it against the real panels and sanity-check**

Run: `python -c "from src.models.sensitivity import meta_cross_sport as m; print(m().to_string(index=False))"`
Expected, matching the ad-hoc numbers in `CLAUDE.md` within rounding: 4-sport FE ≈ **−0.0003** (SE ≈ .0111), RE ≈ **+0.0014** (SE ≈ .0123), τ² ≈ .000088, I² ≈ 13.8%; 3-sport FE ≈ **−0.0025** (SE ≈ .0127), RE ≈ **+0.0043** (SE ≈ .0183), I² ≈ 40.4%; Q(4-sport) ≈ 3.48. Per-sport `mde_80` for nhl ≈ 0.063.
**If the CSV disagrees with `CLAUDE.md`, the CSV wins** — that is the entire point of this phase — but note the discrepancy in the task report.

---

### Task 4: `trend_sensitivity()` and `season_fe_sensitivity()`

**Files:**
- Modify: `src/models/sensitivity.py` (append two functions)
- Test: `tests/test_sensitivity.py` (append)
- Output: `results/tables/trend_sensitivity.csv`, `results/tables/season_fe_sensitivity.csv`

**Interfaces:**
- Consumes: `twfe.fit(..., trend=...)`, `twfe.fit(..., season_fe=True, trend="none")`, `twfe._prep`, `_load_panels`, `_cfg` from Task 3.
- Produces:
  ```python
  trend_sensitivity(panels=None) -> pd.DataFrame
  season_fe_sensitivity(panels=None) -> pd.DataFrame
  _collinearity_r2(panel) -> float    # R^2 of crowd_pct ~ C(season) + C(home_team)
  ```

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_sensitivity.py` (import `_synth` from the twfe tests — it is the shared synthetic panel with a planted effect):

```python
from tests.test_twfe import _synth
from src.models.sensitivity import (_collinearity_r2, season_fe_sensitivity,
                                    trend_sensitivity)


def _panels():
    """Two-sport synthetic stand-in for the real processed parquets."""
    a = _synth(beta=3.0, seed=0); a["sport"] = "nfl"
    b = _synth(beta=1.0, seed=1); b["sport"] = "nba"
    return {"nfl": a, "nba": b}


def test_trend_sensitivity_covers_every_sport_outcome_and_trend(monkeypatch, tmp_path):
    import src.models.sensitivity as sens
    monkeypatch.setattr(sens, "SPORTS", ["nfl", "nba"])
    monkeypatch.setattr(sens, "TABLES", tmp_path)
    monkeypatch.setattr(sens, "_cfg", lambda: {"nfl": {"treated_seasons": [2020, 2021]},
                                               "nba": {"treated_seasons": [2020, 2021]}})
    out = sens.trend_sensitivity(_panels())
    assert set(out["trend"]) == {"none", "linear", "quadratic"}
    assert len(out) == 2 * 2 * 3                     # sport x outcome x trend
    assert (tmp_path / "trend_sensitivity.csv").exists()
    # sample integrity: the three trend specs must use the SAME rows, or the
    # coefficient comparison is not a comparison of specifications.
    for (sport, outcome), g in out.groupby(["sport", "outcome"]):
        assert g["n_obs"].nunique() == 1, (sport, outcome)


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


def test_collinearity_r2_is_one_when_crowd_is_season_locked():
    # A crowd dose that is a pure function of season is perfectly explained by
    # season dummies -> R^2 == 1. This is the degenerate case the 6a design
    # argues NFL is close to (measured .974).
    df = _synth(games=3)
    df["crowd_pct"] = df["season"].map({2018: 0.9, 2019: 0.9, 2020: 0.1, 2021: 0.1})
    assert _collinearity_r2(df) == pytest.approx(1.0, abs=1e-6)
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_sensitivity.py -q`
Expected: FAIL — `ImportError: cannot import name '_collinearity_r2'`.

- [ ] **Step 3: Implement**

Append to `src/models/sensitivity.py`:

```python
def trend_sensitivity(panels=None) -> pd.DataFrame:
    """Crowd coefficient under no / linear (shipped) / quadratic season trend.

    Pre-empts the first objection a referee raises: is the linear season_trend
    absorbing the treatment? Reported for every sport and both outcomes."""
    panels = panels or _load_panels()
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
    less the season-FE coefficient means."""
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
    panels = panels or _load_panels()
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
```

Add `_prep` to the twfe import at the top of the module:
```python
from src.models.twfe import SPORTS, _prep, fit
```

- [ ] **Step 4: Run the tests**

Run: `pytest tests/test_sensitivity.py -q`
Expected: 6 PASS.

- [ ] **Step 5: Run against real panels and check against the prose**

```bash
python -c "
from src.models.sensitivity import trend_sensitivity, season_fe_sensitivity
print(trend_sensitivity().to_string(index=False))
print(season_fe_sensitivity().to_string(index=False))
"
```
Expected (from `CLAUDE.md`, which the CSV now supersedes): NHL `home_margin` — none +0.0296, linear +0.0077, quadratic +0.0316; NHL `home_win` — none +0.0118, linear +0.0066, quadratic +0.0025. Collinearity R²: nfl ≈ .974, nba ≈ .916, nhl ≈ .878, mlb ≈ .618. NHL `home_win` season-FE coefficient ≈ **+0.076** (se ≈ .048). Report any discrepancy.

---

### Task 5: `within_season_dose()`, `mlb_treated_split()`, and `main()`

**Files:**
- Modify: `src/models/sensitivity.py` (append two functions + `main`)
- Test: `tests/test_sensitivity.py` (append)
- Output: `results/tables/within_season_dose.csv`, `results/tables/mlb_treated_split.csv`

**Interfaces:**
- Consumes: `twfe.fit(..., sample="treated", trend="none")`, `twfe.fit(..., report=...)`, `twfe._prep`.
- Produces:
  ```python
  within_season_dose(panels=None) -> pd.DataFrame
  mlb_treated_split(panels=None) -> pd.DataFrame
  main() -> None     # runs all five, writes five CSVs, prints a summary
  ```

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_sensitivity.py`:

```python
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
    assert "coef_treated_season_dummy" in out.columns


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
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_sensitivity.py -q`
Expected: FAIL — `AttributeError: module 'src.models.sensitivity' has no attribute 'within_season_dose'`.

- [ ] **Step 3: Implement**

Append to `src/models/sensitivity.py`:

```python
def within_season_dose(panels=None) -> pd.DataFrame:
    """Crowd dose estimated WITHIN the treated season(s) only, all four sports.

    This design is endogenous and uninformative, and that is the finding: in
    2020-21 within-team fan access is confounded with calendar time (venues
    reopened progressively, so "more fans" ~= "later in the season"), and the
    fitted support is far short of 1.0, so a crowd_pct slope extrapolates. NHL's
    raw means run one way and its team-FE estimate the other — the sign flip IS
    the endogeneity lesson. Reported for all four sports so it is a comparison
    rather than an anecdote. Every row carries its support range."""
    panels = panels or _load_panels()
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
        empty = d[d["crowd_pct"] == 0]
        fans = d[d["crowd_pct"] > 0]
        for outcome in OUTCOMES:
            r = fit(panel, outcome, "treated", treated, trend="none",
                    extra_controls=extra)
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
                "raw_empty_mean": float(empty[outcome].astype(float).mean()) if len(empty) else float("nan"),
                "n_empty": int(len(empty)),
                "raw_fans_mean": float(fans[outcome].astype(float).mean()) if len(fans) else float("nan"),
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
    than a crowd effect. Suggestive only — it cannot separate the two."""
    panels = panels or _load_panels()
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
            # crowd_pct out, the two year indicators in; report one at a time.
            r = fit(panel, outcome, "pooled", treated,
                    drop_controls=["crowd_pct"], extra_controls=indicators,
                    report=col)
            rows.append({
                "sport": "mlb", "outcome": outcome, "treated_year": y,
                # sign convention matches 6b: positive = HFA was HIGHER that year
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


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the tests**

Run: `pytest tests/test_sensitivity.py -q`
Expected: 9 PASS. Then `pytest -q` — expected 137 passed.

- [ ] **Step 5: Run the whole module against real data**

Run: `python -m src.models.sensitivity`
Expected: five CSVs in `results/tables/` and the printed summary. Cross-check against `CLAUDE.md`: NHL within-2021 `home_margin` ≈ **−1.414** (se .858, n 849), `home_win` ≈ **−0.281** (se .183); NHL raw means empty n=556 margin +0.146, with-fans n=310 margin +0.471; NHL `crowd_max` ≈ 0.400 with `crowd_p99` ≈ 0.283. Report any discrepancy rather than adjusting the code to match the prose.

Run: `ls results/tables/`
Expected to include: `meta_cross_sport.csv`, `trend_sensitivity.csv`, `season_fe_sensitivity.csv`, `within_season_dose.csv`, `mlb_treated_split.csv`.

---

### Task 6: Workstream C — playoffs parameter, palette, and the two Minors

**Files:**
- Modify: `src/viz/descriptive.py:19-23` (palette comment + `SPORT_COLORS`), `:53-79` (`summarize`), `:26-33` (`_clean_home`)
- Modify: `src/models/twfe.py:32` (`SPORT_COLORS`, must match `descriptive.py` exactly)
- Modify: `tests/test_config.py:8` (rename)
- Test: `tests/test_descriptive.py` (append)

**Interfaces:**
- Consumes: nothing from Tasks 1–5.
- Produces: `descriptive.summarize(panel, playoffs=False)` — Phase 8's playoff-HFA subsection depends on this parameter existing.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_descriptive.py`. It already defines `_panel()` at line 8 — a 7-row nfl fixture holding exactly **one** playoff game (season 2019, `home_margin=14`, `home_win=True`, no other exclusion flag set) and one neutral-site game. Use it as-is; do NOT modify the fixture — other tests assert on its exact counts.

```python
def test_summarize_playoffs_flag_selects_the_postseason_slice():
    panel = _panel()
    reg = summarize(panel)                       # default: regular season, unchanged
    post = summarize(panel, playoffs=True)

    # the fixture's only playoff game is 2019, margin +14, a home win
    p19 = post[post["season"] == 2019].iloc[0]
    assert p19["n_games"] == 1
    assert p19["mean_home_margin"] == 14
    assert p19["home_win_pct"] == 1.0
    # the regular-season slice is untouched by the new parameter
    assert reg[reg["season"] == 2019].iloc[0]["n_games"] == 3
    assert list(reg.columns) == list(post.columns)
    # no 2020 playoff game in the fixture -> only 2019 + the pooled row
    assert set(post["season"]) == {2019, "pooled_fullcrowd"}


def test_sport_colors_match_across_modules():
    from src.models.twfe import SPORT_COLORS as a
    from src.viz.descriptive import SPORT_COLORS as b
    assert a == b                          # two dicts that must never drift


def test_every_sport_color_clears_the_3to1_contrast_floor():
    from src.viz.descriptive import SPORT_COLORS

    def lum(hexcode):
        c = [int(hexcode[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]

    for sport, hexcode in SPORT_COLORS.items():
        ratio = 1.05 / (lum(hexcode) + 0.05)
        assert ratio >= 3.0, f"{sport} {hexcode} contrast {ratio:.2f} < 3:1"
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_descriptive.py -q`
Expected: `test_summarize_playoffs_flag_selects_the_postseason_slice` FAILS with `TypeError: summarize() got an unexpected keyword argument 'playoffs'`, and `test_every_sport_color_clears_the_3to1_contrast_floor` FAILS on nba `#e87ba4` at ratio ≈ 2.62.

- [ ] **Step 3: Implement C1 (playoffs parameter)**

In `src/viz/descriptive.py`, thread the flag through both hardcoded `~is_playoff` filters:

```python
def _clean_home(panel: pd.DataFrame, playoffs: bool = False) -> pd.DataFrame:
    """True-home games (drop neutral/relocated/bubble), regular season by default.

    playoffs=True selects the postseason slice instead. Playoff HFA is NOT
    comparable to the regular-season number: the playoff home team is the better
    seed, so home advantage is blended with a quality asymmetry, and the treated
    seasons' postseasons are largely bubble/neutral. Reported with an asterisk."""
    excl = (
        panel["neutral_site"].fillna(False)
        | panel["relocated_home"].fillna(False)
        | panel["is_bubble"].fillna(False)
    )
    is_playoff = panel["is_playoff"].fillna(False)
    return panel[(is_playoff if playoffs else ~is_playoff) & (~excl)]


def summarize(panel: pd.DataFrame, playoffs: bool = False) -> pd.DataFrame:
    """Per-season + pooled-full-crowd descriptive HFA for one sport.

    playoffs=False (default) is the shipped Phase 5 behaviour and every number
    already published; playoffs=True gives Phase 8 its postseason subsection."""
    sport = panel["sport"].iloc[0]
    clean = _clean_home(panel, playoffs)
    is_playoff = panel["is_playoff"].fillna(False)
    reg = panel[is_playoff if playoffs else ~is_playoff]
    ...
```
(the rest of `summarize` is unchanged.)

- [ ] **Step 4: Implement C2 (palette)**

Measure candidates before choosing. Run:

```bash
python -c "
def lum(h):
    c=[int(h[i:i+2],16)/255 for i in (1,3,5)]
    c=[x/12.92 if x<=0.03928 else ((x+0.055)/1.055)**2.4 for x in c]
    return 0.2126*c[0]+0.7152*c[1]+0.0722*c[2]
for h in ['#e87ba4','#a4036f','#b0176b','#8e2f6b','#2a78d6','#008300','#e08b00']:
    print(h, round(1.05/(lum(h)+0.05),2))
"
```
Expected: `#e87ba4` ≈ 2.62 (the failure), `#a4036f` ≈ 7.4 (passes). Pick the first candidate that clears **3:1 against white** while staying distinguishable from blue `#2a78d6`, green `#008300`, and amber `#e08b00` under deuteranopia and protanopia — the four hues must remain separable by hue *and* lightness. **Record the measured ratio for the chosen colour in the task report**; do not assert it without measuring.

Then set the chosen value in **both** dicts, which must stay identical:
- `src/viz/descriptive.py:23`
- `src/models/twfe.py:32`

And in the `descriptive.py` comment block above the dict, delete the reference to `scripts/validate_palette.js` (it has never existed — a phantom path must not ship with a paper) and replace the comment with what is now true:

```python
# dataviz skill categorical slots: blue / green / magenta / amber.
# Every hue clears the 3:1 contrast floor against white — figures are print-bound
# and sport is encoded by line colour. The floor is enforced by
# tests/test_descriptive.py::test_every_sport_color_clears_the_3to1_contrast_floor,
# and this dict must stay identical to src/models/twfe.py SPORT_COLORS.
SPORT_COLORS = {"nfl": "#2a78d6", "mlb": "#008300", "nba": "<chosen>", "nhl": "#e08b00"}
```

- [ ] **Step 5: Implement C4 (test rename)**

In `tests/test_config.py:8`, rename `test_config_has_three_sports_with_treated_seasons` → `test_config_has_four_sports_with_treated_seasons`. (The `extra_controls` de-dupe half of C4 shipped in Task 2.)

- [ ] **Step 6: Run the tests**

Run: `pytest -q`
Expected: 140 passed (137 + 3 new), zero failures.

- [ ] **Step 7: Regenerate the three figures with the new palette**

```bash
python -m src.viz.descriptive
python -m src.models.twfe
python -m src.models.did
ls -l results/figures/
```
Expected: `hfa_by_season.png`, `twfe_crowd_effect.png`, `did_hfa_shrink.png` all with fresh timestamps (`did.py` imports `SPORT_COLORS` from `twfe`, so all three pick up the change). Open each and confirm four visually distinct series.

Re-run the Task 2 Step 5 equality check afterwards — regenerating figures also rewrites the CSVs, and the numbers must still be identical.

---

### Task 7: Full-suite verification and CLAUDE.md update

**Files:**
- Modify: `CLAUDE.md` (Status section + a new Phase 7 section)

- [ ] **Step 1: Run everything from clean**

```bash
pytest -q
python -m src.viz.descriptive
python -m src.models.twfe
python -m src.models.did
python -m src.models.sensitivity
```
Expected: 140 passed; every command exits 0.

- [ ] **Step 2: Confirm the done-when conditions (spec §8)**

```bash
ls results/tables/meta_cross_sport.csv results/tables/trend_sensitivity.csv \
   results/tables/season_fe_sensitivity.csv results/tables/within_season_dose.csv \
   results/tables/mlb_treated_split.csv docs/literature-review.md paper/references.bib
grep -rn "validate_palette.js" src/ || echo "phantom reference gone"
```
Expected: all seven paths exist; `phantom reference gone`.

- [ ] **Step 3: Update `CLAUDE.md`**

Add a `## Phase 7 — pre-write-up consolidation (done 2026-07-27) — COMPLETE` section following the established format: what was built, decisions settled, measured results, deferred minors. It must record:
- The five CSVs and that **the CSVs are now authoritative over the prose** — any Phase 8 number comes from `results/tables/` or a `.qmd` chunk, never from `CLAUDE.md`.
- Any discrepancy found between a recomputed number and the prose value (Tasks 3–5 Step 5).
- The chosen NBA colour and its **measured** contrast ratio.
- Which of the three C3 claims verified and which were cut.
- The literature review's answer to Q3 (are we underpowered relative to studies that found effects?) in one or two sentences — it is the finding most likely to shape Phase 8's conclusion.

Then rewrite the **Status** section: Phase 7 complete, **Phase 8 (Quarto write-up) is next**, carrying forward the existing Phase 8 checklist plus the §6 must-not-do list.

- [ ] **Step 4: Report, do not commit**

Leave everything uncommitted. Print `git status --short` and list the changed files in the task report so the user can review and commit their own history.

---

## Self-Review

**Spec coverage:** §3 five functions → Tasks 3–5 (`meta_cross_sport`, `trend_sensitivity`, `season_fe_sensitivity`, `within_season_dose`, `mlb_treated_split`, `main`); §3 tests (sample integrity, meta arithmetic incl. τ²=0, non-vacuous) → Task 3 Step 1, Task 4 Step 1, Task 5 Step 1. §4 four questions + bib → Task 1 Step 4/5. §5 C1 → Task 6 Step 3; C2 → Task 6 Step 4; C3 → Task 1 Step 2; C4 dedupe → Task 2, test rename → Task 6 Step 5. §6 bans → Global Constraints + module docstrings. §7 order B→A→C → Task order (1 → 2–5 → 6). §8 done-when → Task 7 Step 2.

**Gap accepted deliberately:** the spec assigns the `extra_controls` de-dupe to workstream C (last), but Workstream A is the caller that makes it live, so it ships in Task 2. Fixing it earlier than specified is strictly safer.

**Type consistency:** `fit()`'s new keywords (`trend`, `season_fe`, `report`, `sample="treated"`) are defined in Task 2 and used with those exact names in Tasks 4 and 5. `_meta` keys (`fe_coef`, `fe_se`, `re_coef`, `re_se`, `tau2`, `q`, `df`, `q_pvalue`, `i2`, `k`) are defined in Task 3 and read with `m[f"{method}_coef"]` in the same task. `_load_panels`/`_cfg`/`TABLES`/`OUTCOMES`/`_prep` are defined in Task 3 and used in Tasks 4–5. `summarize(panel, playoffs=False)` is defined once, in Task 6.
