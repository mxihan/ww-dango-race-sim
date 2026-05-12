# Two-Half Starting State And Turn Order Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add configurable dice-based turn order, editable second-half starting states, half-specific entry/finish rules, and top-N simulation statistics.

**Architecture:** Keep the existing `RaceConfig` + `RaceEngine` API and extend it conservatively. Add a focused `RaceStartingState` model and `state_io.py` for JSON, split engine internals into roll phases, entry handling, finish accounting, and movement modifiers, and keep batch simulation as the only statistics layer.

**Tech Stack:** Python 3.12, dataclasses, stdlib `json`/`pathlib`/`random`, pytest, uv.

---

## File Structure

- Modify `src/dango_sim/models.py`
  - Add `RaceStartingState`.
  - Add `RaceConfig.order_direction`, `RaceConfig.bu_king_order_faces`, and `RaceConfig.starting_state`.
  - Extend `RaceState` with `laps_completed` and entered-state helpers.
- Create `src/dango_sim/state_io.py`
  - Read and write editable starting-state JSON.
- Modify `src/dango_sim/engine.py`
  - Replace pure-shuffle turn order with order-roll grouping.
  - Add movement pre-rolls, entry-on-first-action, lap counting, second-half threshold logic, and Bu King roll gating.
- Modify `src/dango_sim/skills.py`
  - Make Chisa read the new base movement roll pool.
  - Keep existing skill class names and constructor compatibility.
- Modify `src/dango_sim/simulation.py`
  - Add `top_n_rates` and `top_n` aggregation.
- Modify `src/dango_sim/__init__.py`
  - Export `RaceStartingState`, `load_starting_state`, and `dump_starting_state`.
- Modify `main.py`
  - Add `--starting-state` and `--top-n`.
- Modify `README.md` and `src/dango_sim/AGENTS.md`
  - Document the new rules and JSON format.
- Add/modify tests:
  - `tests/test_models.py`
  - `tests/test_state_io.py`
  - `tests/test_engine.py`
  - `tests/test_skills.py`
  - `tests/test_simulation.py`

---

### Task 1: Add Starting-State Models And Config Validation

**Files:**
- Modify: `src/dango_sim/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write failing model tests**

Append these tests to `tests/test_models.py`:

```python
def test_config_defaults_turn_order_and_no_starting_state():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="a", name="A")],
    )

    assert config.order_direction == "high_first"
    assert config.bu_king_order_faces == "d3"
    assert config.starting_state is None
    config.validate()


def test_config_accepts_low_first_and_d6_bu_king_order_faces():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="a", name="A")],
        order_direction="low_first",
        bu_king_order_faces="d6",
    )

    config.validate()


def test_config_rejects_unknown_order_direction():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="a", name="A")],
        order_direction="sideways",
    )

    with pytest.raises(ValueError, match="order_direction"):
        config.validate()


def test_config_rejects_unknown_bu_king_order_faces():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="a", name="A")],
        bu_king_order_faces="d20",
    )

    with pytest.raises(ValueError, match="bu_king_order_faces"):
        config.validate()


def test_starting_state_copies_positions_and_laps():
    starting_state = RaceStartingState(
        positions={0: ["a"], 4: ["bu_king", "b"]},
        laps_completed={"a": 1, "b": 0},
    )

    assert starting_state.positions[4] == ("bu_king", "b")
    assert starting_state.laps_completed["a"] == 1

    with pytest.raises(TypeError):
        starting_state.positions[0] = ("b",)
```

Update imports at the top of `tests/test_models.py`:

```python
from dango_sim.models import BU_KING_ID, Board, Dango, RaceConfig, RaceResult, RaceStartingState, RaceState
```

- [ ] **Step 2: Run model tests to verify they fail**

Run:

```bash
uv run pytest tests/test_models.py::test_config_defaults_turn_order_and_no_starting_state tests/test_models.py::test_config_accepts_low_first_and_d6_bu_king_order_faces tests/test_models.py::test_config_rejects_unknown_order_direction tests/test_models.py::test_config_rejects_unknown_bu_king_order_faces tests/test_models.py::test_starting_state_copies_positions_and_laps -q
```

Expected: FAIL because `RaceStartingState`, `order_direction`, `bu_king_order_faces`, and `starting_state` do not exist.

- [ ] **Step 3: Implement model fields**

In `src/dango_sim/models.py`, add these imports:

```python
from types import MappingProxyType
from typing import Mapping, Protocol
```

Add this dataclass before `RaceConfig`:

```python
@dataclass(frozen=True)
class RaceStartingState:
    positions: Mapping[int, tuple[str, ...] | list[str]]
    laps_completed: Mapping[str, int]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "positions",
            MappingProxyType(
                {
                    int(position): tuple(stack)
                    for position, stack in self.positions.items()
                }
            ),
        )
        object.__setattr__(
            self,
            "laps_completed",
            MappingProxyType(
                {
                    str(dango_id): int(laps)
                    for dango_id, laps in self.laps_completed.items()
                }
            ),
        )
