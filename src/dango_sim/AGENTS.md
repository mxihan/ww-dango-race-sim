<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-12 | Updated: 2026-05-12 -->

# dango_sim

## Purpose
Core simulation library for dango races. Provides domain models, a turn-based race engine, a Monte Carlo simulation runner, and pluggable skill/tile systems.

## Key Files

| File | Description |
|------|-------------|
| `__init__.py` | Public API re-exports: `Board`, `Dango`, `RaceConfig`, `RaceResult`, `SimulationSummary`, `run_simulations` |
| `models.py` | Domain dataclasses — `Board`, `Dango`, `RaceConfig`, `RaceState`, `RaceResult`; `Skill` and `TileEffect` protocols; `BU_KING_ID` constant |
| `engine.py` | `RaceEngine` — orchestrates a single race: rolling, turn resolution, Bu King turns, tile chaining, ranking |
| `simulation.py` | `run_simulations()` Monte Carlo runner; `SimulationSummary` frozen dataclass with win rates, average rank, average rounds |
| `skills.py` | Per-dango skill implementations: `CarlottaSkill`, `ChisaSkill`, `LynaeSkill`, `MornyeSkill`, `ShorekeeperSkill`, `AemeathSkill` |
| `tiles.py` | Tile effect implementations: `Booster` (forward), `Inhibitor` (backward), `SpaceTimeRift` (shuffle stack) |

## For AI Agents

### Working In This Directory

#### Architecture
- **models.py** defines data and protocols (no logic beyond validation/mutation helpers on `RaceState`)
- **engine.py** contains all race logic — turn order, movement, tile resolution, Bu King AI
- **skills.py** and **tiles.py** implement the `Skill` and `TileEffect` protocols via duck-typed dataclasses
- **simulation.py** is a thin runner that instantiates engines and aggregates results

#### Adding a new skill
1. Create a dataclass in `skills.py` implementing one or more hook methods: `roll_faces()`, `roll()`, `modify_roll()`, `before_move()`, `after_move()`
2. The engine calls hooks via `hasattr` checks — no registration needed
3. Add the skill to `Dango.skill` in the config and wire it in `main.py`

#### Adding a new tile
1. Create a frozen dataclass in `tiles.py` implementing `on_landed(group, position, state, rng) -> int`
2. Return the new position (same position = no further movement)
3. Place it on the `Board.tiles` mapping

#### Bu King (special participant)
- Auto-injected by the engine when `RaceConfig.include_bu_king=True`
- Starts at the finish line, moves backward each round (after round 3)
- Carries normal dangos it passes; teleports behind last place at round end

### Testing Requirements
- Corresponding test file for each module in `tests/`
- Skills: test each hook in isolation with a mock `RaceState`
- Tiles: test `on_landed` return values and state mutations
- Engine: integration tests covering full race scenarios

### Common Patterns
- Frozen dataclasses for immutable value objects (`Board`, `RaceResult`, `SimulationSummary`, tiles)
- Mutable dataclasses for stateful objects (`RaceState`, skills with `used`/`index` tracking)
- `MappingProxyType` wrapping to freeze dicts after construction
- Factory pattern: `config_factory: Callable[[], RaceConfig]` ensures fresh state per simulation

## Dependencies

### Internal
- `models.py` is imported by every other module
- `engine.py` imports from `models` and is imported by `simulation`
- `skills.py` imports `BU_KING_ID`, `Dango`, `RaceState` from `models`
- `tiles.py` imports `RaceState` from `models`

### External
- `random` (stdlib) — all randomness via `random.Random` instances
- `dataclasses`, `copy.deepcopy` — domain object construction
- `types.MappingProxyType` — frozen dict views

<!-- MANUAL: Custom project notes can be added below -->
