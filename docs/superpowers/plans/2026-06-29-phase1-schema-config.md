# Phase 1: Schema Contract + Config — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the unified panel schema as a code validator plus a filled `config/sports.yaml`, so every later phase has one enforced contract to emit and consume.

**Architecture:** A `COLUMNS` dict of `Col` specs in `src/schema.py` is the single source of truth; `validate(df)` checks any panel against it, collecting all violations and raising one `ValueError`. `config/sports.yaml` carries `treated_seasons` per sport (the `covid_era` window). All sport-blind.

**Tech Stack:** Python 3.12, pandas 2.2 (nullable extension dtypes `Int64`/`boolean`), PyYAML, pytest.

## Global Constraints

- **Git is the user's job — do NOT run `git add`/`commit`/`push` or branch.** Each task boundary is a review checkpoint; stop there and let the user commit.
- Run all commands with the project venv: `.venv/bin/python`, `.venv/bin/pytest`.
- numpy `<2`, pandas `>=2.0,<2.3` (already installed — do not upgrade).
- `crowd_pct == 0` is a REAL value (empty stadium), never coerced to null.
- Schema layer stays config-free: `validate()` must not import YAML or read `config/`.
- Column set is exactly the 29 columns in the spec — no additions, no omissions.
- Spec: `docs/superpowers/specs/2026-06-29-phase1-schema-config-design.md`.

---

### Task 1: `Col` spec, `COLUMNS`, and structural `validate()`

Structural checks only (presence, dtype, nullability, domain/range). Conditional cross-field rules come in Task 2.

**Files:**
- Create: `src/schema.py`
- Create: `tests/test_schema.py`
- Create: `pyproject.toml`

**Interfaces:**
- Produces: `Col(dtype: str, nullable: bool = False, min=None, max=None, values: set | None = None)` frozen dataclass; `COLUMNS: dict[str, Col]`; `validate(df: pd.DataFrame) -> None` (raises `ValueError` listing all violations, returns `None` on success).
- `validate()` dtype tags: `"str"`, `"int"`, `"float"`, `"bool"`, `"date"`, `"Int64"` (nullable int), `"boolean"` (nullable bool).

- [ ] **Step 1: Create `pyproject.toml` so `from src.schema import ...` resolves**

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
```

`src/` is an implicit namespace package (no `__init__.py` needed); putting the repo root on the path makes `src.schema` importable from tests and from `src/data/` loaders later.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_schema.py`:

```python
import pandas as pd
import pytest

from src.schema import COLUMNS, validate


def valid_panel() -> pd.DataFrame:
    """One correct row, every column at its proper dtype."""
    return pd.DataFrame({
        "sport": pd.Series(["nfl"], dtype="object"),
        "game_id": ["2020_07_KC_DEN"],
        "season": [2020],
        "date": pd.to_datetime(["2020-10-25"]),
        "is_playoff": [False],
        "home_team": ["DEN"], "away_team": ["KC"],
        "home_score": [16], "away_score": [43],
        "home_margin": [-27],
        "home_win": pd.array([False], dtype="boolean"),
        "attendance": [5314], "capacity": [76125],
        "crowd_pct": [5314 / 76125],
        "covid_era": [True],
        "home_elo": [1500.0], "away_elo": [1600.0],
        "closing_spread": [7.0],
        "home_rest_days": pd.array([7], dtype="Int64"),
        "away_rest_days": pd.array([6], dtype="Int64"),
        "away_travel_km": [1500.0],
        "venue": ["Empower Field at Mile High"],
        "is_dome": [False],
        "temp_f": [14.0], "wind_mph": [11.0], "precip": [0.0],
        "neutral_site": [False], "relocated_home": [False], "is_bubble": [False],
    })


def test_valid_panel_passes():
    validate(valid_panel())  # must not raise


def test_columns_count_is_locked():
    assert len(COLUMNS) == 29


def test_missing_column_raises():
    df = valid_panel().drop(columns=["venue"])
    with pytest.raises(ValueError, match="venue"):
        validate(df)


def test_crowd_pct_out_of_range_raises():
    df = valid_panel()
    df["crowd_pct"] = [2.0]
    with pytest.raises(ValueError, match="crowd_pct"):
        validate(df)


def test_null_in_non_nullable_raises():
    df = valid_panel()
    df["venue"] = [None]
    with pytest.raises(ValueError, match="venue"):
        validate(df)


def test_bad_sport_value_raises():
    df = valid_panel()
    df["sport"] = ["xfl"]
    with pytest.raises(ValueError, match="sport"):
        validate(df)
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_schema.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.schema'`.

