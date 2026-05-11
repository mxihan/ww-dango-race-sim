# Dango Race Simulator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a tested Python simulator for configurable single-lane dango races with stacking, skills, tile events, Bu King, and aggregate win-rate simulation.

**Architecture:** Implement a pure rules package under `src/dango_sim` with focused modules for models, skills, tiles, engine, and batch simulation. Keep `main.py` as a thin CLI that assembles a sample race and delegates to the package.

**Tech Stack:** Python 3.12, standard library `dataclasses`, `random.Random`, `argparse`, and `pytest` for tests.

---

## File Structure

- Create `src/dango_sim/__init__.py`: package exports.
- Create `src/dango_sim/models.py`: core data classes, stack state helpers, race config, race result, and config validation.
- Create `src/dango_sim/skills.py`: skill protocol/base class and built-in dango skill implementations.
- Create `src/dango_sim/tiles.py`: tile effect protocol/base class and built-in tile implementations.
- Create `src/dango_sim/engine.py`: turn loop, movement, stacking, tile resolution, Bu King behavior, and ranking.
- Create `src/dango_sim/simulation.py`: repeated race runner and aggregate statistics.
- Modify `main.py`: command-line entry point for sample simulations.
- Modify `pyproject.toml`: package layout and pytest dependency group.
- Create `tests/test_models.py`: config and stack-state tests.
- Create `tests/test_engine.py`: movement, stacking, ranking, tile chaining, and Bu King tests.
- Create `tests/test_skills.py`: deterministic tests for built-in skills.
- Create `tests/test_tiles.py`: direct tile behavior tests.
- Create `tests/test_simulation.py`: batch simulation aggregation tests.

## Task 1: Project Test Harness

**Files:**
- Modify: `pyproject.toml`
- Create: `src/dango_sim/__init__.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write the failing package import test**

Create `tests/test_models.py`:

```python
from dango_sim.models import Board


def test_board_accepts_finish_position():
    board = Board(finish=12)

    assert board.finish == 12
```

- [ ] **Step 2: Run the import test to verify it fails**

Run: `uv run pytest tests/test_models.py::test_board_accepts_finish_position -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'dango_sim'`.

- [ ] **Step 3: Add pytest and src package layout**

Update `pyproject.toml` to include:

```toml
[project]
name = "ww-dango"
version = "0.1.0"
description = "Dango race simulator"
readme = "README.md"
requires-python = ">=3.12"
dependencies = []

[dependency-groups]
dev = [
    "pytest>=8.0",
]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

Create `src/dango_sim/__init__.py`:

```python
"""Dango race simulator package."""
```

Create `src/dango_sim/models.py` with the minimal board:

```python
from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class Board:
    finish: int
    tiles: Mapping[int, object] = field(default_factory=dict)
```

- [ ] **Step 4: Run the import test to verify it passes**

Run: `uv run pytest tests/test_models.py::test_board_accepts_finish_position -v`

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add pyproject.toml src/dango_sim/__init__.py src/dango_sim/models.py tests/test_models.py
git commit -m "test: add package test harness"
```

## Task 2: Models and Validation

**Files:**
- Modify: `src/dango_sim/models.py`
- Modify: `tests/test_models.py`

- [ ] **Step 1: Write failing model and validation tests**

Append to `tests/test_models.py`:

```python
import pytest

from dango_sim.models import Dango, RaceConfig, RaceState


def test_race_state_tracks_bottom_to_top_stacks():
    state = RaceState.initial(["a", "b", "c"], start_position=0)

    assert state.stack_at(0) == ["a", "b", "c"]
    assert state.position_of("b") == 0
    assert state.stack_index("b") == 1


def test_remove_moving_group_keeps_lower_dango_at_source():
    state = RaceState.initial(["a", "b", "c"], start_position=0)

    group = state.lift_group_from("b")

    assert group == ["b", "c"]
    assert state.stack_at(0) == ["a"]


def test_place_group_on_top_of_destination_stack():
    state = RaceState.initial(["a", "b"], start_position=0)
    state.place_group(["c", "d"], 0)

    assert state.stack_at(0) == ["a", "b", "c", "d"]
    assert state.position_of("d") == 0


def test_config_validation_rejects_duplicate_normal_dango_ids():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[
            Dango(id="same", name="A"),
            Dango(id="same", name="B"),
        ],
    )

    with pytest.raises(ValueError, match="unique"):
        config.validate()


def test_config_validation_rejects_tile_outside_board():
    config = RaceConfig(
        board=Board(finish=10, tiles={11: object()}),
        participants=[Dango(id="a", name="A")],
    )

    with pytest.raises(ValueError, match="within"):
        config.validate()
