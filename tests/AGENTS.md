<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-12 | Updated: 2026-05-12 -->

# tests

## Purpose
Pytest test suite covering the dango_sim library — models, engine, skills, tiles, and simulation runner.

## Key Files

| File | Description |
|------|-------------|
| `test_models.py` | Tests for `Board`, `Dango`, `RaceConfig` validation, `RaceState` mutations (lift, place, remove, stack operations) |
| `test_engine.py` | Integration tests for `RaceEngine` — full race runs, turn resolution, Bu King behavior, tile chaining, rankings |
| `test_skills.py` | Unit tests for each skill: `CorletaSkill` (double roll), `ChisaSkill` (min-roll bonus), `LinnaeSkill` (block/double), `MorningSkill` (fixed sequence), `ShorekeeperSkill` (custom faces), `AimisSkill` (teleport) |
| `test_tiles.py` | Tests for `Booster`, `Inhibitor`, `SpaceTimeRift` tile effects |
| `test_simulation.py` | Tests for `run_simulations()` and `SimulationSummary` — statistical accuracy, seed determinism, validation |

## For AI Agents

### Working In This Directory
- Run with `uv run pytest` (pythonpath is configured in pyproject.toml)
- Import from `dango_sim.*` directly — no sys.path hacks needed in tests
- Use `random.Random(fixed_seed)` for deterministic test scenarios
- Test helper pattern: create `RaceConfig` with minimal board/participants for focused tests

### Testing Requirements
- Each source module should have a corresponding test file
- New skills or tiles must include tests covering edge cases (blocked, zero movement, boundary positions)
- Engine tests should verify both happy paths and `RuntimeError` on max_rounds exceeded

### Common Patterns
- Inline `RaceConfig` construction for small focused tests
- `RaceState.initial()` as test fixture for state manipulation tests
- Seeded `random.Random` for deterministic skill/tile behavior verification

## Dependencies

### Internal
- `dango_sim.models` — used in all test files
- `dango_sim.engine` — used in `test_engine.py`, `test_simulation.py`
- `dango_sim.skills` — used in `test_skills.py`
- `dango_sim.tiles` — used in `test_tiles.py`
- `dango_sim.simulation` — used in `test_simulation.py`

### External
- `pytest >=8.0`
- `random` (stdlib, for seeded RNG in tests)

<!-- MANUAL: Custom project notes can be added below -->
