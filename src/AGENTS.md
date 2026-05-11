<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-12 | Updated: 2026-05-12 -->

# src

## Purpose
Source tree containing the `dango_sim` package — the entire simulation library.

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `dango_sim/` | Core simulation package with models, engine, skills, tiles, and runner (see `dango_sim/AGENTS.md`) |

## For AI Agents

### Working In This Directory
- This directory has no standalone modules; all code is inside `dango_sim/`
- pytest is configured with `pythonpath = ["src"]`, so imports use `dango_sim.*`

<!-- MANUAL: Custom project notes can be added below -->