- [ ] **Step 4: Implement `src/schema.py` (structural validation)**

```python
"""Unified game-level panel schema — the single contract every sport loader
must emit and every downstream phase consumes. Sport-blind.

See docs/superpowers/specs/2026-06-29-phase1-schema-config-design.md.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd
from pandas.api import types as pdt


@dataclass(frozen=True)
class Col:
    dtype: str                      # str/int/float/bool/date/Int64/boolean
    nullable: bool = False
    min: Optional[float] = None
    max: Optional[float] = None
    values: Optional[set] = None    # allowed value set


COLUMNS: dict[str, Col] = {
    "sport":      Col("str", values={"mlb", "nba", "nfl"}),
    "game_id":    Col("str"),
    "season":     Col("int"),
    "date":       Col("date"),
    "is_playoff": Col("bool"),
    "home_team":  Col("str"),
    "away_team":  Col("str"),
    "home_score": Col("int", min=0),
    "away_score": Col("int", min=0),
    "home_margin": Col("int"),
    "home_win":   Col("boolean", nullable=True),
    "attendance": Col("int", min=0),
    "capacity":   Col("int", min=1),
    "crowd_pct":  Col("float", min=0.0, max=1.05),
    "covid_era":  Col("bool"),
    "home_elo":   Col("float"),
    "away_elo":   Col("float"),
    "closing_spread": Col("float", nullable=True),
    "home_rest_days": Col("Int64", nullable=True),
    "away_rest_days": Col("Int64", nullable=True),
    "away_travel_km": Col("float", nullable=True),
    "venue":      Col("str"),
    "is_dome":    Col("bool"),
    "temp_f":     Col("float", nullable=True),
    "wind_mph":   Col("float", nullable=True),
    "precip":     Col("float", nullable=True),
    "neutral_site":   Col("bool"),
    "relocated_home": Col("bool"),
    "is_bubble":  Col("bool"),
}


def _dtype_ok(s: pd.Series, tag: str) -> bool:
    if tag == "int":     return pdt.is_integer_dtype(s) and not isinstance(s.dtype, pd.Int64Dtype)
    if tag == "Int64":   return isinstance(s.dtype, pd.Int64Dtype)
    if tag == "float":   return pdt.is_float_dtype(s)
    if tag == "bool":    return pdt.is_bool_dtype(s) and not isinstance(s.dtype, pd.BooleanDtype)
    if tag == "boolean": return isinstance(s.dtype, pd.BooleanDtype)
    if tag == "date":    return pdt.is_datetime64_any_dtype(s)
    if tag == "str":     return pdt.is_object_dtype(s) or pdt.is_string_dtype(s)
    raise ValueError(f"unknown dtype tag {tag!r}")


def validate(df: pd.DataFrame) -> None:
    """Validate a panel against COLUMNS. Collects every violation and raises a
    single ValueError listing all of them; returns None if the panel is clean."""
    errors: list[str] = []

    missing = [c for c in COLUMNS if c not in df.columns]
    if missing:
        errors.append(f"missing columns: {missing}")

    for name, spec in COLUMNS.items():
        if name not in df.columns:
            continue
        s = df[name]

        if not _dtype_ok(s, spec.dtype):
            errors.append(f"{name}: expected dtype {spec.dtype!r}, got {s.dtype}")

        nulls = s.isna()
        if not spec.nullable and bool(nulls.any()):
            errors.append(f"{name}: {int(nulls.sum())} null(s) in non-nullable column")

        nn = s[~nulls]
        if spec.values is not None and len(nn):
            bad = set(pd.unique(nn)) - spec.values
            if bad:
                errors.append(f"{name}: values outside {spec.values}: {bad}")
        if spec.min is not None and len(nn) and bool((nn < spec.min).any()):
            errors.append(f"{name}: value(s) below min {spec.min}")
        if spec.max is not None and len(nn) and bool((nn > spec.max).any()):
            errors.append(f"{name}: value(s) above max {spec.max}")

    if errors:
        raise ValueError("panel validation failed:\n  - " + "\n  - ".join(errors))
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv/bin/pytest tests/test_schema.py -q`
Expected: PASS (6 tests).

