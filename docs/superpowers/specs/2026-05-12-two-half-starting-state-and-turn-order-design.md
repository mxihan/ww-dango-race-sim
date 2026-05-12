# Two-Half Starting State And Turn Order Design

## Goal

Update the simulator rules for two related changes:

- Turn order is decided by a separate order-roll phase instead of pure shuffle.
- A race can start from an editable half-time state file so the second half can align with real first-half results.

The simulator should expose bottom-level capabilities only. It should not automatically run a first-half simulation and feed that result into a second-half simulation, because second-half simulations may need to start from a real observed result instead of a simulated one.

## Rule Summary

Each round begins by determining the actors that are allowed to act this round, then pre-rolling both order rolls and movement rolls for those actors.

Normal dango that have not entered the race are not on the board and cannot be targeted, stacked, ranked, moved by Bu King, or considered by skills. Without a custom starting state, all normal dango begin unentered and enter only when their first turn is resolved. When a normal dango enters, it starts from position `0` and immediately moves by its movement value.

When a group crosses the finish, it is forced to position `0`. The engine does not preserve the wrapped destination. The half ends immediately when a winning condition is met, and no later actors in the already determined order act.

## Configuration

Add these fields to `RaceConfig`:

- `order_direction`: `"high_first"` or `"low_first"`. This controls whether larger or smaller order rolls act first.
- `bu_king_order_faces`: `"d3"` or `"d6"`. This controls Bu King's order roll faces when Bu King is allowed to act.
- `starting_state`: `RaceStartingState | None`. When absent, the race starts with no normal dango on the board. When present, the race starts from the provided editable state.

Keep `tile_resolution`, `include_bu_king`, and other existing configuration fields.

## Starting State JSON

Use JSON for editable starting states:

```json
{
  "positions": {
    "0": ["a", "b"],
    "7": ["bu_king", "c"],
    "30": ["d"]
  },
  "laps_completed": {
    "a": 1,
    "b": 0,
    "c": 1,
    "d": 0
  }
}
```

Rules:

- `positions` keys are stringified integer positions and must load into `0..finish-1`.
- Position arrays are stack order from bottom to top, matching `RaceState`.
- A second-half starting-state file must include every normal dango exactly once in `positions`.
- `laps_completed` records normal dango only. Missing normal dango entries are invalid for a custom starting state.
- `laps_completed` values are non-negative integers. For the intended two-half game, values are normally `0` or `1`.
- If `positions` contains `bu_king`, the engine keeps Bu King exactly where the file places it. Bu King is not reset to `0`.
- If `positions` does not contain `bu_king` and `include_bu_king=True`, the engine injects Bu King at `0`.
- Bu King does not enter any roll phase in rounds 1 and 2 of the current half, even if the starting-state file already placed Bu King on the board.

Add a `RaceStartingState` model and a small `state_io.py` module:

- `load_starting_state(path) -> RaceStartingState`
- `dump_starting_state(starting_state, path) -> None`

The IO module should not run simulations. It only reads and writes the editable format.

## Race State

Extend `RaceState` with enough data to model entered and unentered dango:

- `laps_completed: dict[str, int]`
- an entered-dango marker, either explicit `entered_ids: set[str]` or derived from the position map

Useful helpers:

- `is_entered(dango_id) -> bool`
- `enter_at_start(dango_id) -> None`
- `normal_ids_on_track() -> list[str]`

`RaceState.initial()` should support the no-starting-state opening case by creating an empty normal-dango board. Existing tests that need a stack at `0` can still construct `RaceState` directly or use an explicit helper.

## Roll Phases

Each round first determines the actors allowed to participate in the roll phases.

Normal dango:

- Without a starting state, all normal dango are candidates from round 1 even though they may not be on the board yet. When their turn comes, they enter at `0`.
- With a starting state, all normal dango from that state are candidates from round 1.

Bu King:

- Bu King is a candidate only when `include_bu_king=True` and `round_number >= 3`.
- In rounds 1 and 2, Bu King does not roll order dice, does not roll movement dice, and does not affect any roll pool, whether or not it is already placed on the board.

The two pre-roll phases are:

1. `order_rolls`
   - Determines action order.
   - Normal dango trigger dice-phase skills only.
   - Bu King rolls `1..3` when `bu_king_order_faces == "d3"` and `1..6` when it is `"d6"`.

2. `round_move_rolls`
   - Determines base movement values for the same actors.
   - Normal dango all roll together before any actor moves, triggering dice-phase skills.
   - Bu King, when eligible, also rolls movement during this phase with fixed `1..6` faces.

Action order is sorted by `order_direction`. Actors with different order-roll values never cross groups. Actors with equal order-roll values are shuffled within that equal-value group using the engine RNG.