```

Update `RaceConfig` fields:

```python
@dataclass
class RaceConfig:
    board: Board
    participants: list[Dango]
    include_bu_king: bool = True
    max_rounds: int = 500
    max_tile_depth: int = 20
    tile_resolution: str = "single"
    order_direction: str = "high_first"
    bu_king_order_faces: str = "d3"
    starting_state: RaceStartingState | None = None
```

Add validation at the end of `RaceConfig.validate()`:

```python
        if self.order_direction not in {"high_first", "low_first"}:
            raise ValueError("order_direction must be 'high_first' or 'low_first'")
        if self.bu_king_order_faces not in {"d3", "d6"}:
            raise ValueError("bu_king_order_faces must be 'd3' or 'd6'")
        if self.starting_state is not None:
            self._validate_starting_state(normal_ids)
```

Add this method to `RaceConfig`:

```python
    def _validate_starting_state(self, normal_ids: list[str]) -> None:
        assert self.starting_state is not None
        seen: list[str] = []
        for position, stack in self.starting_state.positions.items():
            if not (0 <= position < self.board.finish):
                raise ValueError("starting_state positions must be within 0..(finish-1)")
            if not stack:
                raise ValueError("starting_state stacks must not be empty")
            seen.extend(dango_id for dango_id in stack if dango_id != BU_KING_ID)

        if sorted(seen) != sorted(normal_ids):
            raise ValueError("starting_state must include every normal dango exactly once")
        if len(seen) != len(set(seen)):
            raise ValueError("starting_state normal dango ids must be unique")

        lap_ids = set(self.starting_state.laps_completed)
        if lap_ids != set(normal_ids):
            raise ValueError("starting_state laps_completed must include every normal dango")
        for dango_id, laps in self.starting_state.laps_completed.items():
            if laps < 0:
                raise ValueError("starting_state laps_completed values must be non-negative")
```

- [ ] **Step 4: Run focused model tests**

Run:

```bash
uv run pytest tests/test_models.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dango_sim/models.py tests/test_models.py
git commit -m "feat: add half starting state model"
```

---

### Task 2: Add RaceState Entry And Lap Helpers

**Files:**
- Modify: `src/dango_sim/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write failing RaceState tests**

Append to `tests/test_models.py`:

```python
def test_race_state_can_start_with_no_entered_dango():
    state = RaceState.empty(["a", "b"])

    assert state.positions == {}
    assert not state.is_entered("a")
    assert state.laps_completed == {"a": 0, "b": 0}


def test_race_state_enter_at_start_places_dango_once():
    state = RaceState.empty(["a", "b"])

    state.enter_at_start("a")

    assert state.is_entered("a")
    assert state.stack_at(0) == ["a"]

    state.enter_at_start("a")
    assert state.stack_at(0) == ["a"]


def test_race_state_from_starting_state_preserves_laps_and_stacks():
    starting_state = RaceStartingState(
        positions={3: ["a", "b"]},
        laps_completed={"a": 1, "b": 0},
    )

    state = RaceState.from_starting_state(starting_state)

    assert state.positions == {3: ["a", "b"]}
    assert state.laps_completed == {"a": 1, "b": 0}
    assert state.is_entered("a")
    assert state.is_entered("b")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_models.py::test_race_state_can_start_with_no_entered_dango tests/test_models.py::test_race_state_enter_at_start_places_dango_once tests/test_models.py::test_race_state_from_starting_state_preserves_laps_and_stacks -q
```

Expected: FAIL because the new helpers and `laps_completed` field do not exist.

- [ ] **Step 3: Implement RaceState helpers**

Update `RaceState` in `src/dango_sim/models.py`:

```python
@dataclass
class RaceState:
    positions: dict[int, list[str]]
    round_number: int = 0
    finished_group: list[str] | None = None
    finished_position: int | None = None
    laps_completed: dict[str, int] = field(default_factory=dict)

    @classmethod
    def initial(cls, dango_ids: list[str], start_position: int = 0) -> RaceState:
        return cls(
            positions={start_position: list(dango_ids)},
            laps_completed={dango_id: 0 for dango_id in dango_ids},
        )

    @classmethod
    def empty(cls, dango_ids: list[str]) -> RaceState:
        return cls(
            positions={},
            laps_completed={dango_id: 0 for dango_id in dango_ids},
        )

    @classmethod
    def from_starting_state(cls, starting_state: RaceStartingState) -> RaceState:
        return cls(
            positions={
                position: list(stack)
                for position, stack in starting_state.positions.items()
            },
            laps_completed=dict(starting_state.laps_completed),
        )

    def is_entered(self, dango_id: str) -> bool:
        return any(dango_id in stack for stack in self.positions.values())

    def enter_at_start(self, dango_id: str) -> None:
        if self.is_entered(dango_id):
            return
        self.place_group([dango_id], 0)
        self.laps_completed.setdefault(dango_id, 0)
```

Keep the existing methods below these helpers unchanged.

- [ ] **Step 4: Run model tests**

Run:

```bash
uv run pytest tests/test_models.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dango_sim/models.py tests/test_models.py
git commit -m "feat: track entered dango and laps"
```

---

### Task 3: Add Starting-State JSON IO

**Files:**
- Create: `src/dango_sim/state_io.py`
- Modify: `src/dango_sim/__init__.py`
- Test: `tests/test_state_io.py`

