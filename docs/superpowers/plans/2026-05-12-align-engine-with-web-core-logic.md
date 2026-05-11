# Align Engine With Web Core Logic Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rework the existing Python race engine so its core behavior matches the runnable web example while keeping the zero-based Python API and configurable maps.

**Architecture:** Keep the current `dango_sim` package shape and modify the existing `RaceEngine`. Add small circular-board helpers and finish metadata to the engine/state model, keep skill and tile hooks pluggable, and make tile resolution mode configurable with `"single"` as the default and `"chain"` as the opt-in legacy behavior.

**Tech Stack:** Python 3, dataclasses, `random.Random`, pytest, uv.

---

## File Structure

- Modify `src/dango_sim/models.py`
  - Add `tile_resolution` validation to `RaceConfig`.
  - Add finish-context fields to `RaceState` so ranking can preserve the finishing group.
  - Keep `Board`, `Dango`, `RaceResult` public APIs stable.
- Modify `src/dango_sim/engine.py`
  - Add circular movement helpers.
  - Rework turn-order construction.
  - Rework normal movement, finishing, ranking, tile resolution, and Bu King movement.
  - Add post-action skill callback support needed by Aemeath waiting.
- Modify `src/dango_sim/skills.py`
  - Update `AemeathSkill` to use path-based midpoint detection and waiting behavior.
  - Keep existing skill class names and constructor compatibility.
- Modify `src/dango_sim/tiles.py`
  - Keep `Booster`, `Inhibitor`, and `SpaceTimeRift` interfaces.
  - Ensure Rift preserves Bu King at the bottom when present.
- Modify `tests/test_models.py`
  - Add validation tests for `tile_resolution`.
- Modify `tests/test_engine.py`
  - Replace linear movement expectations with circular movement expectations.
  - Cover single and chain tile behavior.
  - Cover Bu King round order, stepwise movement, carrying, and return check.
- Modify `tests/test_skills.py`
  - Replace Aemeath final-position tests with path-trigger and waiting tests.
- Modify `tests/test_tiles.py`
  - Add direct Rift test for Bu King bottom preservation.
- Modify `README.md`
  - Document the default single-tile behavior and optional chain behavior.
- Modify `docs/superpowers/specs/2026-05-12-dango-race-simulator-design.md`
  - Sync original design with the accepted web-aligned loop behavior.

## Implementation Notes

Keep the zero-based API:

- `finish=32` means valid positions are `0..31`.
- Position `0` is start and finish.
- A web tile number maps to local position `web_tile - 1`.
- Custom tiles remain valid only at `1..finish-1`.

Use `"single"` and `"chain"` string values for `RaceConfig.tile_resolution`. Avoid an enum unless the codebase already has one by the time this task is executed.

---

### Task 1: Add Tile Resolution Mode And Finish Context Models

**Files:**
- Modify: `src/dango_sim/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write failing model tests**

Add these tests to `tests/test_models.py`:

```python
def test_config_defaults_to_single_tile_resolution():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="a", name="A")],
    )

    assert config.tile_resolution == "single"
    config.validate()


def test_config_accepts_chain_tile_resolution():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="a", name="A")],
        tile_resolution="chain",
    )

    config.validate()


def test_config_rejects_unknown_tile_resolution():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="a", name="A")],
        tile_resolution="forever",
    )

    with pytest.raises(ValueError, match="tile_resolution"):
        config.validate()