```

- [ ] **Step 2: Run the model tests to verify they fail**

Run: `uv run pytest tests/test_models.py -v`

Expected: FAIL because `Dango`, `RaceConfig`, and `RaceState` are not implemented.

- [ ] **Step 3: Implement the model layer**

Replace `src/dango_sim/models.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol


BU_KING_ID = "bu_king"


class Skill(Protocol):
    pass


class TileEffect(Protocol):
    pass


@dataclass(frozen=True)
class Board:
    finish: int
    tiles: Mapping[int, TileEffect] = field(default_factory=dict)


@dataclass
class Dango:
    id: str
    name: str
    skill: Skill | None = None
    is_special: bool = False


@dataclass
class RaceConfig:
    board: Board
    participants: list[Dango]
    include_bu_king: bool = True
    max_rounds: int = 500
    max_tile_depth: int = 20

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
            if position < 0 or position > self.board.finish:
                raise ValueError("tile positions must be within 0..finish")
        if self.max_rounds <= 0:
            raise ValueError("max_rounds must be positive")
        if self.max_tile_depth <= 0:
            raise ValueError("max_tile_depth must be positive")


@dataclass
class RaceState:
    positions: dict[int, list[str]]
    round_number: int = 0

    @classmethod
    def initial(cls, dango_ids: list[str], start_position: int = 0) -> RaceState:
        return cls(positions={start_position: list(dango_ids)})

    def stack_at(self, position: int) -> list[str]:
        return list(self.positions.get(position, []))

    def position_of(self, dango_id: str) -> int:
        for position, stack in self.positions.items():
            if dango_id in stack:
                return position
        raise KeyError(dango_id)

    def stack_index(self, dango_id: str) -> int:
        position = self.position_of(dango_id)
        return self.positions[position].index(dango_id)

    def lift_group_from(self, dango_id: str) -> list[str]:
        position = self.position_of(dango_id)
        stack = self.positions[position]
        index = stack.index(dango_id)
        group = stack[index:]
        self.positions[position] = stack[:index]
        if not self.positions[position]:
            del self.positions[position]
        return group

    def remove_ids(self, dango_ids: list[str]) -> None:
        to_remove = set(dango_ids)
        empty_positions = []
        for position, stack in self.positions.items():
            self.positions[position] = [dango_id for dango_id in stack if dango_id not in to_remove]
            if not self.positions[position]:
                empty_positions.append(position)
        for position in empty_positions:
            del self.positions[position]

    def place_group(self, group: list[str], position: int, *, bottom: bool = False) -> None:
        existing = self.positions.setdefault(position, [])
        if bottom:
            self.positions[position] = list(group) + existing
        else:
            existing.extend(group)

    def all_stacks(self) -> dict[int, list[str]]:
        return {position: list(stack) for position, stack in self.positions.items()}


@dataclass(frozen=True)
class RaceResult:
    winner_id: str
    rankings: list[str]
    rounds: int
```

- [ ] **Step 4: Run the model tests to verify they pass**

Run: `uv run pytest tests/test_models.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/dango_sim/models.py tests/test_models.py
git commit -m "feat: add race models"
```

## Task 3: Engine Movement, Stacking, and Ranking

**Files:**
- Create: `src/dango_sim/engine.py`
- Create: `tests/test_engine.py`

- [ ] **Step 1: Write failing engine tests**

Create `tests/test_engine.py`:

```python
from dango_sim.engine import RaceEngine
from dango_sim.models import Board, Dango, RaceConfig, RaceState


class FixedRng:
    def __init__(self, choices):
        self.choices = list(choices)

    def shuffle(self, values):
        return None

    def choice(self, values):
        return self.choices.pop(0)

    def random(self):
        return 0.99


def test_normal_dango_reaching_finish_ends_race_immediately():
    config = RaceConfig(
        board=Board(finish=3),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng([3]))

    result = engine.run()

    assert result.winner_id == "a"
    assert result.rankings == ["a", "b"]
    assert result.rounds == 1


def test_lower_dango_carries_dango_above_it():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B"), Dango(id="c", name="C")],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng([2]))
    engine.state = RaceState.initial(["a", "b", "c"])

    engine.take_turn("b")

    assert engine.state.stack_at(0) == ["a"]
    assert engine.state.stack_at(2) == ["b", "c"]


def test_moving_group_lands_on_top_of_destination_stack():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B"), Dango(id="c", name="C")],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng([2]))
    engine.state = RaceState(positions={0: ["a", "b"], 2: ["c"]})

    engine.take_turn("a")

    assert engine.state.stack_at(2) == ["c", "a", "b"]


def test_ranking_uses_nearest_to_finish_then_top_to_bottom():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B"), Dango(id="c", name="C")],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng([]))
    engine.state = RaceState(positions={4: ["a"], 7: ["b", "c"]})

    assert engine.rankings() == ["c", "b", "a"]
