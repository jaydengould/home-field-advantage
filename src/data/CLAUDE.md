# src/data — per-sport loaders

This is the **only** place sport-specific logic is allowed.

Every loader must return the **unified game-level panel schema** — the same
columns regardless of sport — so that everything downstream stays sport-blind.

The exact column set will be defined next session. Until then, the contract is:
one row per game, identical schema across MLB / NBA / NFL.

Loaders read from `data/raw/<sport>/` (immutable) and never overwrite it.