- [ ] **Step 1: Write failing IO tests**

Create `tests/test_state_io.py`:

```python
import json

from dango_sim.models import RaceStartingState
from dango_sim.state_io import dump_starting_state, load_starting_state


def test_load_starting_state_converts_positions_to_ints_and_stacks_to_tuples(tmp_path):
    path = tmp_path / "state.json"
    path.write_text(
        json.dumps(
            {
                "positions": {"0": ["a"], "7": ["bu_king", "b"]},
                "laps_completed": {"a": 1, "b": 0},
            }
        ),
        encoding="utf-8",
    )

    state = load_starting_state(path)

    assert state == RaceStartingState(
        positions={0: ("a",), 7: ("bu_king", "b")},
        laps_completed={"a": 1, "b": 0},
    )


def test_dump_starting_state_writes_editable_json(tmp_path):
    path = tmp_path / "state.json"
    state = RaceStartingState(
        positions={3: ["a", "b"]},
        laps_completed={"a": 1, "b": 0},
    )

    dump_starting_state(state, path)

    assert json.loads(path.read_text(encoding="utf-8")) == {
        "positions": {"3": ["a", "b"]},
        "laps_completed": {"a": 1, "b": 0},
    }
```

- [ ] **Step 2: Run IO tests to verify they fail**

Run:

```bash
uv run pytest tests/test_state_io.py -q
```

Expected: FAIL because `dango_sim.state_io` does not exist.

- [ ] **Step 3: Implement state_io**

Create `src/dango_sim/state_io.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from dango_sim.models import RaceStartingState


def load_starting_state(path: str | Path) -> RaceStartingState:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return RaceStartingState(
        positions={
            int(position): list(stack)
            for position, stack in payload["positions"].items()
        },
        laps_completed={
            str(dango_id): int(laps)
            for dango_id, laps in payload["laps_completed"].items()
        },
    )


def dump_starting_state(starting_state: RaceStartingState, path: str | Path) -> None:
    payload = {
        "positions": {
            str(position): list(stack)
            for position, stack in starting_state.positions.items()
        },
        "laps_completed": dict(starting_state.laps_completed),
    }
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
```

Update `src/dango_sim/__init__.py`:

```python
from dango_sim.models import Board, Dango, RaceConfig, RaceResult, RaceStartingState
from dango_sim.state_io import dump_starting_state, load_starting_state
```

Add these names to `__all__`:

```python
    "RaceStartingState",
    "dump_starting_state",
    "load_starting_state",
```

- [ ] **Step 4: Run IO tests**

Run:

```bash
uv run pytest tests/test_state_io.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dango_sim/state_io.py src/dango_sim/__init__.py tests/test_state_io.py
git commit -m "feat: add starting state json io"
```

---

### Task 4: Add Dice-Based Turn Order And Pre-Roll Movement

**Files:**
- Modify: `src/dango_sim/engine.py`
- Modify: `src/dango_sim/skills.py`
- Test: `tests/test_engine.py`
- Test: `tests/test_skills.py`

- [ ] **Step 1: Write failing turn-order tests**

Append to `tests/test_engine.py`:

```python
class QueueRng:
    def __init__(self, choices, shuffles=None):
        self.choices = list(choices)
        self.shuffles = list(shuffles or [])

    def choice(self, values):
        value = self.choices.pop(0)
        assert value in values
        return value

    def shuffle(self, values):
        if self.shuffles:
            ordered = self.shuffles.pop(0)
            values[:] = ordered

    def random(self):
        return 0.99


def test_round_order_uses_high_first_order_rolls_and_shuffles_ties():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="a", name="A"),
            Dango(id="b", name="B"),
            Dango(id="c", name="C"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=QueueRng([3, 1, 3], shuffles=[["c", "a"]]))

    order_rolls = engine.roll_order_values(["a", "b", "c"], round_number=1)
    order = engine.order_actors(order_rolls)

    assert order_rolls == {"a": 3, "b": 1, "c": 3}
    assert order == ["c", "a", "b"]


def test_round_order_can_use_low_first_order_rolls():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
        include_bu_king=False,
        order_direction="low_first",
    )
    engine = RaceEngine(config, rng=QueueRng([3, 1]))

    order = engine.order_actors(engine.roll_order_values(["a", "b"], round_number=1))

    assert order == ["b", "a"]
```

- [ ] **Step 2: Write failing dice-skill timing tests**

Append to `tests/test_skills.py`:

```python
def test_mornye_rolls_once_for_order_and_once_for_movement():
    skill = MornyeSkill()
    config = RaceConfig(
        board=Board(finish=20),
        participants=[Dango(id="m", name="Mornye", skill=skill)],
        include_bu_king=False,
    )
    engine = RaceEngine(config)

    assert engine.roll_for_order("m") == 3
    assert engine.roll_for_movement("m") == 2


def test_chisa_uses_base_movement_roll_pool_before_modifiers():
    skill = ChisaSkill()
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="chisa", name="Chisa", skill=skill),
            Dango(id="other", name="Other"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config)
    context = TurnContext(
        round_rolls={"chisa": 1, "other": 1},
        base_roll=1,
        movement=1,
    )

    assert skill.modify_roll(
        engine.dangos["chisa"],
        1,
        engine.state,
        context,
        engine.rng,
    ) == 3
    assert context.round_rolls == {"chisa": 1, "other": 1}
```