```

- [ ] **Step 2: Run engine tests to verify they fail**

Run: `uv run pytest tests/test_engine.py -v`

Expected: FAIL because `RaceEngine` is not implemented.

- [ ] **Step 3: Implement core engine movement and ranking**

Create `src/dango_sim/engine.py`:

```python
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable

from dango_sim.models import BU_KING_ID, Dango, RaceConfig, RaceResult, RaceState


@dataclass
class TurnContext:
    round_rolls: dict[str, int]
    base_roll: int
    movement: int
    blocked: bool = False


class RaceEngine:
    def __init__(self, config: RaceConfig, rng: random.Random | None = None):
        config.validate()
        self.config = config
        self.rng = rng or random.Random()
        self.dangos: dict[str, Dango] = {dango.id: dango for dango in config.participants}
        start_ids = [dango.id for dango in config.participants if not dango.is_special]
        self.state = RaceState.initial(start_ids)

    def run(self) -> RaceResult:
        for round_number in range(1, self.config.max_rounds + 1):
            self.state.round_number = round_number
            order = self.normal_ids()
            self.rng.shuffle(order)
            round_rolls = self.roll_round_values(order)
            for dango_id in order:
                if self.has_finished():
                    break
                self.take_turn(dango_id, base_roll=round_rolls[dango_id], round_rolls=round_rolls)
                if self.has_finished():
                    rankings = self.rankings()
                    return RaceResult(winner_id=rankings[0], rankings=rankings, rounds=round_number)
        raise RuntimeError("race did not finish within max_rounds")

    def normal_ids(self) -> list[str]:
        return [dango.id for dango in self.config.participants if not dango.is_special]

    def roll_round_values(self, order: Iterable[str]) -> dict[str, int]:
        return {dango_id: self.roll_for(dango_id) for dango_id in order}

    def roll_for(self, dango_id: str) -> int:
        dango = self.dangos[dango_id]
        faces = [1, 2, 3]
        if dango.skill and hasattr(dango.skill, "roll_faces"):
            faces = list(dango.skill.roll_faces(dango, self.state))
        if dango.skill and hasattr(dango.skill, "roll"):
            return int(dango.skill.roll(dango, self.state, self.rng))
        return int(self.rng.choice(faces))

    def take_turn(
        self,
        dango_id: str,
        *,
        base_roll: int | None = None,
        round_rolls: dict[str, int] | None = None,
    ) -> None:
        if base_roll is None:
            base_roll = self.roll_for(dango_id)
        context = TurnContext(round_rolls=round_rolls or {dango_id: base_roll}, base_roll=base_roll, movement=base_roll)
        dango = self.dangos[dango_id]
        if dango.skill and hasattr(dango.skill, "modify_roll"):
            context.movement = int(dango.skill.modify_roll(dango, context.movement, self.state, context, self.rng))
        if dango.skill and hasattr(dango.skill, "before_move"):
            dango.skill.before_move(dango, self.state, context, self.rng)
        if context.blocked or context.movement <= 0:
            return
        group = self.state.lift_group_from(dango_id)
        start = self.state.position_of(group[0]) if group[0] in self.dangos else 0
        destination = self.find_group_position(group, default=0) + context.movement
        self.move_group_to(group, destination)
        if dango.skill and hasattr(dango.skill, "after_move"):
            dango.skill.after_move(dango, self.state, context, self.rng, self)

    def find_group_position(self, group: list[str], default: int) -> int:
        for position, stack in self.state.positions.items():
            if any(dango_id in stack for dango_id in group):
                return position
        return default

    def move_group_to(self, group: list[str], destination: int) -> None:
        self.state.remove_ids(group)
        self.state.place_group(group, destination)
        self.resolve_tiles(group, destination)

    def resolve_tiles(self, group: list[str], position: int) -> None:
        current = position
        for _ in range(self.config.max_tile_depth):
            tile = self.config.board.tiles.get(current)
            if tile is None:
                return
            next_position = tile.on_landed(group, current, self.state, self.rng)
            if next_position == current:
                return
            self.state.remove_ids(group)
            self.state.place_group(group, next_position)
            current = next_position
        raise RuntimeError("tile resolution exceeded maximum depth")

    def has_finished(self) -> bool:
        for dango_id in self.normal_ids():
            if self.state.position_of(dango_id) >= self.config.board.finish:
                return True
        return False

    def rankings(self) -> list[str]:
        normal_ids = set(self.normal_ids())
        ordered: list[str] = []
        finish_positions = sorted(
            [position for position in self.state.positions if position >= self.config.board.finish],
            reverse=True,
        )
        for position in finish_positions:
            ordered.extend([dango_id for dango_id in reversed(self.state.stack_at(position)) if dango_id in normal_ids])
        remaining_positions = sorted(
            [position for position in self.state.positions if position < self.config.board.finish],
            reverse=True,
        )
        for position in remaining_positions:
            ordered.extend([dango_id for dango_id in reversed(self.state.stack_at(position)) if dango_id in normal_ids and dango_id not in ordered])
        return ordered
