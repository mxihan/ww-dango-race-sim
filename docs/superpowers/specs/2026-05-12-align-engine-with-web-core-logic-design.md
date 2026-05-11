# Align Engine With Web Core Logic Design

## Goal

Update the existing Python simulator so its core race logic matches the runnable
web example while preserving the local Python API and configurable maps. The
web example's UI, tournament display, manual animation, and extra match
management features are out of scope.

## Chosen Approach

Modify the existing `RaceEngine` instead of adding a second engine.

The public API keeps the local zero-based coordinate model:

- `Board.finish` is the lap length.
- Track positions are `0..finish-1`.
- Position `0` is both start and finish.
- Custom tiles are configured on positions `1..finish-1`.

The runnable web page uses one-based display positions. Its first tile maps to
local position `0`, and its second tile maps to local position `1`.

## Scope

In scope:

- Circular movement for normal dango and Bu King.
- Race end when a normal moving group passes through position `0` after moving
  at least one step.
- Bu King joining turn order from round 3, not before.
- Bu King moving backward one step at a time and carrying contacted dango.
- Bu King round-end return check based on whether it can still contact any
  dango before reaching position `0`.
- Tile resolution modes:
  - default `single`, matching the web example.
  - optional `chain`, preserving the previous local extensibility.
- Space-time Rift preserving Bu King at the bottom of a stack.
- Aemeath path-based midpoint trigger and default waiting behavior.
- Updated tests and documentation for the new core behavior.

Out of scope:

- Web UI behavior.
- A/B/C tournament brackets.
- Manual dice override UI rules.
- The web example's additional A-group dango skills.
- Second-half fixed-start match presets.

## Board And Positioning

The board is a single-lane loop. Position `0` is the start/finish point. Moving
forward increases position modulo `finish`; moving backward decreases position
modulo `finish`.

Helpers should centralize this behavior:

- `next_position(position, steps=1)`
- `previous_position(position, steps=1)`
- path generation for forward and backward moves
- pass-through checks, especially whether a forward path passed `0`

The public zero-based model avoids changing existing callers and keeps current
README semantics valid.

## Initial State

Normal dango start stacked at position `0` by default. The stack order is the
participant order unless callers create a custom state in tests or future APIs.
Bu King is also placed at position `0`, below normal dango only when occupying
the same stack through its own placement behavior.

The web example displays normal dango at tile 2 and Bu King at tile 1. In local
coordinates these are both represented around the start/finish point, with
normal dango beginning at position `0` for API consistency.

## Turn Order And Rolls

Each round shuffles normal dango. Bu King is not included in rounds 1 and 2. In
round 3 and later, Bu King is added to the shuffled order.

Normal dango use default die faces `1, 2, 3`. Bu King uses `1..6`. Roll hooks
continue to support custom skills.

Round roll values for normal dango are prepared for skills such as Chisa. Bu
King's roll should not affect Chisa's "lowest normal dango roll" check unless a
future rule explicitly opts into that.

## Normal Movement

When a normal dango acts, it carries itself and every dango above it in the
stack. Dango below it remain in place.

The moving group advances step by step around the loop. If the path passes
position `0` after at least one step, the race ends immediately. The finishing
group ranks from top to bottom; remaining dango rank by distance to finish and
then by stack order.

If movement does not finish the race, the moving group is placed on top of the
destination stack and tile effects are resolved.

## Bu King Movement

Bu King starts acting in round 3. On its turn it rolls `1..6` and moves backward
one step at a time.

At each step:

- Bu King and any dango above it move as a group.
- When the group arrives on a position with dango, Bu King is placed below the
  contacted stack.
- The next backward step carries all dango above Bu King.

This matches the web example's "encounter then keep carrying" behavior and is
not equivalent to collecting every crossed stack in a single bulk operation.

After Bu King's movement, tile effects apply to its current stack using the same
tile resolution mode as normal movement. Bu King remains at the bottom when a
tile changes stack order.

## Bu King Round-End Return

At the end of each round from round 3 onward:

- If Bu King has any dango above it, it stays in place.
- Otherwise, check positions along Bu King's backward direction until position
  `0`.
- If no normal dango can be contacted before reaching `0`, Bu King returns to
  position `0`.
- If at least one normal dango remains ahead along that path, Bu King stays in
  place.

This replaces the old linear "compare with last-place position" check.

## Tile Resolution

`RaceConfig` gains a tile resolution mode, for example:

```python
tile_resolution: Literal["single", "chain"] = "single"
```

`single` is the default and matches the web example:

- Resolve at most the tile that the group lands on after its primary movement.
- Booster moves forward by its configured steps.
- Inhibitor moves backward by its configured steps.
- Space-time Rift randomizes the dango stack at that position.
- The destination of a Booster or Inhibitor does not trigger another tile in
  the same action.

`chain` preserves previous local behavior:

- Continue resolving tile effects until no tile applies or `max_tile_depth` is
  reached.
- Raise a clear runtime error on loops.

All tile movement uses absolute board directions: forward moves toward the
finish direction, backward moves away from it, regardless of whether Bu King is
the actor.

## Aemeath Skill

Aemeath triggers based on the movement path, not only final position.

Default behavior:

- The midpoint is `finish // 2`.
- When Aemeath is in a moving group whose path passes the midpoint for the first
  time, it checks for the nearest non-Bu-King dango ahead before position `0`.
- If a target exists, Aemeath teleports to the top of that target stack and the
  skill is consumed.
- If no target exists, Aemeath enters waiting state by default.
- While waiting, Aemeath checks again after any unit finishes moving. A
  successful teleport consumes the skill.

The existing `consume_on_fail` option remains available. When true, the skill is
consumed instead of entering or keeping waiting state if no target exists.

## Ranking

Rankings exclude Bu King.

If the race has a finishing group, that group ranks top-to-bottom first. All
remaining normal dango rank by forward distance to position `0`; smaller
distance means closer to finishing. Dango on the same position rank top to
bottom within that stack.

The engine should store enough finish context to rank a group that wins by
passing through `0` even though its modulo destination may also be `0`.

## Testing Strategy

Update tests to cover:

- Normal dango finishing by passing through `0`.
- Circular movement that does not finish when the path does not pass `0`.
- Stack pickup and top placement on a circular board.
- Bu King absent from rounds 1 and 2, present from round 3.
- Bu King stepwise backward carrying and bottom placement.
- Bu King round-end return and stay conditions.
- Single tile resolution default.
- Chain tile resolution opt-in and loop guard.
- Rift keeping Bu King at the bottom.
- Aemeath midpoint path trigger, waiting, later teleport, and consume-on-fail.
- Simulation summaries continuing to aggregate wins, average rank, and rounds.

Existing tests that assert linear positions, old Bu King turn inclusion, or
always-chained tiles should be rewritten to the new contract.

## Migration Notes

Callers can keep constructing `Board`, `RaceConfig`, `Dango`, skills, and tiles
the same way. The main behavior change is that positions are interpreted as
track coordinates on a loop rather than unbounded progress values.

Custom maps continue to use arbitrary lap lengths and arbitrary tile objects.
For a web-style 32-position map, use `Board(finish=32, tiles={...})` with tile
positions translated from web tile `n` to local position `n - 1`.
