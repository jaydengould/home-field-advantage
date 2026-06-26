# src/models — causal models

Holds the causal estimators: difference-in-differences (DiD), synthetic
control, and related panel methods.

**All modeling code is sport-agnostic.** It operates on the unified panel
schema produced by `src/data/` and must never branch on sport. If something
needs sport-specific handling, that belongs in `src/data/`, not here.
