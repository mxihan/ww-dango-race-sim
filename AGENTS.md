<!-- Generated: 2026-05-12 | Updated: 2026-05-12 -->

# ww-dango

## Purpose
Python simulator for configurable single-lane dango races. Models a board-game-style race where dango characters (each with unique skills) advance along a track with special tiles, competing to reach the finish line first.

## Key Files

| File | Description |
|------|-------------|
| `main.py` | CLI entry point — builds a sample race config and runs Monte Carlo simulations |
| `pyproject.toml` | Project metadata, dependencies (pytest), and pytest configuration |
| `README.md` | Quick-start guide for running tests and simulations |
| `uv.lock` | Lock file for uv package manager |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `src/dango_sim/` | Core simulation library (see `src/dango_sim/AGENTS.md`) |
| `tests/` | Test suite (see `tests/AGENTS.md`) |
| `docs/superpowers/` | Design plans and specifications (see `docs/superpowers/AGENTS.md`) |

## For AI Agents

### Working In This Directory
- Requires Python >=3.12
- Use `uv run` for all Python commands (e.g., `uv run pytest`, `uv run python main.py`)
- Source code lives under `src/dango_sim/`; tests under `tests/`
- pytest is configured with `pythonpath = ["src"]` and `testpaths = ["tests"]`

### Testing Requirements
- Run `uv run pytest` before committing
- Tests cover models, engine logic, skills, tiles, and simulation runner

### Common Patterns
- Dataclasses (frozen where immutable) for all domain objects
- Protocol classes for skill and tile-effect interfaces
- `RaceConfig` is created fresh per simulation run via a factory callable
- Deterministic RNG via `random.Random` with optional seed

## Dependencies

### External
- Python >=3.12 (standard library only for runtime)
- pytest >=8.0 (dev only)

<!-- MANUAL: Custom project notes can be added below -->