```

- [ ] **Step 4: Fix movement source tracking if the new tests expose it**

If `test_lower_dango_carries_dango_above_it` fails because the source position is lost after lifting, adjust `take_turn` to capture the source before lift:

```python
source = self.state.position_of(dango_id)
group = self.state.lift_group_from(dango_id)
destination = source + context.movement
self.move_group_to(group, destination)
```

- [ ] **Step 5: Run engine tests to verify they pass**

Run: `uv run pytest tests/test_engine.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add src/dango_sim/engine.py tests/test_engine.py
git commit -m "feat: add core race engine"
```

## Task 4: Tile Effects

**Files:**
- Create: `src/dango_sim/tiles.py`
- Create: `tests/test_tiles.py`
- Modify: `tests/test_engine.py`

- [ ] **Step 1: Write failing tile tests**

Create `tests/test_tiles.py`:

```python
from dango_sim.models import RaceState
from dango_sim.tiles import Booster, Inhibitor, SpaceTimeRift


class FixedRng:
    def shuffle(self, values):
        values.reverse()


def test_booster_moves_group_forward_one():
    state = RaceState(positions={2: ["a"]})

    assert Booster().on_landed(["a"], 2, state, FixedRng()) == 3


def test_inhibitor_moves_group_backward_one():
    state = RaceState(positions={2: ["a"]})

    assert Inhibitor().on_landed(["a"], 2, state, FixedRng()) == 1


def test_space_time_rift_reorders_stack_at_position():
    state = RaceState(positions={2: ["a", "b", "c"]})

    destination = SpaceTimeRift().on_landed(["b", "c"], 2, state, FixedRng())

    assert destination == 2
    assert state.stack_at(2) == ["c", "b", "a"]
```

Append to `tests/test_engine.py`:

```python
from dango_sim.tiles import Booster, Inhibitor


def test_engine_resolves_tile_chaining():
    config = RaceConfig(
        board=Board(finish=10, tiles={2: Booster(), 3: Booster()}),
        participants=[Dango(id="a", name="A")],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng([2]))

    engine.take_turn("a")

    assert engine.state.stack_at(4) == ["a"]


def test_engine_stops_infinite_tile_loop():
    config = RaceConfig(
        board=Board(finish=10, tiles={2: Booster(), 3: Inhibitor()}),
        participants=[Dango(id="a", name="A")],
        include_bu_king=False,
        max_tile_depth=3,
    )
    engine = RaceEngine(config, rng=FixedRng([2]))

    try:
        engine.take_turn("a")
    except RuntimeError as exc:
        assert "tile resolution" in str(exc)
    else:
        raise AssertionError("expected tile loop guard")
```

- [ ] **Step 2: Run tile tests to verify they fail**

Run: `uv run pytest tests/test_tiles.py tests/test_engine.py -v`

Expected: FAIL because `dango_sim.tiles` does not exist.

- [ ] **Step 3: Implement tile effects**

Create `src/dango_sim/tiles.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from dango_sim.models import RaceState


class TileEffect(Protocol):
    def on_landed(self, group: list[str], position: int, state: RaceState, rng) -> int:
        raise NotImplementedError


@dataclass(frozen=True)
class Booster:
    steps: int = 1

    def on_landed(self, group: list[str], position: int, state: RaceState, rng) -> int:
        return position + self.steps


@dataclass(frozen=True)
class Inhibitor:
    steps: int = 1

    def on_landed(self, group: list[str], position: int, state: RaceState, rng) -> int:
        return position - self.steps


@dataclass(frozen=True)
class SpaceTimeRift:
    def on_landed(self, group: list[str], position: int, state: RaceState, rng) -> int:
        stack = state.stack_at(position)
        rng.shuffle(stack)
        state.positions[position] = stack
        return position
```

- [ ] **Step 4: Run tile tests to verify they pass**

Run: `uv run pytest tests/test_tiles.py tests/test_engine.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/dango_sim/tiles.py tests/test_tiles.py tests/test_engine.py
git commit -m "feat: add tile effects"
```

## Task 5: Dango Skills

**Files:**
- Create: `src/dango_sim/skills.py`
- Create: `tests/test_skills.py`
- Modify: `src/dango_sim/engine.py`

- [ ] **Step 1: Write failing skill tests**

Create `tests/test_skills.py`:

```python
from dango_sim.engine import RaceEngine, TurnContext
from dango_sim.models import Board, Dango, RaceConfig, RaceState
from dango_sim.skills import AemeathSkill, CarlottaSkill, LynaeSkill, MornyeSkill, ChisaSkill, ShorekeeperSkill