- [ ] **Step 6: Checkpoint** — stop for user review/commit. Do not run git.

---

### Task 2: Conditional (cross-field) rules

Add the derived-column and conditional consistency checks the spec names. Forward weather rule only (`is_dome ⇒ weather null`); the reverse is deliberately NOT enforced.

**Files:**
- Modify: `src/schema.py` (add `_check_conditionals`, call it in `validate`)
- Modify: `tests/test_schema.py` (add conditional tests)

**Interfaces:**
- Consumes: `COLUMNS`, `validate` from Task 1.
- Produces: `_check_conditionals(df: pd.DataFrame, errors: list[str]) -> None` (appends violation strings; no return).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_schema.py`:

```python
def test_home_margin_must_equal_score_diff():
    df = valid_panel()
    df["home_margin"] = [99]
    with pytest.raises(ValueError, match="home_margin"):
        validate(df)


def test_weather_on_domed_game_raises():
    df = valid_panel()
    df["is_dome"] = [True]          # weather columns still populated -> leak
    with pytest.raises(ValueError, match="weather"):
        validate(df)


def test_dome_with_null_weather_passes():
    df = valid_panel()
    df["is_dome"] = [True]
    df["temp_f"] = [float("nan")]   # stay float64; pd.NA would flip dtype to object
    df["wind_mph"] = [float("nan")]
    df["precip"] = [float("nan")]
    validate(df)  # must not raise


def test_crowd_pct_must_match_attendance_over_capacity():
    df = valid_panel()
    df["crowd_pct"] = [0.5]         # inconsistent with 5314/76125
    with pytest.raises(ValueError, match="crowd_pct"):
        validate(df)


def test_home_win_must_match_margin_sign():
    df = valid_panel()
    df["home_win"] = pd.array([True], dtype="boolean")  # but margin is -27
    with pytest.raises(ValueError, match="home_win"):
        validate(df)


def test_tie_requires_null_home_win():
    df = valid_panel()
    df["home_score"] = [20]
    df["away_score"] = [20]
    df["home_margin"] = [0]
    df["home_win"] = pd.array([True], dtype="boolean")  # tie must be null
    with pytest.raises(ValueError, match="home_win"):
        validate(df)


def test_empty_stadium_crowd_pct_zero_is_valid():
    df = valid_panel()
    df["attendance"] = [0]
    df["crowd_pct"] = [0.0]
    validate(df)  # 0 is a real value, must not raise
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `.venv/bin/pytest tests/test_schema.py -q -k "margin or weather or dome or crowd_pct or home_win or tie or empty_stadium"`
Expected: FAIL — the inconsistent rows currently pass `validate()` (conditional rules not implemented), so `pytest.raises` is not triggered. (`test_dome_with_null_weather_passes` and `test_empty_stadium_crowd_pct_zero_is_valid` already pass.)

- [ ] **Step 3: Add `_check_conditionals` and call it from `validate`**

In `src/schema.py`, add this function above `validate`:

```python
def _check_conditionals(df: pd.DataFrame, errors: list[str]) -> None:
    cols = set(df.columns)

    if {"home_margin", "home_score", "away_score"} <= cols:
        bad = (df["home_margin"] != (df["home_score"] - df["away_score"]))
        if bool(bad.fillna(True).any()):
            errors.append(
                f"home_margin != home_score - away_score in {int(bad.fillna(True).sum())} row(s)")

    if {"crowd_pct", "attendance", "capacity"} <= cols:
        expected = df["attendance"] / df["capacity"]
        present = df["crowd_pct"].notna() & df["attendance"].notna() & df["capacity"].notna()
        bad = present & ((df["crowd_pct"] - expected).abs() > 0.01)
        if bool(bad.fillna(False).any()):
            errors.append(
                f"crowd_pct != attendance/capacity (tol 0.01) in {int(bad.fillna(False).sum())} row(s)")

    if {"home_win", "home_margin"} <= cols:
        hw = df["home_win"]
        decided = df["home_margin"] != 0
        margin_pos = df["home_margin"] > 0
        mism = decided & (hw.isna() | (hw.fillna(False).astype(bool) != margin_pos))
        if bool(mism.fillna(False).any()):
            errors.append(
                f"home_win inconsistent with home_margin sign in {int(mism.fillna(False).sum())} decided row(s)")
        tie_bad = (df["home_margin"] == 0) & hw.notna()
        if bool(tie_bad.fillna(False).any()):
            errors.append(
                f"home_win must be null on ties (home_margin==0) in {int(tie_bad.fillna(False).sum())} row(s)")

    if {"is_dome", "temp_f", "wind_mph", "precip"} <= cols:
        dome = df["is_dome"].astype("boolean").fillna(False)
        leak = dome & (df["temp_f"].notna() | df["wind_mph"].notna() | df["precip"].notna())
        if bool(leak.fillna(False).any()):
            errors.append(f"weather present on domed game in {int(leak.fillna(False).sum())} row(s)")
```

