# Dango Race Simulator Design

## Goal

Build a Python race simulator for a single-lane Monopoly-like board. Each race can use a different set of dango participants and a different board. The simulator must support repeated simulations and report win rates while keeping the race rules, dango skills, board tiles, and CLI runner loosely coupled and easy to test.

## Recommended Approach

Use a pure rules engine with a thin CLI wrapper.

The core package exposes Python APIs for creating boards, dango definitions, skills, and race configurations. The CLI in `main.py` only builds a sample/default race, runs a configurable number of simulations, and prints aggregate results. This keeps the simulator usable from tests and future tools without coupling the rules to command-line parsing.

## Scope

In scope:

- Single-lane loop board where position `0` is both start and finish.
- `finish` is the number of positions in one lap.
- Custom board per race.
- Custom participant list per race.
- Dango stacking and stack movement.
- Dango-specific dice and skills.
- Tile events that trigger when a dango or stack lands on a tile.
- Immediate race end when any non-special dango's forward movement path passes position `0` after moving at least one step.
- Batch simulations with win count and win rate output.
- High-coverage unit tests for existing rule behavior.

Out of scope for the first version:

- Branching maps.
- Persistent JSON/YAML scenario files.
- UI or visual replay.
- Step-overflow bounce-back rules.

## Core Concepts

### Board

`Board` represents a single-lane race track:

- `finish`: number of positions in one lap.
- `tiles`: mapping from track position to a `TileEffect`; valid custom tile positions are `1..finish-1`.

Forward means increasing position modulo `finish`; backward means decreasing position modulo `finish`. Tile effects use those absolute directions regardless of the moving dango's current travel direction.

### Dango

`Dango` describes a participant:

- `id`: stable identifier.
- `name`: display name.
- `skill`: skill object.
- `is_special`: marks non-ranking special actors such as Bu King.

Normal dango use a base die with faces `1, 2, 3`.

### Bu King Dango

Bu King is a special dango:

- Does not participate in ranking.
- Starts at position `0`.
- Begins acting in round 3.
- Rolls `1..6`.
- Moves backward step-by-step around the loop.
- Always occupies the bottom of any stack it contacts.
- If it contacts a stack while moving, it carries that stack backward.
- Tile mechanisms affect Bu King like other moving stacks.
- At round end, if Bu King is not carrying dango and cannot contact any normal dango before reaching position `0`, Bu King returns to position `0`.

### Stack Model

Each board position can hold an ordered stack of dango ids from bottom to top.

When a normal dango acts:

- If it has dango above it, it carries itself and every dango above it as one moving group.
- Dango below it remain at the source position.
- After movement and tile effects, the moving group is placed on top of any stack at the destination.

When Bu King contacts a stack:

- Bu King is placed at the bottom of the carried group.
- It carries normal dango in that stack toward the start.

### Turn Order

Each round randomizes the normal dango action order. Bu King is excluded from rounds 1 and 2, then participates from round 3 using its special movement rules. The random source is injected so tests can use deterministic rolls and order.

### Finish and Ranking

The race ends immediately when any normal dango's forward movement path passes position `0` after moving at least one step. Overshoot is allowed and does not require bounce-back.

Ranking excludes Bu King:

- If a stack finishes by passing position `0`, members of that finishing stack rank from top to bottom.
- Remaining dango rank by forward distance to position `0`, nearest first.
- Dango at the same position rank from top to bottom within their stack.

## Skill Rules

Skills use small hook methods so each dango can be tested independently:

- `roll_faces(dango, state)`: optionally replace die faces.
- `modify_roll(dango, roll, state, turn_context)`: adjust the rolled value.
- `before_move(dango, state, turn_context)`: block or change movement before movement is applied.
- `after_move(dango, state, turn_context)`: trigger effects after movement and tile resolution.
- `after_any_move(dango, state, turn_context)`: optionally react after any unit moves.

Initial skills:

- Carlotta: 28% chance to move by double the rolled points.
- Chisa: if its rolled result is one of the lowest rolled values in the current round, move 2 extra spaces.
- Lynae: each round has a 60% chance to move by double points, and a 20% chance to be unable to move. If both checks would apply, unable to move wins.
- Mornye: dice result cycles through `3, 2, 1`.
- Aemeath: once per race, after its movement path first passes the midpoint, if there is a non-Bu-King dango ahead before position `0`, teleport to the top of the nearest such dango's stack.
  If no valid target exists, the skill waits by default and rechecks after later movement. `consume_on_fail=True` keeps the opt-in failure consumption behavior.
- Shorekeeper: die only rolls `2` or `3`.

## Tile Rules

Tile effects implement `on_landed(group, position, state, rng)`.

Initial tiles:

- Booster: if a moving group lands here, move it forward 1 more space.
- Inhibitor: if a moving group lands here, move it backward 1 space.
- Space-time Rift: if a moving group lands here, randomly reshuffle the normal dango stack order at that position; Bu King stays at the bottom when present.

Tile effects resolve once by default, matching the reference web simulator. Set `RaceConfig(tile_resolution="chain")` to allow a tile to move the group onto another tile and continue resolving until no tile applies or `max_tile_depth` is reached.

## Public API Shape

Expected package layout:

- `dango_sim.models`: data classes and value objects.
- `dango_sim.skills`: built-in skill implementations.
- `dango_sim.tiles`: built-in tile effect implementations.
- `dango_sim.engine`: race execution and ranking.
- `dango_sim.simulation`: repeated simulations and aggregate statistics.
- `main.py`: CLI entry point.

Typical usage:

```python
from dango_sim.engine import RaceEngine
from dango_sim.models import Board, RaceConfig
from dango_sim.simulation import run_simulations

config = RaceConfig(
    board=Board(finish=32, tiles={5: Booster(), 9: Inhibitor()}),
    participants=[carlotta(), chisa(), shorekeeper()],
)

results = run_simulations(config_factory=lambda: config, runs=1000, seed=42)
```

`config_factory` allows each race to receive a fresh participant list, skill state, and board. Callers can return different boards or participant sets per run.

## Error Handling

The engine validates race configuration before running:

- `finish` must be positive.
- Normal dango ids must be unique.
- At least one normal dango must participate.
- Tile positions must be within `1..finish-1`; position `0` is the start/finish point and `finish` is lap length, not a board tile.
- `tile_resolution` must be `"single"` or `"chain"`.
- Bu King is created by the engine or added through a controlled config flag, not duplicated by callers.

Invalid configuration raises `ValueError` with a clear message.

## Testing Plan

Tests should cover:

- Normal loop movement and immediate finish when a forward path passes position `0`.
- Stack pickup, split, and placement on destination stack.
- Ranking by finishing stack top-to-bottom and by forward distance to position `0`.
- Each built-in skill with deterministic RNG.
- Booster, inhibitor, and rift tile behavior.
- Default single tile resolution, opt-in tile chaining, and loop guard.
- Bu King starts acting on round 3.
- Bu King carries contacted stacks backward from the bottom.
- Bu King is excluded from rankings.
- Bu King teleport behavior at round end.
- Batch simulations aggregate wins and win rates.
- Config validation errors.

Use deterministic random sources or fixed seeds so tests are stable.

## Open Decisions Resolved

- Race ends immediately when any normal dango's forward movement path passes position `0`.
- Normal dango default dice are `1, 2, 3`.
- Board is a single-lane loop track where `0` is both start and finish.
- Forward and backward are absolute board directions.
- Participants and board may differ for every race.