## Skill Timing

Separate dice-phase skills from movement-modifier skills.

Dice-phase skills:

- Mornye and Shorekeeper affect dice results.
- These skills trigger once during `order_rolls` and once during `round_move_rolls`, so they can trigger twice in a single round.

Movement-modifier skills:

- Carlotta, Lynae, Chisa, and similar movement modifiers only trigger when the actor's turn is resolved.
- They do not affect `order_rolls`.
- They do not re-roll movement dice.

Chisa:

- Chisa's minimum-roll check uses the complete `round_move_rolls` for normal dango in the round.
- The check excludes Bu King.
- The check uses base movement roll results after dice-phase skills and before movement modifiers.
- Chisa's own `+2` bonus is not included in the pool used to decide whether Chisa qualifies.

Aemeath:

- Unentered dango are not valid targets.
- Path-based trigger behavior remains unchanged once Aemeath has entered and moves.

## Finish And Half Rules

The board remains a loop where position `0` is start and finish.

When a moving normal dango group passes position `0`:

- Remove that group from its old location.
- Place it at position `0`.
- Increment `laps_completed` for each normal dango in the group.
- Record `finished_group` using the same top-to-bottom winner ordering currently used by rankings.
- Stop the half immediately if any normal dango in the group reaches the win threshold.

Win threshold:

- Without a custom starting state, this is the first half. A dango wins when it completes `1` lap.
- With a custom starting state, this is the second half. Every dango wins when its cumulative `laps_completed` reaches `2`.
- Therefore, a dango with `laps_completed=1` in the starting state needs one more finish crossing. A dango with `laps_completed=0` needs two crossings in the second half.

The simulator only models first half and second half. It does not need an open-ended multi-half abstraction.

## Bu King In Second Half

When a starting state contains Bu King:

- Keep Bu King's position and stack order exactly as loaded.
- Do not move Bu King back to `0` during initialization.
- Do not let Bu King roll or act before round 3 of the current half.
- From round 3 onward, Bu King participates in order and movement pre-roll phases and acts according to its existing movement/carry rules.

When a starting state does not contain Bu King and `include_bu_king=True`, inject Bu King at `0`, but it still does not participate in roll phases until round 3.

## Simulation Statistics

Extend `SimulationSummary` with:

```python
top_n_rates: Mapping[int, Mapping[str, float]]
```

Extend `run_simulations()` with:

```python
top_n: Iterable[int] = ()
```

Keep `config_factory` as the single source of per-run configuration. Callers should put any real second-half `RaceStartingState` into the `RaceConfig` returned by the factory:

```python
starting_state = load_starting_state("second-half-start.json")

summary = run_simulations(
    config_factory=lambda: RaceConfig(
        board=board,
        participants=participants,
        starting_state=starting_state,
    ),
    runs=10000,
    seed=42,
    top_n=[3, 4],
)
```

For each `N`, `top_n_rates[N][dango_id]` is the probability that `dango_id` finished in the top `N` of `RaceResult.rankings`.

## CLI

Expose bottom-level capabilities only:

- `--starting-state PATH` loads a JSON starting state into the sample config.
- `--top-n 3 4` prints top-3 and top-4 rates.

Do not add automatic first-half-to-second-half simulation chaining.

## Testing

Add focused tests for:

- High-first and low-first action ordering.
- Equal order-roll groups being shuffled only within the same roll value.
- Mornye/Shorekeeper triggering during both order and movement pre-roll phases.
- Movement modifiers not affecting order rolls.
- Chisa reading complete normal-dango `round_move_rolls`, excluding Bu King and movement modifiers.
- No starting state creates no starting stack and enters dango on first action.
- Unentered dango are ignored by Aemeath, Bu King, ranking, and board stack interactions.
- Starting-state JSON round-trip and validation.
- Second-half `laps_completed` thresholds: `1` needs one more crossing, `0` needs two.
- Finishing places the group at `0` and stops the half immediately.
- Starting-state Bu King remains at file position but cannot roll or act before round 3.
- Bu King order faces can be configured independently from its fixed `1..6` movement roll.
- `run_simulations(top_n=[...])` reports per-N top placement rates.

## Out Of Scope

- Automatically simulating both halves in one runner call.
- Exporting every simulation's final state in batch mode.
- Generalizing to more than two halves.
- Adding a broad strategy-object rules framework.

## Self-Review

- No placeholder requirements remain.
- The design keeps the existing `RaceConfig` and `RaceEngine` architecture and avoids a second engine.
- The dice timing rules distinguish order rolls, movement pre-rolls, and movement modifiers.
- Bu King is explicitly excluded from all roll phases before round 3.
- The second-half win threshold is defined by cumulative `laps_completed` reaching `2`.