Then, in `validate`, insert the call immediately before the `if errors:` block:

```python
    _check_conditionals(df, errors)

    if errors:
        raise ValueError("panel validation failed:\n  - " + "\n  - ".join(errors))
```

- [ ] **Step 4: Run the full test file to verify all pass**

Run: `.venv/bin/pytest tests/test_schema.py -q`
Expected: PASS (13 tests).

- [ ] **Step 5: Checkpoint** — stop for user review/commit. Do not run git.

---

### Task 3: Fill `config/sports.yaml`

**Files:**
- Modify: `config/sports.yaml`
- Create: `tests/test_config.py`

**Interfaces:**
- Produces: `config/sports.yaml` with top-level keys `nfl`, `mlb`, `nba`, each a mapping with `treated_seasons: list[int]`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_config.py`:

```python
from pathlib import Path

import yaml

CONFIG = Path(__file__).resolve().parents[1] / "config" / "sports.yaml"


def test_config_has_three_sports_with_treated_seasons():
    cfg = yaml.safe_load(CONFIG.read_text())
    assert set(cfg) == {"nfl", "mlb", "nba"}
    for sport, body in cfg.items():
        seasons = body["treated_seasons"]
        assert isinstance(seasons, list) and seasons, f"{sport}: empty treated_seasons"
        assert all(isinstance(y, int) for y in seasons), f"{sport}: non-int season"


def test_nfl_treated_seasons_is_2020_only():
    cfg = yaml.safe_load(CONFIG.read_text())
    assert cfg["nfl"]["treated_seasons"] == [2020]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/pytest tests/test_config.py -q`
Expected: FAIL — current `config/sports.yaml` is an empty comment stub, so `yaml.safe_load` returns `None` and `set(cfg)` raises `TypeError`.

- [ ] **Step 3: Fill `config/sports.yaml`**

Replace the file contents with:

```yaml
# Per-sport COVID treatment window.
#
# covid_era seasons = the policy-restricted window where a reduced crowd_pct is
# EXOGENOUS (forced by capacity caps, not chosen by fans). The continuous
# per-game dose lives in crowd_pct; this only marks which seasons' crowd
# variation we trust as causal. Season ints follow each data source's labeling.
nfl:
  treated_seasons: [2020]        # 2021 reopened to full capacity league-wide
mlb:
  treated_seasons: [2020, 2021]  # 2020 ~empty, 2021 staggered reopen — confirm in Phase 3
nba:
  treated_seasons: [2020, 2021]  # 2020-21 empty/limited; bubble via is_bubble — confirm in Phase 3
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `.venv/bin/pytest tests/test_config.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Run the whole suite**

Run: `.venv/bin/pytest -q`
Expected: PASS (15 tests total).

- [ ] **Step 6: Checkpoint** — stop for user review/commit. Do not run git.

---

## Done-when (Phase 1 exit check)

- `.venv/bin/pytest -q` → 15 passing tests.
- `validate()` accepts a correct panel and rejects: missing column, bad dtype/null, out-of-range/bad-value, derived `home_margin` mismatch, weather-in-a-dome, `crowd_pct` ≠ attendance/capacity, `home_win`/tie inconsistency.
- `config/sports.yaml` loads with `treated_seasons` for all three sports.
