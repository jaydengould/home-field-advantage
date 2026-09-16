# src/models — causal estimators

`twfe.py` (6a, dose-response, the engine) · `did.py` (6b, on/off before-after, co-primary) ·
`sensitivity.py` (robustness tables). All of it is **sport-agnostic** and must never branch on
sport — sport-specific handling belongs in `src/data/`.

`twfe._exclusion_mask` is the single shared exclusion definition; `did.py` also reuses
`_restricted_seasons` and `SPORT_COLORS` from `twfe`.

The 6a specification is **frozen** — add sensitivity columns beside it, don't re-specify it.
Why it is team FE + linear trend (and not two-way FE): `docs/design-decisions.md`.
