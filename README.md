# home-field-advantage

A cross-sport study of home-field advantage across MLB, NBA, and NFL with two
parts: (1) **quantify** it descriptively (home win %, scoring margin) and
(2) estimate the **crowd-attributable slice** of it, using the COVID
empty/partial-stadium period (**full 2020–21 restriction window**) as a natural
experiment. The modeled outcome is **scoring margin** (more statistical power),
with **home win % reported alongside** as the intuitive number. Each sport is
analyzed separately, then combined into a cross-sport comparison, with a
paper-quality write-up rendered via Quarto (PDF + HTML).

Design: `docs/superpowers/specs/2026-06-29-home-field-advantage-design.md`.

**Status: in development — Phase 1 (schema + config) complete.**

## Progress

- ✅ **Design approved** — two-part question (descriptive + causal), continuous
  `crowd_pct` dose identified off policy capacity caps, TWFE panel estimator.
- ✅ **Pre-Phase-1 attendance spike** — confirmed `crowd_pct` is obtainable for
  NFL (ESPN attendance API + a static capacity lookup); `nfl_data_py` carries no
  attendance.
- ✅ **Phase 1 — schema contract + config** — `src/schema.py` (`validate()` over a
  29-column unified panel) and `config/sports.yaml` (per-sport COVID windows).
  15/15 tests passing.

## Roadmap (working, subject to change)

Per-sport logic lives only in `src/data/`; everything downstream is sport-blind.
NFL is the pilot — prove the vertical slice on one sport, then the others conform.

| Phase | What | Status |
|---|---|---|
| 1 | Schema contract validator + `config/sports.yaml` | ✅ done |
| 2 | NFL pilot loader → validated panel (ESPN attendance + capacity lookup) | ⏭️ next |
| 3 | MLB + NBA loaders conform to the contract | |
| 4 | Sport-blind features — Elo, `crowd_pct`, rest, travel | |
| 5 | Descriptive HFA (win% / margin by sport & season) — data sanity gate | |
| 6a | Causal — TWFE dose-response (the engine) | |
| 6b | Causal — back-pocket on/off DiD (intuitive sanity check) | |
| 7 | Bubble decomposition + seeding-games placebo | |
| 8 | Quarto write-up → PDF + HTML | |

Each phase is its own spec → plan → build loop (see `docs/superpowers/`).

## Layout

- `config/sports.yaml` — treatment windows and per-sport parameters
- `data/{raw,interim,processed}/` — raw is immutable input; the rest is derived
- `src/data/` — per-sport loaders → unified panel schema
- `src/schema.py` — the unified panel contract (`validate()`); imported everywhere
- `src/features/`, `src/models/`, `src/viz/` — sport-blind feature building, models, plots
- `results/{figures,tables}/` — generated outputs
- `paper/` — Quarto write-up + references.bib
- `tests/`

## Setup

```bash
.venv/bin/pip install -r requirements.txt   # + pytest (dev)
.venv/bin/pytest -q                          # run the test suite
```