- [ ] **Step 3: Run focused tests to verify they fail**

Run:

```bash
uv run pytest tests/test_engine.py::test_round_order_uses_high_first_order_rolls_and_shuffles_ties tests/test_engine.py::test_round_order_can_use_low_first_order_rolls tests/test_skills.py::test_mornye_rolls_once_for_order_and_once_for_movement tests/test_skills.py::test_chisa_uses_base_movement_roll_pool_before_modifiers -q
```

Expected: FAIL because the new roll/order methods do not exist.

- [ ] **Step 4: Implement roll phase helpers**

In `src/dango_sim/engine.py`, replace `build_round_order()` and add helpers:

```python
    def actors_for_round(self, round_number: int) -> list[str]:
        actors = self.normal_ids()
        if self.config.include_bu_king and round_number >= 3:
            actors.append(BU_KING_ID)
        return actors

    def build_round_order(self, round_number: int) -> list[str]:
        return self.order_actors(
            self.roll_order_values(
                self.actors_for_round(round_number),
                round_number=round_number,
            )
        )

    def roll_order_values(
        self,
        actors: Iterable[str],
        *,
        round_number: int,
    ) -> dict[str, int]:
        return {
            actor_id: self.roll_bu_king_order()
            if actor_id == BU_KING_ID
            else self.roll_for_order(actor_id)
            for actor_id in actors
        }

    def order_actors(self, order_rolls: dict[str, int]) -> list[str]:
        reverse = self.config.order_direction == "high_first"
        ordered: list[str] = []
        for roll in sorted(set(order_rolls.values()), reverse=reverse):
            group = [
                actor_id
                for actor_id, value in order_rolls.items()
                if value == roll
            ]
            self.rng.shuffle(group)
            ordered.extend(group)
        return ordered

    def roll_bu_king_order(self) -> int:
        faces = [1, 2, 3] if self.config.bu_king_order_faces == "d3" else [1, 2, 3, 4, 5, 6]
        return int(self.rng.choice(faces))

    def roll_for_order(self, dango_id: str) -> int:
        return self.roll_with_dice_skill(dango_id)

    def roll_for_movement(self, dango_id: str) -> int:
        return self.roll_with_dice_skill(dango_id)

    def roll_with_dice_skill(self, dango_id: str) -> int:
        dango = self.dangos[dango_id]
        faces = [1, 2, 3]
        if dango.skill and hasattr(dango.skill, "roll_faces"):
            faces = list(dango.skill.roll_faces(dango, self.state))
        if dango.skill and hasattr(dango.skill, "roll"):
            return int(dango.skill.roll(dango, self.state, self.rng))
        return int(self.rng.choice(faces))
```

Replace `roll_for()` with:

```python
    def roll_for(self, dango_id: str) -> int:
        return self.roll_for_movement(dango_id)
```

Update `run()` so movement rolls are pre-rolled before any actor acts:

```python
            actors = self.actors_for_round(round_number)
            order_rolls = self.roll_order_values(actors, round_number=round_number)
            order = self.order_actors(order_rolls)
            round_rolls = self.roll_round_values(actors)
```

Update `roll_round_values()`:

```python
    def roll_round_values(self, actors: Iterable[str]) -> dict[str, int]:
        rolls: dict[str, int] = {}
        for actor_id in actors:
            if actor_id == BU_KING_ID:
                rolls[actor_id] = int(self.rng.choice([1, 2, 3, 4, 5, 6]))
            else:
                rolls[actor_id] = self.roll_for_movement(actor_id)
        return rolls
```

Update the Bu King call in `run()`:

```python
                if dango_id == BU_KING_ID:
                    self.take_bu_king_turn(base_roll=round_rolls[dango_id])
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
uv run pytest tests/test_engine.py::test_round_order_uses_high_first_order_rolls_and_shuffles_ties tests/test_engine.py::test_round_order_can_use_low_first_order_rolls tests/test_skills.py::test_mornye_rolls_once_for_order_and_once_for_movement tests/test_skills.py::test_chisa_uses_base_movement_roll_pool_before_modifiers -q
```

Expected: PASS.

- [ ] **Step 6: Run engine and skill tests**

Run:

```bash
uv run pytest tests/test_engine.py tests/test_skills.py -q
```

Expected: Some old turn-order tests may fail because they assume pure shuffle. Update only those expectations to match order-roll behavior.

- [ ] **Step 7: Commit**

```bash
git add src/dango_sim/engine.py src/dango_sim/skills.py tests/test_engine.py tests/test_skills.py
git commit -m "feat: use dice based turn order"
```

---

### Task 5: Implement Entry-On-First-Action And Starting-State Initialization

**Files:**
- Modify: `src/dango_sim/engine.py`
- Test: `tests/test_engine.py`
- Test: `tests/test_skills.py`

- [ ] **Step 1: Write failing entry tests**

Append to `tests/test_engine.py`:

```python
def test_without_starting_state_dangos_are_not_on_board_until_first_action():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
        include_bu_king=False,
    )
    engine = RaceEngine(config)

    assert engine.state.positions == {}
    assert not engine.state.is_entered("a")

    engine.take_turn("a", base_roll=2, round_rolls={"a": 2, "b": 1})

    assert engine.state.positions == {2: ["a"]}
    assert not engine.state.is_entered("b")


def test_with_starting_state_preserves_initial_stacks_and_laps():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
        include_bu_king=False,
        starting_state=RaceStartingState(
            positions={4: ["a", "b"]},
            laps_completed={"a": 1, "b": 0},
        ),
    )

    engine = RaceEngine(config)

    assert engine.state.positions == {4: ["a", "b"]}
    assert engine.state.laps_completed == {"a": 1, "b": 0}
```

Update imports in `tests/test_engine.py`:

```python
from dango_sim.models import BU_KING_ID, Board, Dango, RaceConfig, RaceStartingState, RaceState
```

- [ ] **Step 2: Write failing unentered-target test**

Append to `tests/test_skills.py`:

```python
def test_aemeath_ignores_unentered_dango_targets():
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

    engine.take_turn("aemeath", base_roll=6, round_rolls={"aemeath": 6, "target": 1})

    assert skill.waiting
    assert engine.state.positions == {6: ["aemeath"]}
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_engine.py::test_without_starting_state_dangos_are_not_on_board_until_first_action tests/test_engine.py::test_with_starting_state_preserves_initial_stacks_and_laps tests/test_skills.py::test_aemeath_ignores_unentered_dango_targets -q
```

Expected: FAIL because the engine still starts every normal dango at `0`.

- [ ] **Step 4: Update engine initialization and take_turn entry**

In `RaceEngine.__init__`, replace state initialization with:

```python
        if self.config.starting_state is None:
            self.state = RaceState.empty(self.normal_ids())
        else:
            self.state = RaceState.from_starting_state(self.config.starting_state)
```

Update Bu King injection:

```python
        if self.config.include_bu_king:
            self.dangos[BU_KING_ID] = Dango(
                id=BU_KING_ID,
                name="Bu King",
                is_special=True,
            )
            if not self.state.is_entered(BU_KING_ID):
                self.state.place_group([BU_KING_ID], 0, bottom=True)
```

At the start of `take_turn()` after skill setup and before reading `source`, add:

```python
        if not self.state.is_entered(dango_id):
            self.state.enter_at_start(dango_id)
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
uv run pytest tests/test_engine.py::test_without_starting_state_dangos_are_not_on_board_until_first_action tests/test_engine.py::test_with_starting_state_preserves_initial_stacks_and_laps tests/test_skills.py::test_aemeath_ignores_unentered_dango_targets -q
```

Expected: PASS.

- [ ] **Step 6: Run affected tests**

Run:

```bash
uv run pytest tests/test_engine.py tests/test_skills.py -q
```

Expected: Update tests that assumed initial normal stacks at `0` by setting `engine.state = RaceState.initial([...])` explicitly when the test is about stack mechanics rather than default opening behavior.

- [ ] **Step 7: Commit**

```bash
git add src/dango_sim/engine.py tests/test_engine.py tests/test_skills.py
git commit -m "feat: enter dango on first action"
```

---

### Task 6: Implement Lap Counting And Half Win Thresholds

**Files:**
- Modify: `src/dango_sim/engine.py`
- Test: `tests/test_engine.py`

- [ ] **Step 1: Write failing lap threshold tests**

Append to `tests/test_engine.py`:

```python
def test_first_half_finish_increments_lap_and_places_group_at_zero():
    config = RaceConfig(
        board=Board(finish=5),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
        include_bu_king=False,
    )
    engine = RaceEngine(config)
    engine.state = RaceState(positions={4: ["a"], 2: ["b"]}, laps_completed={"a": 0, "b": 0})

    engine.take_turn("a", base_roll=1, round_rolls={"a": 1, "b": 1})

    assert engine.has_finished()
    assert engine.state.positions[0] == ["a"]
    assert engine.state.laps_completed["a"] == 1


def test_second_half_dango_with_one_lap_needs_one_more_finish():
    config = RaceConfig(
        board=Board(finish=5),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
        include_bu_king=False,
        starting_state=RaceStartingState(
            positions={4: ["a"], 2: ["b"]},
            laps_completed={"a": 1, "b": 0},
        ),
    )
    engine = RaceEngine(config)

    engine.take_turn("a", base_roll=1, round_rolls={"a": 1, "b": 1})

    assert engine.has_finished()
    assert engine.state.laps_completed["a"] == 2


def test_second_half_dango_with_zero_laps_needs_two_finishes():
    config = RaceConfig(
        board=Board(finish=5),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
        include_bu_king=False,
        starting_state=RaceStartingState(
            positions={4: ["a"], 2: ["b"]},
            laps_completed={"a": 0, "b": 1},
        ),
    )
    engine = RaceEngine(config)

    engine.take_turn("a", base_roll=1, round_rolls={"a": 1, "b": 1})

    assert not engine.has_finished()
    assert engine.state.laps_completed["a"] == 1
    assert engine.state.positions[0] == ["a"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_engine.py::test_first_half_finish_increments_lap_and_places_group_at_zero tests/test_engine.py::test_second_half_dango_with_one_lap_needs_one_more_finish tests/test_engine.py::test_second_half_dango_with_zero_laps_needs_two_finishes -q
```