def test_race_state_records_finishing_group():
    state = RaceState.initial(["a", "b"])

    state.finished_group = ["b", "a"]

    assert state.finished_group == ["b", "a"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_models.py -q
```

Expected: FAIL because `RaceConfig.tile_resolution` and `RaceState.finished_group` do not exist.

- [ ] **Step 3: Implement model fields and validation**

In `src/dango_sim/models.py`, update `RaceConfig` and `RaceState`:

```python
@dataclass
class RaceConfig:
    board: Board
    participants: list[Dango]
    include_bu_king: bool = True
    max_rounds: int = 500
    max_tile_depth: int = 20
    tile_resolution: str = "single"

    def validate(self) -> None:
        if self.board.finish <= 0:
            raise ValueError("board finish must be positive")
        normal_ids = [dango.id for dango in self.participants if not dango.is_special]
        if not normal_ids:
            raise ValueError("at least one normal dango must participate")
        if len(normal_ids) != len(set(normal_ids)):
            raise ValueError("normal dango ids must be unique")
        if any(dango.id == BU_KING_ID for dango in self.participants):
            raise ValueError("Bu King is managed by the engine and must not be provided")
        for position in self.board.tiles:
            if not (0 < position < self.board.finish):
                raise ValueError("tile positions must be within 1..(finish-1)")
        if self.max_rounds <= 0:
            raise ValueError("max_rounds must be positive")
        if self.max_tile_depth <= 0:
            raise ValueError("max_tile_depth must be positive")
        if self.tile_resolution not in {"single", "chain"}:
            raise ValueError("tile_resolution must be 'single' or 'chain'")
```

```python
@dataclass
class RaceState:
    positions: dict[int, list[str]]
    round_number: int = 0
    finished_group: list[str] | None = None
    finished_position: int | None = None
```

Leave existing `RaceState` methods unchanged in this task.

- [ ] **Step 4: Run model tests**

Run:

```bash
uv run pytest tests/test_models.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dango_sim/models.py tests/test_models.py
git commit -m "feat: add tile resolution mode"
```

---

### Task 2: Add Circular Board Helpers

**Files:**
- Modify: `src/dango_sim/engine.py`
- Test: `tests/test_engine.py`

- [ ] **Step 1: Write failing helper tests**

Add these tests to `tests/test_engine.py`:

```python
def test_engine_forward_path_wraps_around_finish():
    config = RaceConfig(
        board=Board(finish=5),
        participants=[Dango(id="a", name="A")],
        include_bu_king=False,
    )
    engine = RaceEngine(config)

    assert engine.forward_path(3, 4) == [4, 0, 1, 2]
    assert engine.path_passes_start(engine.forward_path(3, 4))


def test_engine_backward_path_wraps_around_start():
    config = RaceConfig(
        board=Board(finish=5),
        participants=[Dango(id="a", name="A")],
        include_bu_king=False,
    )
    engine = RaceEngine(config)

    assert engine.backward_path(1, 3) == [0, 4, 3]
```

- [ ] **Step 2: Run helper tests to verify they fail**

Run:

```bash
uv run pytest tests/test_engine.py::test_engine_forward_path_wraps_around_finish tests/test_engine.py::test_engine_backward_path_wraps_around_start -q
```

Expected: FAIL because helper methods do not exist.

- [ ] **Step 3: Implement helpers**

Add these methods to `RaceEngine` in `src/dango_sim/engine.py`:

```python
    def normalize_position(self, position: int) -> int:
        return position % self.config.board.finish

    def next_position(self, position: int, steps: int = 1) -> int:
        return (position + steps) % self.config.board.finish

    def previous_position(self, position: int, steps: int = 1) -> int:
        return (position - steps) % self.config.board.finish

    def forward_path(self, source: int, steps: int) -> list[int]:
        return [self.next_position(source, step) for step in range(1, steps + 1)]

    def backward_path(self, source: int, steps: int) -> list[int]:
        return [self.previous_position(source, step) for step in range(1, steps + 1)]

    def path_passes_start(self, path: list[int]) -> bool:
        return 0 in path
```

- [ ] **Step 4: Run helper tests**

Run:

```bash
uv run pytest tests/test_engine.py::test_engine_forward_path_wraps_around_finish tests/test_engine.py::test_engine_backward_path_wraps_around_start -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dango_sim/engine.py tests/test_engine.py
git commit -m "feat: add circular board helpers"
```

---

### Task 3: Rework Normal Movement And Ranking For Loop Finish

**Files:**
- Modify: `src/dango_sim/engine.py`
- Test: `tests/test_engine.py`

- [ ] **Step 1: Replace/add failing normal movement tests**

Update the existing linear finish tests in `tests/test_engine.py` and add:

```python
def test_normal_dango_finishes_when_forward_path_passes_start():
    config = RaceConfig(
        board=Board(finish=5),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
        include_bu_king=False,
    )
    engine = RaceEngine(config)
    engine.state.positions = {3: ["a"], 1: ["b"]}

    engine.take_turn("a", base_roll=2, round_rolls={"a": 2, "b": 1})

    assert engine.has_finished()
    assert engine.state.finished_group == ["a"]
    assert engine.rankings() == ["a", "b"]


def test_normal_dango_wraps_without_finishing_when_start_not_passed():
    config = RaceConfig(
        board=Board(finish=5),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
        include_bu_king=False,
    )
    engine = RaceEngine(config)
    engine.state.positions = {1: ["a"], 3: ["b"]}

    engine.take_turn("a", base_roll=2, round_rolls={"a": 2, "b": 1})

    assert not engine.has_finished()
    assert engine.state.positions == {3: ["b", "a"]}
    assert engine.rankings() == ["b", "a"]


def test_ranking_uses_forward_distance_to_start_and_top_to_bottom():
    config = RaceConfig(
        board=Board(finish=8),
        participants=[
            Dango(id="a", name="A"),
            Dango(id="b", name="B"),
            Dango(id="c", name="C"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config)
    engine.state.positions = {6: ["a"], 7: ["b", "c"], 2: []}

    assert engine.rankings() == ["c", "b", "a"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_engine.py::test_normal_dango_finishes_when_forward_path_passes_start tests/test_engine.py::test_normal_dango_wraps_without_finishing_when_start_not_passed tests/test_engine.py::test_ranking_uses_forward_distance_to_start_and_top_to_bottom -q
```

Expected: FAIL because movement and ranking still use linear positions.

- [ ] **Step 3: Implement loop movement and ranking**

In `RaceEngine.take_turn`, replace destination calculation and finish handling with:

```python
        source = self.state.position_of(dango_id)
        group = self.state.lift_group_from(dango_id)
        path = self.forward_path(source, context.movement)
        if self.path_passes_start(path):
            self.state.finished_group = list(group)
            self.state.finished_position = 0
            self.state.place_group(group, 0)
            self.after_any_move(group=group, path=path, actor_id=dango_id)
            return

        destination = path[-1] if path else source
        self.move_group_to(group, destination, actor_id=dango_id, path=path)
```

Change `move_group_to` signature:

```python
    def move_group_to(
        self,
        group: list[str],
        destination: int,
        *,
        actor_id: str | None = None,
        path: list[int] | None = None,
        bottom: bool = False,
    ) -> None:
        self.state.remove_ids(group)
        self.state.place_group(group, self.normalize_position(destination), bottom=bottom)
        self.resolve_tiles(group, self.normalize_position(destination))
        self.after_any_move(group=group, path=path or [self.normalize_position(destination)], actor_id=actor_id)
```

Add a callback hook that Task 7 will expand for Aemeath waiting:

```python
    def after_any_move(
        self,
        *,
        group: list[str],
        path: list[int],
        actor_id: str | None,
    ) -> None:
        return
```

Replace `has_finished`:

```python
    def has_finished(self) -> bool:
        return self.state.finished_group is not None
```

Replace `rankings` with:

```python
    def rankings(self) -> list[str]:
        normal_ids = set(self.normal_ids())
        ordered: list[str] = []

        if self.state.finished_group:
            ordered.extend(
                dango_id
                for dango_id in reversed(self.state.finished_group)
                if dango_id in normal_ids
            )

        def distance_to_finish(position: int) -> int:
            return (self.config.board.finish - position) % self.config.board.finish

        remaining_positions = sorted(
            [
                position
                for position, stack in self.state.positions.items()
                if any(dango_id in normal_ids and dango_id not in ordered for dango_id in stack)
            ],
            key=distance_to_finish,
        )
        for position in remaining_positions:
            ordered.extend(
                dango_id
                for dango_id in reversed(self.state.stack_at(position))
                if dango_id in normal_ids and dango_id not in ordered
            )

        return ordered
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
uv run pytest tests/test_engine.py::test_normal_dango_finishes_when_forward_path_passes_start tests/test_engine.py::test_normal_dango_wraps_without_finishing_when_start_not_passed tests/test_engine.py::test_ranking_uses_forward_distance_to_start_and_top_to_bottom -q
```

Expected: PASS.

- [ ] **Step 5: Run all engine tests and note expected failures**

Run:

```bash
uv run pytest tests/test_engine.py -q
```

Expected: Some old linear or Bu King tests may still fail. Do not weaken new circular tests.

- [ ] **Step 6: Commit**

```bash
git add src/dango_sim/engine.py tests/test_engine.py
git commit -m "feat: use loop movement for normal dango"
```

---

### Task 4: Implement Single Tile Resolution Default And Chain Opt-In

**Files:**
- Modify: `src/dango_sim/engine.py`
- Modify: `src/dango_sim/tiles.py`
- Test: `tests/test_engine.py`
- Test: `tests/test_tiles.py`

- [ ] **Step 1: Write failing tile tests**

Add to `tests/test_engine.py`:

```python
def test_single_tile_resolution_does_not_chain_by_default():
    config = RaceConfig(
        board=Board(finish=8, tiles={2: Booster(), 3: Booster()}),
        participants=[Dango(id="a", name="A")],
        include_bu_king=False,
    )
    engine = RaceEngine(config)
    engine.state.positions = {1: ["a"]}

    engine.take_turn("a", base_roll=1, round_rolls={"a": 1})

    assert engine.state.position_of("a") == 3


def test_chain_tile_resolution_remains_opt_in():
    config = RaceConfig(
        board=Board(finish=8, tiles={2: Booster(), 3: Booster()}),
        participants=[Dango(id="a", name="A")],
        include_bu_king=False,
        tile_resolution="chain",
    )
    engine = RaceEngine(config)
    engine.state.positions = {1: ["a"]}

    engine.take_turn("a", base_roll=1, round_rolls={"a": 1})

    assert engine.state.position_of("a") == 4


def test_chain_tile_resolution_wraps_tile_movement():
    config = RaceConfig(
        board=Board(finish=5, tiles={4: Booster()}),
        participants=[Dango(id="a", name="A")],
        include_bu_king=False,
    )
    engine = RaceEngine(config)
    engine.state.positions = {3: ["a"]}

    engine.take_turn("a", base_roll=1, round_rolls={"a": 1})

    assert engine.has_finished()
```

Add to `tests/test_tiles.py`:

```python
def test_rift_keeps_bu_king_at_bottom_when_present():
    state = RaceState(positions={2: [BU_KING_ID, "a", "b"]})
    rng = random.Random(1)

    SpaceTimeRift().on_landed(["a", "b"], 2, state, rng)

    assert state.positions[2][-1] != BU_KING_ID
    assert state.positions[2][0] == BU_KING_ID
    assert sorted(state.positions[2][1:]) == ["a", "b"]
```

Ensure `tests/test_tiles.py` imports `random` and `BU_KING_ID`:

```python
import random

from dango_sim.models import BU_KING_ID, RaceState
```

- [ ] **Step 2: Run tile tests to verify they fail**

Run:

```bash
uv run pytest tests/test_engine.py::test_single_tile_resolution_does_not_chain_by_default tests/test_engine.py::test_chain_tile_resolution_remains_opt_in tests/test_engine.py::test_chain_tile_resolution_wraps_tile_movement tests/test_tiles.py::test_rift_keeps_bu_king_at_bottom_when_present -q
```

Expected: FAIL because tile resolution still always chains and Rift does not preserve Bu King.

- [ ] **Step 3: Implement tile movement path and resolution modes**

Update `RaceEngine.resolve_tiles`:

```python
    def resolve_tiles(self, group: list[str], position: int) -> None:
        if self.config.tile_resolution == "single":
            self.resolve_single_tile(group, position)
            return

        self.resolve_chained_tiles(group, position)

    def resolve_single_tile(self, group: list[str], position: int) -> None:
        current = self.normalize_position(position)
        tile = self.config.board.tiles.get(current)
        if tile is None:
            return

        next_position = self.normalize_position(tile.on_landed(group, current, self.state, self.rng))
        if next_position == current:
            return

        path = self.tile_path(current, next_position)
        if self.path_passes_start(path):
            self.state.finished_group = list(group)
            self.state.finished_position = 0
            self.state.remove_ids(group)
            self.state.place_group(group, 0)
            return

        self.state.remove_ids(group)
        self.state.place_group(group, next_position)

    def resolve_chained_tiles(self, group: list[str], position: int) -> None:
        current = self.normalize_position(position)
        for _ in range(self.config.max_tile_depth):
            tile = self.config.board.tiles.get(current)
            if tile is None:
                return

            next_position = self.normalize_position(tile.on_landed(group, current, self.state, self.rng))
            if next_position == current:
                return

            path = self.tile_path(current, next_position)
            if self.path_passes_start(path):
                self.state.finished_group = list(group)
                self.state.finished_position = 0
                self.state.remove_ids(group)
                self.state.place_group(group, 0)
                return

            self.state.remove_ids(group)
            self.state.place_group(group, next_position)
            current = next_position

        if self.config.board.tiles.get(current) is None:
            return
        raise RuntimeError("tile resolution exceeded maximum depth")

    def tile_path(self, source: int, destination: int) -> list[int]:
        source = self.normalize_position(source)
        destination = self.normalize_position(destination)
        if source == destination:
            return []
        forward_steps = (destination - source) % self.config.board.finish
        backward_steps = (source - destination) % self.config.board.finish
        if forward_steps <= backward_steps:
            return self.forward_path(source, forward_steps)
        return self.backward_path(source, backward_steps)
```

The `tile_path` helper infers shortest direction from the returned position. If a custom tile can move more than half the board and needs exact pass-through semantics, that tile should be modeled with a richer movement result in a separate design; do not add that abstraction in this task.

- [ ] **Step 4: Preserve Bu King in Rift**

Update `SpaceTimeRift.on_landed` in `src/dango_sim/tiles.py`:

```python
@dataclass(frozen=True)
class SpaceTimeRift:
    def on_landed(self, group: list[str], position: int, state: RaceState, rng) -> int:
        stack = state.stack_at(position)
        has_bu_king = BU_KING_ID in stack
        normal_stack = [dango_id for dango_id in stack if dango_id != BU_KING_ID]
        rng.shuffle(normal_stack)
        state.positions[position] = (
            [BU_KING_ID, *normal_stack] if has_bu_king else normal_stack
        )
        return position
```

Add the import:

```python
from dango_sim.models import BU_KING_ID, RaceState
```

- [ ] **Step 5: Run tile tests**

Run:

```bash
uv run pytest tests/test_engine.py::test_single_tile_resolution_does_not_chain_by_default tests/test_engine.py::test_chain_tile_resolution_remains_opt_in tests/test_engine.py::test_chain_tile_resolution_wraps_tile_movement tests/test_tiles.py::test_rift_keeps_bu_king_at_bottom_when_present -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/dango_sim/engine.py src/dango_sim/tiles.py tests/test_engine.py tests/test_tiles.py
git commit -m "feat: support single tile resolution"
```

---

### Task 5: Rework Bu King Turn Order And Stepwise Carrying

**Files:**
- Modify: `src/dango_sim/engine.py`
- Test: `tests/test_engine.py`

- [ ] **Step 1: Write failing Bu King tests**

Add or replace tests in `tests/test_engine.py`:

```python
def test_bu_king_starts_at_zero_and_is_excluded_from_ranking():
    config = RaceConfig(board=Board(finish=10), participants=[Dango(id="a", name="A")])
    engine = RaceEngine(config)

    assert engine.state.position_of(BU_KING_ID) == 0
    assert BU_KING_ID not in engine.rankings()


def test_round_order_excludes_bu_king_before_round_three():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
    )
    engine = RaceEngine(config, random.Random(1))

    assert BU_KING_ID not in engine.build_round_order(1)
    assert BU_KING_ID not in engine.build_round_order(2)
    assert BU_KING_ID in engine.build_round_order(3)


def test_bu_king_moves_backward_stepwise_and_carries_contacted_dango():
    config = RaceConfig(
        board=Board(finish=8),
        participants=[
            Dango(id="a", name="A"),
            Dango(id="b", name="B"),
            Dango(id="c", name="C"),
        ],
    )
    engine = RaceEngine(config)
    engine.state.round_number = 3
    engine.state.positions = {0: [BU_KING_ID], 7: ["a"], 6: ["b", "c"]}

    engine.take_bu_king_turn(base_roll=2)

    assert engine.state.positions == {6: [BU_KING_ID, "b", "c", "a"]}


def test_bu_king_tile_effect_keeps_bu_king_at_bottom():
    config = RaceConfig(
        board=Board(finish=8, tiles={6: SpaceTimeRift()}),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
    )
    engine = RaceEngine(config, random.Random(1))
    engine.state.round_number = 3
    engine.state.positions = {0: [BU_KING_ID], 7: ["a"], 6: ["b"]}

    engine.take_bu_king_turn(base_roll=2)

    assert engine.state.positions[6][0] == BU_KING_ID
    assert sorted(engine.state.positions[6][1:]) == ["a", "b"]
```

Ensure `tests/test_engine.py` imports `SpaceTimeRift`:

```python
from dango_sim.tiles import Booster, Inhibitor, SpaceTimeRift
```

- [ ] **Step 2: Run Bu King tests to verify they fail**

Run:

```bash
uv run pytest tests/test_engine.py::test_bu_king_starts_at_zero_and_is_excluded_from_ranking tests/test_engine.py::test_round_order_excludes_bu_king_before_round_three tests/test_engine.py::test_bu_king_moves_backward_stepwise_and_carries_contacted_dango tests/test_engine.py::test_bu_king_tile_effect_keeps_bu_king_at_bottom -q
```

Expected: FAIL because Bu King currently starts at `finish`, appears in order before round 3, and moves in bulk.

- [ ] **Step 3: Update Bu King initialization and order builder**

In `RaceEngine.__init__`, place Bu King at `0`:

```python
            self.state.place_group([BU_KING_ID], 0, bottom=True)
```

Add order builder:

```python
    def build_round_order(self, round_number: int) -> list[str]:
        order = self.normal_ids()
        if self.config.include_bu_king and round_number >= 3:
            order.append(BU_KING_ID)
        self.rng.shuffle(order)
        return order
```

In `run`, replace manual order construction with:

```python
            order = self.build_round_order(round_number)
```

Keep `round_rolls` limited to normal dango:

```python
            round_rolls = self.roll_round_values(
                dango_id for dango_id in order if dango_id != BU_KING_ID
            )
```

- [ ] **Step 4: Implement stepwise Bu King movement**

Replace `take_bu_king_turn` with:

```python
    def take_bu_king_turn(self, base_roll: int | None = None) -> None:
        if not self.config.include_bu_king or self.state.round_number < 3:
            return

        roll = int(base_roll if base_roll is not None else self.rng.choice([1, 2, 3, 4, 5, 6]))
        path: list[int] = []
        group = self.bu_king_group()
        for _ in range(roll):
            source = self.state.position_of(BU_KING_ID)
            group = self.bu_king_group()
            self.state.remove_ids(group)
            destination = self.previous_position(source)
            existing = self.state.stack_at(destination)
            self.state.remove_ids(existing)
            merged = [BU_KING_ID, *existing, *[dango_id for dango_id in group if dango_id != BU_KING_ID]]
            self.state.place_group(merged, destination)
            path.append(destination)

        final_group = self.bu_king_group()
        self.resolve_tiles(final_group, self.state.position_of(BU_KING_ID))
        self.after_any_move(group=final_group, path=path, actor_id=BU_KING_ID)

    def bu_king_group(self) -> list[str]:
        position = self.state.position_of(BU_KING_ID)
        stack = self.state.stack_at(position)
        index = stack.index(BU_KING_ID)
        return stack[index:]
```

This code assumes stack order is bottom-to-top and Bu King is at index `0` when carrying. If a test creates a stack with Bu King above other dango, `bu_king_group` still carries Bu King and everything above it.

- [ ] **Step 5: Run Bu King tests**

Run:

```bash
uv run pytest tests/test_engine.py::test_bu_king_starts_at_zero_and_is_excluded_from_ranking tests/test_engine.py::test_round_order_excludes_bu_king_before_round_three tests/test_engine.py::test_bu_king_moves_backward_stepwise_and_carries_contacted_dango tests/test_engine.py::test_bu_king_tile_effect_keeps_bu_king_at_bottom -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/dango_sim/engine.py tests/test_engine.py
git commit -m "feat: move bu king stepwise on loop"
```

---

### Task 6: Rework Bu King Round-End Return

**Files:**
- Modify: `src/dango_sim/engine.py`
- Test: `tests/test_engine.py`

- [ ] **Step 1: Write failing return tests**

Add to `tests/test_engine.py`:

```python
def test_bu_king_returns_to_zero_when_no_dango_ahead_before_start():
    config = RaceConfig(
        board=Board(finish=8),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
    )
    engine = RaceEngine(config)
    engine.state.round_number = 3
    engine.state.positions = {5: [BU_KING_ID], 6: ["a"], 7: ["b"]}

    engine.end_round()

    assert engine.state.position_of(BU_KING_ID) == 0


def test_bu_king_stays_when_dango_ahead_before_start():
    config = RaceConfig(
        board=Board(finish=8),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
    )
    engine = RaceEngine(config)
    engine.state.round_number = 3
    engine.state.positions = {5: [BU_KING_ID], 4: ["a"], 7: ["b"]}

    engine.end_round()

    assert engine.state.position_of(BU_KING_ID) == 5


def test_bu_king_stays_when_carrying_dango_above_it():
    config = RaceConfig(
        board=Board(finish=8),
        participants=[Dango(id="a", name="A")],
    )
    engine = RaceEngine(config)
    engine.state.round_number = 3
    engine.state.positions = {5: [BU_KING_ID, "a"]}

    engine.end_round()

    assert engine.state.position_of(BU_KING_ID) == 5
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_engine.py::test_bu_king_returns_to_zero_when_no_dango_ahead_before_start tests/test_engine.py::test_bu_king_stays_when_dango_ahead_before_start tests/test_engine.py::test_bu_king_stays_when_carrying_dango_above_it -q
```

Expected: FAIL because the current return check is linear.

- [ ] **Step 3: Implement return helpers**

Replace `end_round` and add helpers:

```python
    def end_round(self) -> None:
        if not self.config.include_bu_king or self.state.round_number < 3:
            return
        if self.bu_king_has_dango_above():
            return
        if not self.has_normal_dango_ahead_of_bu_king():
            self.state.remove_ids([BU_KING_ID])
            self.state.place_group([BU_KING_ID], 0, bottom=True)

    def bu_king_has_dango_above(self) -> bool:
        position = self.state.position_of(BU_KING_ID)
        stack = self.state.stack_at(position)
        index = stack.index(BU_KING_ID)
        return any(dango_id in self.normal_ids() for dango_id in stack[index + 1 :])

    def has_normal_dango_ahead_of_bu_king(self) -> bool:
        normal_ids = set(self.normal_ids())
        position = self.state.position_of(BU_KING_ID)
        current = position
        while current != 0:
            current = self.previous_position(current)
            if any(dango_id in normal_ids for dango_id in self.state.stack_at(current)):
                return True
        return False
```

- [ ] **Step 4: Run return tests**

Run:

```bash
uv run pytest tests/test_engine.py::test_bu_king_returns_to_zero_when_no_dango_ahead_before_start tests/test_engine.py::test_bu_king_stays_when_dango_ahead_before_start tests/test_engine.py::test_bu_king_stays_when_carrying_dango_above_it -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dango_sim/engine.py tests/test_engine.py
git commit -m "feat: align bu king return check"
```

---

### Task 7: Rework Aemeath Path Trigger And Waiting

**Files:**
- Modify: `src/dango_sim/skills.py`
- Modify: `src/dango_sim/engine.py`
- Test: `tests/test_skills.py`

- [ ] **Step 1: Write failing Aemeath tests**

Replace old final-position Aemeath tests or add:

```python
def test_aemeath_triggers_when_movement_path_passes_midpoint():
    skill = AemeathSkill()
    config = RaceConfig(
        board=Board(finish=10),
        participants=[
            Dango(id="aemeath", name="Aemeath", skill=skill),
            Dango(id="target", name="Target"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config)
    engine.state.positions = {4: ["aemeath"], 8: ["target"]}

    engine.take_turn("aemeath", base_roll=2, round_rolls={"aemeath": 2, "target": 1})

    assert skill.used
    assert engine.state.positions[8] == ["target", "aemeath"]


def test_aemeath_waits_when_no_target_after_midpoint():
    skill = AemeathSkill()
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="aemeath", name="Aemeath", skill=skill)],
        include_bu_king=False,
    )
    engine = RaceEngine(config)
    engine.state.positions = {4: ["aemeath"]}

    engine.take_turn("aemeath", base_roll=2, round_rolls={"aemeath": 2})

    assert not skill.used
    assert skill.waiting


def test_aemeath_waiting_rechecks_after_any_move():
    skill = AemeathSkill()
    config = RaceConfig(
        board=Board(finish=12),
        participants=[
            Dango(id="aemeath", name="Aemeath", skill=skill),
            Dango(id="target", name="Target"),
            Dango(id="other", name="Other"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config)
    engine.state.positions = {5: ["aemeath"], 2: ["target"], 1: ["other"]}

    engine.take_turn("aemeath", base_roll=1, round_rolls={"aemeath": 1, "target": 1, "other": 1})
    assert skill.waiting

    engine.take_turn("target", base_roll=5, round_rolls={"aemeath": 1, "target": 5, "other": 1})

    assert skill.used
    assert not skill.waiting
    assert engine.state.positions[7] == ["target", "aemeath"]


def test_aemeath_consume_on_fail_consumes_instead_of_waiting():
    skill = AemeathSkill(consume_on_fail=True)
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="aemeath", name="Aemeath", skill=skill)],
        include_bu_king=False,
    )
    engine = RaceEngine(config)
    engine.state.positions = {4: ["aemeath"]}

    engine.take_turn("aemeath", base_roll=2, round_rolls={"aemeath": 2})

    assert skill.used
    assert not skill.waiting
```

- [ ] **Step 2: Run Aemeath tests to verify they fail**

Run:

```bash
uv run pytest tests/test_skills.py::test_aemeath_triggers_when_movement_path_passes_midpoint tests/test_skills.py::test_aemeath_waits_when_no_target_after_midpoint tests/test_skills.py::test_aemeath_waiting_rechecks_after_any_move tests/test_skills.py::test_aemeath_consume_on_fail_consumes_instead_of_waiting -q
```

Expected: FAIL because Aemeath still uses final position and has no waiting state.

- [ ] **Step 3: Update AemeathSkill state and hooks**

Replace `AemeathSkill` in `src/dango_sim/skills.py`:

```python
@dataclass
class AemeathSkill:
    used: bool = False
    consume_on_fail: bool = False
    waiting: bool = False
    midpoint: int | None = None

    def after_move(self, dango: Dango, state: RaceState, context, rng, engine) -> None:
        path = getattr(context, "path", [])
        group = getattr(context, "group", [dango.id])
        if dango.id not in group:
            return
        midpoint = self.midpoint if self.midpoint is not None else engine.config.board.finish // 2
        if midpoint not in path:
            return
        self.try_teleport(dango, state, engine, enter_wait=True)

    def after_any_move(self, dango: Dango, state: RaceState, context, rng, engine) -> None:
        if self.used or not self.waiting:
            return
        self.try_teleport(dango, state, engine, enter_wait=False)

    def try_teleport(self, dango: Dango, state: RaceState, engine, *, enter_wait: bool) -> None:
        if self.used:
            return
        position = state.position_of(dango.id)
        target = engine.nearest_normal_dango_ahead(position, exclude_id=dango.id)
        if target is None:
            if self.consume_on_fail:
                self.used = True
                self.waiting = False
            elif enter_wait:
                self.waiting = True
            return

        target_position, _target_id = target
        state.remove_ids([dango.id])
        state.place_group([dango.id], target_position)
        self.used = True
        self.waiting = False
```

- [ ] **Step 4: Pass movement context to skills and add target helper**

Update `TurnContext` in `src/dango_sim/engine.py`:

```python
@dataclass
class TurnContext:
    round_rolls: dict[str, int]
    base_roll: int
    movement: int
    blocked: bool = False
    path: list[int] = field(default_factory=list)
    group: list[str] = field(default_factory=list)
```

Add the import:

```python
from dataclasses import dataclass, field
```

In `take_turn`, after `group` and `path` are known, set:

```python
        context.group = list(group)
        context.path = list(path)
```

Keep the existing skill `after_move` call after movement/tile resolution:

```python
        if dango.skill and hasattr(dango.skill, "after_move"):
            dango.skill.after_move(dango, self.state, context, self.rng, self)
```

Add helper to `RaceEngine`:

```python
    def nearest_normal_dango_ahead(
        self,
        position: int,
        *,
        exclude_id: str | None = None,
    ) -> tuple[int, str] | None:
        normal_ids = set(self.normal_ids())
        if exclude_id is not None:
            normal_ids.discard(exclude_id)
        current = self.normalize_position(position)
        while True:
            current = self.next_position(current)
            if current == 0:
                return None
            for dango_id in reversed(self.state.stack_at(current)):
                if dango_id in normal_ids:
                    return current, dango_id
```

Update `after_any_move`:

```python
    def after_any_move(
        self,
        *,
        group: list[str],
        path: list[int],
        actor_id: str | None,
    ) -> None:
        context = TurnContext(
            round_rolls={},
            base_roll=0,
            movement=0,
            path=list(path),
            group=list(group),
        )
        for dango in self.participants:
            if dango.skill and hasattr(dango.skill, "after_any_move"):
                dango.skill.after_any_move(dango, self.state, context, self.rng, self)
```

- [ ] **Step 5: Run Aemeath tests**

Run:

```bash
uv run pytest tests/test_skills.py::test_aemeath_triggers_when_movement_path_passes_midpoint tests/test_skills.py::test_aemeath_waits_when_no_target_after_midpoint tests/test_skills.py::test_aemeath_waiting_rechecks_after_any_move tests/test_skills.py::test_aemeath_consume_on_fail_consumes_instead_of_waiting -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/dango_sim/engine.py src/dango_sim/skills.py tests/test_skills.py
git commit -m "feat: align aemeath midpoint skill"
```

---

### Task 8: Update Full Run Behavior And Simulation Tests

**Files:**
- Modify: `src/dango_sim/engine.py`
- Modify: `tests/test_engine.py`
- Modify: `tests/test_simulation.py`

- [ ] **Step 1: Add full-run smoke tests**

Add to `tests/test_engine.py`:

```python
def test_full_loop_race_returns_valid_result():
    config = RaceConfig(
        board=Board(finish=10, tiles={3: Booster(), 6: Inhibitor()}),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
    )

    result = RaceEngine(config, random.Random(7)).run()

    assert result.winner_id in {"a", "b"}
    assert set(result.rankings) == {"a", "b"}
    assert result.rounds >= 1
```

Update any `tests/test_simulation.py` assumptions that used `board.finish` as an expected round count. Keep these existing expectations:

```python
assert summary.runs == 2
assert set(summary.wins) == {"a", "b"}
assert set(summary.average_rank) == {"a", "b"}
```

- [ ] **Step 2: Run all tests to find remaining old-contract failures**

Run:

```bash
uv run pytest -q
```

Expected: FAIL only where old linear behavior tests remain.

- [ ] **Step 3: Rewrite remaining old-contract tests**

For each failing test:

- If it asserts positions beyond `finish`, change expected positions to modulo positions.
- If it asserts Bu King is in rounds 1 or 2, change it to assert Bu King appears only from round 3.
- If it asserts tile chaining by default, set `tile_resolution="chain"` or change the expected result to single resolution.
- If it asserts ranking by highest position, change it to ranking by shortest forward distance to `0`.

Do not delete coverage without replacing it with a web-aligned assertion.

- [ ] **Step 4: Run all tests**

Run:

```bash
uv run pytest -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dango_sim/engine.py tests/test_engine.py tests/test_simulation.py
git commit -m "test: update suite for loop engine"
```

---

### Task 9: Sync Documentation And CLI Example

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-05-12-dango-race-simulator-design.md`
- Modify: `src/dango_sim/AGENTS.md`
- Modify: `main.py`

- [ ] **Step 1: Update README**

Add or revise the board section in `README.md`:

```markdown
The board is a loop. Position `0` is both start and finish, and `finish`
is the number of positions in one lap. Valid track positions are
`0..finish-1`; custom tiles live on `1..finish-1`.

Tile effects resolve once by default, matching the reference web simulator.
Set `RaceConfig(tile_resolution="chain")` to allow a tile to move a stack onto
another tile and keep resolving until no tile applies or `max_tile_depth` is
reached.
```

- [ ] **Step 2: Update original spec**

In `docs/superpowers/specs/2026-05-12-dango-race-simulator-design.md`, revise:

- Finish wording from "reaches or passes finish" to "forward path passes position `0` after moving at least one step".
- Tile section to say default is single resolution and chain is opt-in.
- Bu King section to say it is not included in turn order before round 3.
- Aemeath section to say path midpoint trigger and waiting are default.

- [ ] **Step 3: Update source AGENTS notes**

In `src/dango_sim/AGENTS.md`, revise the Bu King and tile notes:

```markdown
- Bu King starts at position `0`, joins turn order from round 3, and moves
  backward step-by-step around the loop.
- Tile resolution defaults to single-trigger behavior. Use
  `RaceConfig(tile_resolution="chain")` for chained tile maps.
```

- [ ] **Step 4: Check `main.py` sample config**

If `main.py` uses a web-style board, ensure tile positions use zero-based local positions. For a web tile `n`, configure local tile `n - 1`. Keep the sample simple:

```python
board=Board(
    finish=32,
    tiles={
        3: Booster(),
        6: SpaceTimeRift(),
        10: Inhibitor(),
    },
)
```

- [ ] **Step 5: Run docs grep and tests**

Run:

```bash
rg -n "reaches or passes finish|position >=|tile chaining|starts at the finish" README.md docs src main.py
uv run pytest -q
```

Expected: `rg` should not show stale rule text except in historical plan files. Tests should PASS.

- [ ] **Step 6: Commit**

```bash
git add README.md docs/superpowers/specs/2026-05-12-dango-race-simulator-design.md src/dango_sim/AGENTS.md main.py
git commit -m "docs: sync web-aligned engine rules"
```

---

### Task 10: Final Verification

**Files:**
- No planned source edits unless verification finds a defect.

- [ ] **Step 1: Run full test suite**

Run:

```bash
uv run pytest -q
```

Expected: PASS.

- [ ] **Step 2: Run sample simulation**

Run:

```bash
uv run python main.py --runs 20 --seed 42
```

Expected: command exits 0 and prints win rates/average ranks.

- [ ] **Step 3: Inspect git status**

Run:

```bash
git status --short
```

Expected: only intentionally untracked `.omc/` and `example/` remain, unless the user has added other local files.

- [ ] **Step 4: If any final fix was needed, commit it**

Only if Step 1 or Step 2 required changes:

```bash
git add <changed-files>
git commit -m "fix: finish web-aligned loop engine"
```

---

## Self-Review

- Spec coverage: This plan covers circular movement, zero-based API, normal finish, Bu King round order and movement, Bu King return, tile single/chain modes, Rift bottom preservation, Aemeath path trigger and waiting, tests, docs, and final verification.
- Red-flag scan: No unresolved marker text is intentionally left in the implementation steps.
- Type consistency: The plan consistently uses `RaceConfig.tile_resolution`, `RaceState.finished_group`, `RaceEngine.forward_path`, `RaceEngine.backward_path`, `RaceEngine.path_passes_start`, and `AemeathSkill.waiting`.
