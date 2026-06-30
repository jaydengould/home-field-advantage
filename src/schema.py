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
    values: Optional[frozenset] = None  # allowed value set (frozenset: keep Col hashable)


COLUMNS: dict[str, Col] = {
    "sport":      Col("str", values=frozenset({"mlb", "nba", "nfl"})),
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

    _check_conditionals(df, errors)

    if errors:
        raise ValueError("panel validation failed:\n  - " + "\n  - ".join(errors))