Expected: FAIL because crossing always finishes immediately and does not count laps.

- [ ] **Step 3: Add finish helpers**

In `src/dango_sim/engine.py`, add:

```python
    def win_lap_threshold(self) -> int:
        return 2 if self.config.starting_state is not None else 1

    def finish_group_at_start(self, group: list[str]) -> None:
        normal_ids = set(self.normal_ids())
        self.state.remove_ids(group)
        self.state.place_group(group, 0)
        for dango_id in group:
            if dango_id in normal_ids:
                self.state.laps_completed[dango_id] = (
                    self.state.laps_completed.get(dango_id, 0) + 1
                )

        threshold = self.win_lap_threshold()
        if any(
            dango_id in normal_ids
            and self.state.laps_completed.get(dango_id, 0) >= threshold
            for dango_id in group
        ):
            self.state.finished_group = [
                dango_id for dango_id in reversed(group) if dango_id in normal_ids
            ]
            self.state.finished_position = 0
```

Replace finish handling in `take_turn()`:

```python
        if self.path_passes_start(path):
            self.finish_group_at_start(group)
            self.after_any_move(group, path, dango_id)
            return
```

Replace finish handling in `apply_tile_movement()`:

```python
        if self.path_passes_start(path):
            self.finish_group_at_start(group)
            return 0
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
uv run pytest tests/test_engine.py::test_first_half_finish_increments_lap_and_places_group_at_zero tests/test_engine.py::test_second_half_dango_with_one_lap_needs_one_more_finish tests/test_engine.py::test_second_half_dango_with_zero_laps_needs_two_finishes -q
```

Expected: PASS.

- [ ] **Step 5: Run engine tests**

Run:

```bash
uv run pytest tests/test_engine.py -q
```

Expected: PASS after updating expectations for lap-counted non-winning second-half crossings.

- [ ] **Step 6: Commit**

```bash
git add src/dango_sim/engine.py tests/test_engine.py
git commit -m "feat: count half laps for finish"
```

---

### Task 7: Align Bu King Roll Gating And Chisa Pool

**Files:**
- Modify: `src/dango_sim/engine.py`
- Modify: `src/dango_sim/skills.py`
- Test: `tests/test_engine.py`
- Test: `tests/test_skills.py`

- [ ] **Step 1: Write failing Bu King gating tests**

Append to `tests/test_engine.py`:

```python
def test_bu_king_in_starting_state_does_not_roll_before_round_three():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="a", name="A")],
        starting_state=RaceStartingState(
            positions={5: [BU_KING_ID], 2: ["a"]},
            laps_completed={"a": 1},
        ),
    )
    engine = RaceEngine(config, rng=QueueRng([3, 2]))

    actors = engine.actors_for_round(1)
    order_rolls = engine.roll_order_values(actors, round_number=1)
    move_rolls = engine.roll_round_values(actors)

    assert actors == ["a"]
    assert order_rolls == {"a": 3}
    assert move_rolls == {"a": 2}
    assert engine.state.position_of(BU_KING_ID) == 5


def test_bu_king_uses_configurable_order_faces_and_fixed_movement_faces_from_round_three():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="a", name="A")],
        bu_king_order_faces="d6",
    )
    engine = RaceEngine(config, rng=QueueRng([2, 6, 1, 5]))

    actors = engine.actors_for_round(3)
    order_rolls = engine.roll_order_values(actors, round_number=3)
    move_rolls = engine.roll_round_values(actors)

    assert actors == ["a", BU_KING_ID]
    assert order_rolls[BU_KING_ID] == 6
    assert move_rolls[BU_KING_ID] == 5
```

- [ ] **Step 2: Write failing Chisa pool test**

Append to `tests/test_skills.py`:

```python
def test_chisa_minimum_check_includes_bu_king_once_bu_king_can_act():
    skill = ChisaSkill()
    config = RaceConfig(
        board=Board(finish=20),
        participants=[Dango(id="chisa", name="Chisa", skill=skill)],
    )
    engine = RaceEngine(config)
    context = TurnContext(
        round_rolls={"chisa": 2, BU_KING_ID: 1},
        base_roll=2,
        movement=2,
    )

    assert skill.modify_roll(
        engine.dangos["chisa"],
        2,
        engine.state,
        context,
        engine.rng,
    ) == 2
```

Update imports in `tests/test_skills.py`:

```python
from dango_sim.models import BU_KING_ID, Board, Dango, RaceConfig, RaceState
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_engine.py::test_bu_king_in_starting_state_does_not_roll_before_round_three tests/test_engine.py::test_bu_king_uses_configurable_order_faces_and_fixed_movement_faces_from_round_three tests/test_skills.py::test_chisa_minimum_check_includes_bu_king_once_bu_king_can_act -q
```

Expected: FAIL until Bu King is fully routed through the pre-roll phases and Chisa uses the full pool.

- [ ] **Step 4: Confirm Chisa implementation**