class FixedRng:
    def __init__(self, choices=None, randoms=None):
        self.choices = list(choices or [])
        self.randoms = list(randoms or [])

    def shuffle(self, values):
        return None

    def choice(self, values):
        return self.choices.pop(0)

    def random(self):
        return self.randoms.pop(0)


def test_carlotta_doubles_roll_when_probability_triggers():
    skill = CarlottaSkill()
    context = TurnContext(round_rolls={"c": 2}, base_roll=2, movement=2)

    movement = skill.modify_roll(Dango(id="c", name="Carlotta"), 2, RaceState.initial(["c"]), context, FixedRng(randoms=[0.27]))

    assert movement == 4


def test_chisa_adds_two_when_roll_is_round_minimum():
    skill = ChisaSkill()
    context = TurnContext(round_rolls={"q": 1, "a": 1, "b": 3}, base_roll=1, movement=1)

    movement = skill.modify_roll(Dango(id="q", name="Chisa"), 1, RaceState.initial(["q"]), context, FixedRng())

    assert movement == 3


def test_lynae_blocked_state_wins_over_double_move():
    skill = LynaeSkill()
    context = TurnContext(round_rolls={"l": 2}, base_roll=2, movement=2)

    skill.before_move(Dango(id="l", name="Lynae"), RaceState.initial(["l"]), context, FixedRng(randoms=[0.10, 0.10]))

    assert context.blocked is True
    assert context.movement == 2


def test_lynae_can_double_when_not_blocked():
    skill = LynaeSkill()
    context = TurnContext(round_rolls={"l": 2}, base_roll=2, movement=2)

    skill.before_move(Dango(id="l", name="Lynae"), RaceState.initial(["l"]), context, FixedRng(randoms=[0.80, 0.50]))

    assert context.blocked is False
    assert context.movement == 4


def test_mornye_cycles_rolls_three_two_one():
    skill = MornyeSkill()
    dango = Dango(id="m", name="Mornye")
    state = RaceState.initial(["m"])

    assert [skill.roll(dango, state, FixedRng()) for _ in range(4)] == [3, 2, 1, 3]


def test_shorekeeper_faces_are_two_and_three():
    assert ShorekeeperSkill().roll_faces(Dango(id="s", name="Shorekeeper"), RaceState.initial(["s"])) == [2, 3]


