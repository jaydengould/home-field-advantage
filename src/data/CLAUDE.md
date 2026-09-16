# src/data — per-sport loaders

The **only** place sport-specific logic is allowed. Every loader emits the unified 29-column
panel from `src/schema.py` and passes `validate()`, so everything downstream stays sport-blind.

`_espn.py` is the shared ESPN layer (`fetch_summary`, `walk_scoreboard`, `derive_capacity`,
`check_coverage`) — reuse it; don't re-derive per sport. Loaders read `data/raw/<sport>/`
(immutable, write-once cache) and write `data/interim/<sport>.parquet`.

Rest, travel and Elo stay null/1500.0 placeholders here — `src/features/build.py` fills them.

Sourcing details and per-sport edge cases: `docs/data-pipeline.md`.