In `src/dango_sim/skills.py`, ensure `ChisaSkill.modify_roll()` remains:

```python
@dataclass
class ChisaSkill:
    bonus: int = 2

    def modify_roll(self, dango: Dango, roll: int, state: RaceState, context, rng) -> int:
        return roll + self.bonus if roll == min(context.round_rolls.values()) else roll
```

This intentionally includes Bu King when the engine includes `BU_KING_ID` in `round_rolls`, and excludes Bu King before round 3 because the engine does not roll it then.

- [ ] **Step 5: Run focused tests**

Run:

```bash
uv run pytest tests/test_engine.py::test_bu_king_in_starting_state_does_not_roll_before_round_three tests/test_engine.py::test_bu_king_uses_configurable_order_faces_and_fixed_movement_faces_from_round_three tests/test_skills.py::test_chisa_minimum_check_includes_bu_king_once_bu_king_can_act -q
```

Expected: PASS.

- [ ] **Step 6: Run engine and skill tests**

Run:

```bash
uv run pytest tests/test_engine.py tests/test_skills.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/dango_sim/engine.py src/dango_sim/skills.py tests/test_engine.py tests/test_skills.py
git commit -m "feat: gate bu king roll phases"
```

---

### Task 8: Add Top-N Simulation Statistics

**Files:**
- Modify: `src/dango_sim/simulation.py`
- Test: `tests/test_simulation.py`

- [ ] **Step 1: Write failing top-N tests**

Append to `tests/test_simulation.py`:

```python
def test_run_simulations_reports_top_n_rates():
    StubEngine.results = [
        RaceResult(winner_id="a", rankings=["a", "b", "c"], rounds=1),
        RaceResult(winner_id="b", rankings=["b", "c", "a"], rounds=1),
        RaceResult(winner_id="c", rankings=["c", "a", "b"], rounds=1),
    ]

    summary = run_simulations(
        config_factory=lambda: RaceConfig(
            board=Board(finish=10),
            participants=[
                Dango(id="a", name="A"),
                Dango(id="b", name="B"),
                Dango(id="c", name="C"),
            ],
            include_bu_king=False,
        ),
        runs=3,
        top_n=[1, 2],
        engine_cls=StubEngine,
    )

    assert dict(summary.top_n_rates[1]) == {"a": 1 / 3, "b": 1 / 3, "c": 1 / 3}
    assert dict(summary.top_n_rates[2]) == {"a": 2 / 3, "b": 2 / 3, "c": 2 / 3}
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_simulation.py::test_run_simulations_reports_top_n_rates -q
```

Expected: FAIL because `top_n` and `top_n_rates` do not exist.

- [ ] **Step 3: Implement top-N aggregation**

Update `SimulationSummary` in `src/dango_sim/simulation.py`:

```python
@dataclass(frozen=True)
class SimulationSummary:
    runs: int
    wins: Mapping[str, int]
    win_rates: Mapping[str, float]
    average_rank: Mapping[str, float]
    average_rounds: float
    top_n_rates: Mapping[int, Mapping[str, float]] = field(default_factory=dict)
```

Add `field` to imports:

```python
from dataclasses import dataclass, field
```

In `__post_init__`, add:

```python
        object.__setattr__(
            self,
            "top_n_rates",
            MappingProxyType(
                {
                    int(n): MappingProxyType(dict(rates))
                    for n, rates in self.top_n_rates.items()
                }
            ),
        )
```

Update `run_simulations()` signature:

```python
def run_simulations(
    *,
    config_factory: Callable[[], RaceConfig],
    runs: int,
    seed: int | None = None,
    engine_cls=RaceEngine,
    top_n: Iterable[int] = (),
) -> SimulationSummary:
```

Add `Iterable` import:

```python
from typing import Callable, Iterable, Mapping
```

Before the loop:

```python
    top_n_values = sorted({int(value) for value in top_n})
    if any(value <= 0 for value in top_n_values):
        raise ValueError("top_n values must be positive")
    top_n_counts: dict[int, dict[str, int]] = {
        value: {} for value in top_n_values
    }
```

Inside the result loop after rankings are processed:

```python
        for n in top_n_values:
            for dango_id in result.rankings[:n]:
                top_n_counts[n][dango_id] = top_n_counts[n].get(dango_id, 0) + 1
            for dango_id in result.rankings:
                top_n_counts[n].setdefault(dango_id, 0)
```

Before return:

```python
    top_n_rates = {
        n: {
            dango_id: count / runs
            for dango_id, count in counts.items()
        }
        for n, counts in top_n_counts.items()
    }
```

Add to returned `SimulationSummary`:

```python
        top_n_rates=top_n_rates,
```

- [ ] **Step 4: Run simulation tests**

Run:

```bash
uv run pytest tests/test_simulation.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dango_sim/simulation.py tests/test_simulation.py
git commit -m "feat: report top n simulation rates"
```

---

### Task 9: Add CLI Options And Documentation

**Files:**
- Modify: `main.py`
- Modify: `README.md`
- Modify: `src/dango_sim/AGENTS.md`
- Test: use CLI smoke command

- [ ] **Step 1: Update CLI imports and arguments**

In `main.py`, add:

```python
from dango_sim.state_io import load_starting_state
```

Change `build_sample_config()` to accept a starting state:

```python
def build_sample_config(starting_state=None) -> RaceConfig:
```

Pass it to `RaceConfig`:

```python
        starting_state=starting_state,
```

Add parser args:

```python
    parser.add_argument(
        "--starting-state",
        type=Path,
        default=None,
        help="JSON starting state for second-half simulations",
    )
    parser.add_argument(
        "--top-n",
        type=positive_int,
        nargs="*",
        default=[],
        help="also report probability of each dango finishing in each top-N bucket",
    )
```

Load the state and pass top-N:

```python
    starting_state = (
        load_starting_state(args.starting_state)
        if args.starting_state is not None
        else None
    )
    summary = run_simulations(
        config_factory=lambda: build_sample_config(starting_state),
        runs=args.runs,
        seed=args.seed,
        top_n=args.top_n,
    )
```

After the existing ranking output, print top-N:

```python
    for n, rates in sorted(summary.top_n_rates.items()):
        print(f"Top {n} rates:")
        for dango_id, rate in sorted(rates.items(), key=lambda item: (-item[1], item[0])):
            print(f"  {dango_id}: {rate * 100:.2f}%")
```

- [ ] **Step 2: Update README**

Add this section to `README.md`:

````markdown
## Starting states

Second-half simulations can start from an editable JSON file:

```json
{
  "positions": {
    "0": ["carlotta"],
    "7": ["bu_king", "chisa"]
  },
  "laps_completed": {
    "carlotta": 1,
    "chisa": 0
  }
}
```

Stacks are listed from bottom to top. If Bu King is present in the file, its
position is preserved, but it still does not roll or act until round 3 of the
current half.

Run a second-half simulation with top-N probabilities:

```bash
uv run python main.py --runs 1000 --seed 42 --starting-state second-half.json --top-n 3 4
```
````

- [ ] **Step 3: Update source AGENTS notes**

In `src/dango_sim/AGENTS.md`, add under architecture or common patterns:

```markdown
- Turn order is dice-based: order rolls are pre-rolled, grouped by value, sorted
  by `RaceConfig.order_direction`, and shuffled only within equal-value groups.
- Starting states are editable JSON via `state_io.py`; no-start races begin with
  normal dango unentered until their first action.
- Bu King may be loaded from a starting state but does not roll or act before
  round 3 of the current half.
```

- [ ] **Step 4: Run CLI smoke tests**

Run:

```bash
uv run python main.py --runs 5 --seed 42 --top-n 3 4
```

Expected: exit 0 and output `Top 3 rates:` and `Top 4 rates:`.

- [ ] **Step 5: Commit**

```bash
git add main.py README.md src/dango_sim/AGENTS.md
git commit -m "docs: document half state simulation"
```

---

### Task 10: Final Verification

**Files:**
- No planned source edits unless verification finds an issue.

- [ ] **Step 1: Run full test suite**

Run:

```bash
uv run pytest
```

Expected: PASS.

- [ ] **Step 2: Run sample simulation**

Run:

```bash
uv run python main.py --runs 20 --seed 42 --top-n 3 4
```

Expected: command exits 0 and prints win rates, average ranks, and top-N rates.

- [ ] **Step 3: Run starting-state CLI smoke test**

Create a temporary state file manually or with PowerShell:

```powershell
$json = @'
{
  "positions": {
    "0": ["carlotta"],
    "4": ["chisa"],
    "8": ["lynae"],
    "12": ["mornye"],
    "16": ["aemeath"],
    "20": ["shorekeeper"]
  },
  "laps_completed": {
    "carlotta": 1,
    "chisa": 0,
    "lynae": 0,
    "mornye": 1,
    "aemeath": 0,
    "shorekeeper": 1
  }
}
'@
Set-Content -Path .\second-half-smoke.json -Value $json -Encoding UTF8
uv run python main.py --runs 5 --seed 42 --starting-state .\second-half-smoke.json --top-n 3
Remove-Item .\second-half-smoke.json
```

Expected: command exits 0 and prints `Top 3 rates:`.

- [ ] **Step 4: Inspect git status**

Run:

```bash
git status --short
```

Expected: only unrelated intentionally untracked `.omc/` and `example/` remain.

- [ ] **Step 5: Commit final fixes if needed**

Only if a verification command required a code or docs fix:

```bash
git add <changed-files>
git commit -m "fix: complete two-half race rules"
```

---

## Self-Review

- Spec coverage: The tasks cover configurable action order, equal-roll shuffle groups, two pre-roll phases, dice-skill timing, movement modifier timing, Chisa including Bu King from round 3, unentered dango, JSON starting state, second-half lap thresholds, Bu King loaded from state, top-N statistics, CLI flags, and docs.
- Red-flag scan: No marker text or open-ended implementation steps are intentionally present.
- Type consistency: The plan consistently uses `RaceStartingState`, `RaceConfig.order_direction`, `RaceConfig.bu_king_order_faces`, `RaceConfig.starting_state`, `RaceState.laps_completed`, `roll_order_values`, `order_actors`, `roll_for_order`, `roll_for_movement`, and `top_n_rates`.