def test_aemeath_teleports_once_to_nearest_dango_ahead():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[
            Dango(id="aemeath", name="Aemeath", skill=AemeathSkill()),
            Dango(id="near", name="Near"),
            Dango(id="far", name="Far"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng())
    engine.state = RaceState(positions={5: ["aemeath"], 7: ["near"], 9: ["far"]})
    context = TurnContext(round_rolls={"aemeath": 3}, base_roll=3, movement=3)

    config.participants[0].skill.after_move(config.participants[0], engine.state, context, FixedRng(), engine)

    assert engine.state.stack_at(7) == ["near", "aemeath"]
```

- [ ] **Step 2: Run skill tests to verify they fail**

Run: `uv run pytest tests/test_skills.py -v`

Expected: FAIL because `dango_sim.skills` does not exist.

- [ ] **Step 3: Implement built-in skills**

Create `src/dango_sim/skills.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from dango_sim.models import BU_KING_ID, Dango, RaceState


@dataclass
class CarlottaSkill:
    chance: float = 0.28

    def modify_roll(self, dango: Dango, roll: int, state: RaceState, context, rng) -> int:
        return roll * 2 if rng.random() < self.chance else roll


@dataclass
class ChisaSkill:
    bonus: int = 2

    def modify_roll(self, dango: Dango, roll: int, state: RaceState, context, rng) -> int:
        return roll + self.bonus if roll == min(context.round_rolls.values()) else roll


@dataclass
class LynaeSkill:
    blocked_chance: float = 0.20
    double_chance: float = 0.60

    def before_move(self, dango: Dango, state: RaceState, context, rng) -> None:
        if rng.random() < self.blocked_chance:
            context.blocked = True
            return
        if rng.random() < self.double_chance:
            context.movement *= 2


@dataclass
class MornyeSkill:
    sequence: tuple[int, ...] = (3, 2, 1)
    index: int = 0

    def roll(self, dango: Dango, state: RaceState, rng) -> int:
        value = self.sequence[self.index]
        self.index = (self.index + 1) % len(self.sequence)
        return value


@dataclass(frozen=True)
class ShorekeeperSkill:
    def roll_faces(self, dango: Dango, state: RaceState) -> list[int]:
        return [2, 3]


@dataclass
class AemeathSkill:
    used: bool = False

    def after_move(self, dango: Dango, state: RaceState, context, rng, engine) -> None:
        if self.used:
            return
        position = state.position_of(dango.id)
        midpoint = engine.config.board.finish / 2
        if position < midpoint:
            return
        candidates = []
        for candidate_position, stack in state.positions.items():
            if candidate_position <= position:
                continue
            if any(candidate_id != BU_KING_ID for candidate_id in stack):
                candidates.append(candidate_position)
        if not candidates:
            return
        target = min(candidates)
        group = state.lift_group_from(dango.id)
        state.place_group(group, target)
        self.used = True
```

- [ ] **Step 4: Run skill tests to verify they pass**

Run: `uv run pytest tests/test_skills.py -v`

Expected: PASS.

- [ ] **Step 5: Run engine tests again**

Run: `uv run pytest tests/test_engine.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add src/dango_sim/skills.py tests/test_skills.py src/dango_sim/engine.py
git commit -m "feat: add dango skills"
```

## Task 6: Bu King Behavior

**Files:**
- Modify: `src/dango_sim/engine.py`
- Modify: `tests/test_engine.py`

- [ ] **Step 1: Write failing Bu King tests**

Append to `tests/test_engine.py`:

```python
from dango_sim.models import BU_KING_ID


def test_bu_king_is_added_at_finish_and_excluded_from_ranking():
    config = RaceConfig(board=Board(finish=10), participants=[Dango(id="a", name="A")])
    engine = RaceEngine(config, rng=FixedRng([]))

    assert engine.state.stack_at(10) == [BU_KING_ID]
    assert BU_KING_ID not in engine.rankings()


def test_bu_king_starts_acting_on_round_three():
    config = RaceConfig(board=Board(finish=10), participants=[Dango(id="a", name="A")])
    engine = RaceEngine(config, rng=FixedRng([1]))

    engine.state.round_number = 2
    engine.take_bu_king_turn()
    assert engine.state.stack_at(10) == [BU_KING_ID]

    engine.state.round_number = 3
    engine.take_bu_king_turn()
    assert engine.state.stack_at(9) == [BU_KING_ID]


def test_bu_king_contacts_stack_and_carries_it_backward_from_bottom():
    config = RaceConfig(board=Board(finish=10), participants=[Dango(id="a", name="A"), Dango(id="b", name="B")])
    engine = RaceEngine(config, rng=FixedRng([3]))
    engine.state = RaceState(positions={10: [BU_KING_ID], 7: ["a", "b"]}, round_number=3)

    engine.take_bu_king_turn()

    assert engine.state.stack_at(7) == []
    assert engine.state.stack_at(4) == [BU_KING_ID, "a", "b"]


def test_bu_king_teleports_to_finish_when_separated_from_last_place():
    config = RaceConfig(board=Board(finish=10), participants=[Dango(id="a", name="A"), Dango(id="b", name="B")])
    engine = RaceEngine(config, rng=FixedRng([]))
    engine.state = RaceState(positions={10: [BU_KING_ID], 2: ["a"], 6: ["b"]}, round_number=3)

    engine.end_round()

    assert engine.state.stack_at(10) == [BU_KING_ID]


def test_bu_king_stays_when_on_last_place_stack():
    config = RaceConfig(board=Board(finish=10), participants=[Dango(id="a", name="A"), Dango(id="b", name="B")])
    engine = RaceEngine(config, rng=FixedRng([]))
    engine.state = RaceState(positions={2: [BU_KING_ID, "a"], 6: ["b"]}, round_number=3)

    engine.end_round()

    assert engine.state.stack_at(2) == [BU_KING_ID, "a"]
```

- [ ] **Step 2: Run Bu King tests to verify they fail**

Run: `uv run pytest tests/test_engine.py -v`

Expected: FAIL because Bu King is not implemented.

- [ ] **Step 3: Implement Bu King setup, turn, carrying, and end-round teleport**

Modify `RaceEngine.__init__` to create Bu King when configured:

```python
if config.include_bu_king:
    bu_king = Dango(id=BU_KING_ID, name="Bu King", is_special=True)
    self.dangos[BU_KING_ID] = bu_king
    self.state.place_group([BU_KING_ID], config.board.finish)
```

Add these methods to `RaceEngine`:

```python
def take_bu_king_turn(self) -> None:
    if not self.config.include_bu_king or self.state.round_number < 3:
        return
    roll = int(self.rng.choice([1, 2, 3, 4, 5, 6]))
    source = self.state.position_of(BU_KING_ID)
    target = source - roll
    contacted_positions = [
        position
        for position in self.state.positions
        if target <= position < source and any(dango_id != BU_KING_ID for dango_id in self.state.positions[position])
    ]
    if contacted_positions:
        contact = max(contacted_positions)
        stack = self.state.stack_at(contact)
        self.state.remove_ids([BU_KING_ID] + stack)
        carried_destination = contact - roll
        self.state.place_group([BU_KING_ID] + stack, carried_destination)
        self.resolve_tiles([BU_KING_ID] + stack, carried_destination)
        return
    group = self.state.lift_group_from(BU_KING_ID)
    self.move_group_to(group, target)

def end_round(self) -> None:
    if not self.config.include_bu_king:
        return
    last_position = min(self.state.position_of(dango_id) for dango_id in self.normal_ids())
    bu_position = self.state.position_of(BU_KING_ID)
    if bu_position != last_position:
        self.state.remove_ids([BU_KING_ID])
        self.state.place_group([BU_KING_ID], self.config.board.finish)
```

Modify `run()` so each round calls `take_bu_king_turn()` after normal dango actions if the race has not finished, then calls `end_round()`:

```python
if not self.has_finished():
    self.take_bu_king_turn()
if self.has_finished():
    rankings = self.rankings()
    return RaceResult(winner_id=rankings[0], rankings=rankings, rounds=round_number)
self.end_round()
```

- [ ] **Step 4: Run Bu King tests to verify they pass**

Run: `uv run pytest tests/test_engine.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add src/dango_sim/engine.py tests/test_engine.py
git commit -m "feat: add bu king behavior"
```

## Task 7: Batch Simulation and CLI

**Files:**
- Create: `src/dango_sim/simulation.py`
- Create: `tests/test_simulation.py`
- Modify: `main.py`
- Modify: `src/dango_sim/__init__.py`

- [ ] **Step 1: Write failing simulation tests**

Create `tests/test_simulation.py`:

```python
from dango_sim.models import Board, Dango, RaceConfig, RaceResult
from dango_sim.simulation import SimulationSummary, run_simulations


class StubEngine:
    results = [
        RaceResult(winner_id="a", rankings=["a", "b"], rounds=1),
        RaceResult(winner_id="b", rankings=["b", "a"], rounds=2),
        RaceResult(winner_id="a", rankings=["a", "b"], rounds=3),
    ]

    def __init__(self, config, rng):
        self.config = config
        self.rng = rng

    def run(self):
        return self.results.pop(0)


def test_run_simulations_counts_wins_and_win_rates():
    StubEngine.results = [
        RaceResult(winner_id="a", rankings=["a", "b"], rounds=1),
        RaceResult(winner_id="b", rankings=["b", "a"], rounds=2),
        RaceResult(winner_id="a", rankings=["a", "b"], rounds=3),
    ]

    summary = run_simulations(
        config_factory=lambda: RaceConfig(
            board=Board(finish=10),
            participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
            include_bu_king=False,
        ),
        runs=3,
        seed=7,
        engine_cls=StubEngine,
    )

    assert summary == SimulationSummary(
        runs=3,
        wins={"a": 2, "b": 1},
        win_rates={"a": 2 / 3, "b": 1 / 3},
        average_rank={"a": 4 / 3, "b": 5 / 3},
        average_rounds=2.0,
    )
```

- [ ] **Step 2: Run simulation tests to verify they fail**

Run: `uv run pytest tests/test_simulation.py -v`

Expected: FAIL because `dango_sim.simulation` does not exist.

- [ ] **Step 3: Implement simulation aggregation**

Create `src/dango_sim/simulation.py`:

```python
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable

from dango_sim.engine import RaceEngine
from dango_sim.models import RaceConfig


@dataclass(frozen=True)
class SimulationSummary:
    runs: int
    wins: dict[str, int]
    win_rates: dict[str, float]
    average_rank: dict[str, float]
    average_rounds: float


def run_simulations(
    *,
    config_factory: Callable[[], RaceConfig],
    runs: int,
    seed: int | None = None,
    engine_cls=RaceEngine,
) -> SimulationSummary:
    if runs <= 0:
        raise ValueError("runs must be positive")
    master_rng = random.Random(seed)
    wins: dict[str, int] = {}
    rank_totals: dict[str, int] = {}
    rank_counts: dict[str, int] = {}
    total_rounds = 0
    for _ in range(runs):
        config = config_factory()
        engine = engine_cls(config, random.Random(master_rng.randrange(2**63)))
        result = engine.run()
        wins[result.winner_id] = wins.get(result.winner_id, 0) + 1
        total_rounds += result.rounds
        for rank, dango_id in enumerate(result.rankings, start=1):
            rank_totals[dango_id] = rank_totals.get(dango_id, 0) + rank
            rank_counts[dango_id] = rank_counts.get(dango_id, 0) + 1
            wins.setdefault(dango_id, 0)
    win_rates = {dango_id: count / runs for dango_id, count in wins.items()}
    average_rank = {
        dango_id: rank_totals[dango_id] / rank_counts[dango_id]
        for dango_id in rank_totals
    }
    return SimulationSummary(
        runs=runs,
        wins=wins,
        win_rates=win_rates,
        average_rank=average_rank,
        average_rounds=total_rounds / runs,
    )
```

- [ ] **Step 4: Update package exports and CLI**

Update `src/dango_sim/__init__.py`:

```python
"""Dango race simulator package."""

from dango_sim.models import Board, Dango, RaceConfig, RaceResult
from dango_sim.simulation import SimulationSummary, run_simulations

__all__ = [
    "Board",
    "Dango",
    "RaceConfig",
    "RaceResult",
    "SimulationSummary",
    "run_simulations",
]
```

Replace `main.py`:

```python
from __future__ import annotations

import argparse

from dango_sim.models import Board, Dango, RaceConfig
from dango_sim.simulation import run_simulations
from dango_sim.skills import AemeathSkill, CarlottaSkill, LynaeSkill, MornyeSkill, ChisaSkill, ShorekeeperSkill
from dango_sim.tiles import Booster, Inhibitor, SpaceTimeRift


def build_sample_config() -> RaceConfig:
    return RaceConfig(
        board=Board(
            finish=30,
            tiles={
                4: Booster(),
                8: Inhibitor(),
                13: SpaceTimeRift(),
                19: Booster(),
                24: Inhibitor(),
            },
        ),
        participants=[
            Dango(id="carlotta", name="珂莱塔团子", skill=CarlottaSkill()),
            Dango(id="chisa", name="千咲团子", skill=ChisaSkill()),
            Dango(id="lynae", name="琳奈团子", skill=LynaeSkill()),
            Dango(id="mornye", name="莫宁团子", skill=MornyeSkill()),
            Dango(id="aemeath", name="爱弥斯团子", skill=AemeathSkill()),
            Dango(id="shorekeeper", name="守岸人团子", skill=ShorekeeperSkill()),
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run dango race simulations.")
    parser.add_argument("--runs", type=int, default=1000, help="number of simulations to run")
    parser.add_argument("--seed", type=int, default=None, help="random seed")
    args = parser.parse_args()

    summary = run_simulations(config_factory=build_sample_config, runs=args.runs, seed=args.seed)
    print(f"Runs: {summary.runs}")
    print(f"Average rounds: {summary.average_rounds:.2f}")
    for dango_id, wins in sorted(summary.wins.items(), key=lambda item: (-item[1], item[0])):
        win_rate = summary.win_rates[dango_id] * 100
        avg_rank = summary.average_rank[dango_id]
        print(f"{dango_id}: wins={wins}, win_rate={win_rate:.2f}%, average_rank={avg_rank:.2f}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run simulation tests to verify they pass**

Run: `uv run pytest tests/test_simulation.py -v`

Expected: PASS.

- [ ] **Step 6: Run the CLI smoke test**

Run: `uv run python main.py --runs 5 --seed 1`

Expected: prints `Runs: 5`, `Average rounds: ...`, and one line per sample dango.

- [ ] **Step 7: Commit**

Run:

```bash
git add src/dango_sim/simulation.py src/dango_sim/__init__.py tests/test_simulation.py main.py
git commit -m "feat: add simulation runner"
```

## Task 8: Final Verification and Documentation

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README usage**

Replace `README.md`:

```markdown
# ww-dango

Python simulator for configurable single-lane dango races.

## Run tests

```bash
uv run pytest
```

## Run sample simulations

```bash
uv run python main.py --runs 1000 --seed 42
```

The core API accepts a fresh `RaceConfig` per simulation, so callers can vary participants and boards between races.
```

- [ ] **Step 2: Run the full test suite**

Run: `uv run pytest -v`

Expected: all tests PASS.

- [ ] **Step 3: Run coverage if pytest-cov is added during implementation**

Only run this if `pytest-cov` is added to `pyproject.toml`:

Run: `uv run pytest --cov=dango_sim --cov-report=term-missing`

Expected: coverage report shows high coverage for implemented modules.

- [ ] **Step 4: Run CLI smoke test**

Run: `uv run python main.py --runs 20 --seed 42`

Expected: command exits with code 0 and prints aggregate simulation stats.

- [ ] **Step 5: Commit**

Run:

```bash
git add README.md
git commit -m "docs: add simulator usage"
```

## Self-Review

- Spec coverage: The tasks cover the package API, configurable race setup, single-lane board, stacking, immediate finish, ranking, all listed skills, all listed tiles, Bu King behavior, batch simulations, CLI output, and tests.
- Placeholder scan: The plan intentionally contains no TBD or open implementation placeholders. The only conditional step is coverage execution, which is tied to whether `pytest-cov` is added.
- Type consistency: The same model names are used across tasks: `Board`, `Dango`, `RaceConfig`, `RaceState`, `RaceResult`, `RaceEngine`, `TurnContext`, and `SimulationSummary`.
