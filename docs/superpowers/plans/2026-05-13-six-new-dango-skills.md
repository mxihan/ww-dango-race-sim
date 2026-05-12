# Six New Dango Skills Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Augusta, Iuno, Phrolova, Changli, Jinhsi, and Calcharo as built-in skills with deterministic tests and minimal engine hook extensions.

**Architecture:** Keep the existing hook style in `skills.py`. Add round-start and next-round forced-last state to `RaceEngine`, plus one ranking helper that includes Bu King for Iuno only. Movement bonuses and stack changes stay inside skill classes through existing `before_move`, `after_move`, and `after_any_move` hooks.

**Tech Stack:** Python 3.12, dataclasses, pytest, `uv run`.

---

## File Structure

- Modify `src/dango_sim/engine.py`: add forced-last state, round-start hook dispatch, turn-start hook dispatch, skip handling, Iuno ranking helper, and a `force_last_next_round()` helper.
- Modify `src/dango_sim/skills.py`: add six skill dataclasses and small stack-position helpers local to the module.
- Modify `tests/test_skills.py`: add tests for each new skill and engine order effects.
- Modify `main.py`: import and include the six new dangos in `build_sample_config()`.
- Optionally modify `src/dango_sim/__init__.py` only if skill exports are added there during implementation; current public API does not export existing skills, so no change is expected.

## Task 1: Engine Round-Start, Turn-Start, and Forced-Last Hooks

**Files:**
- Modify: `src/dango_sim/engine.py`
- Test: `tests/test_skills.py`

- [ ] **Step 1: Write failing tests for Augusta order behavior**

Append these tests to `tests/test_skills.py` and add `AugustaSkill` to the existing `from dango_sim.skills import (...)` block:

```python
def test_augusta_skips_current_round_when_round_starts_on_top():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="base", name="Base"),
            Dango(id="augusta", name="Augusta", skill=AugustaSkill()),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng(choices=[3, 1, 1, 1]))
    engine.state = RaceState(positions={2: ["base", "augusta"]})
    engine.state.round_number = 1
    engine.start_round(1)

    order = engine.build_round_order(1)
    round_rolls = {"base": 1, "augusta": 3}
    for dango_id in order:
        engine.take_turn(dango_id, base_roll=round_rolls[dango_id], round_rolls=round_rolls)

    assert engine.state.stack_at(2) == ["base", "augusta"]
    assert engine.force_last_next_round_ids == {"augusta"}


def test_augusta_forced_last_marker_moves_it_to_next_round_end():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="base", name="Base"),
            Dango(id="augusta", name="Augusta", skill=AugustaSkill()),
            Dango(id="other", name="Other"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng(choices=[3, 1, 2, 1, 3, 2]))
    engine.force_last_next_round_ids.add("augusta")
    engine.start_round(2)

    assert engine.build_round_order(2)[-1] == "augusta"
    assert engine.force_last_next_round_ids == set()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
uv run pytest tests/test_skills.py::test_augusta_skips_current_round_when_round_starts_on_top tests/test_skills.py::test_augusta_forced_last_marker_moves_it_to_next_round_end -q
```

Expected: FAIL because `AugustaSkill` and engine forced-last state do not exist.

- [ ] **Step 3: Implement minimal engine support**

In `RaceEngine.__init__`, add:

```python
self.skip_turns_this_round: set[str] = set()
self.force_last_next_round_ids: set[str] = set()
self.force_last_this_round_ids: set[str] = set()
```

Add methods to `RaceEngine`:

```python
def start_round(self, round_number: int) -> None:
    self.force_last_this_round_ids = set(self.force_last_next_round_ids)
    self.force_last_next_round_ids.clear()
    self.skip_turns_this_round.clear()
    for dango in self.participants:
        if dango.skill and hasattr(dango.skill, "on_round_start"):
            dango.skill.on_round_start(dango, self.state, self, self.rng)

def force_last_next_round(self, dango_id: str) -> None:
    if dango_id in self.normal_ids():
        self.force_last_next_round_ids.add(dango_id)

def skip_turn_this_round(self, dango_id: str) -> None:
    if dango_id in self.normal_ids():
        self.skip_turns_this_round.add(dango_id)

def apply_forced_last(self, order: list[str]) -> list[str]:
    forced = [dango_id for dango_id in order if dango_id in self.force_last_this_round_ids]
    normal = [dango_id for dango_id in order if dango_id not in self.force_last_this_round_ids]
    return normal + forced
```

Change `run()` round setup from direct order creation to:

```python
self.state.round_number = round_number
self.start_round(round_number)
actors = self.actors_for_round(round_number)
order = self.build_round_order(round_number)
round_rolls = self.roll_round_values(actors)
```

Change `build_round_order()` to return:

```python
return self.apply_forced_last(
    self.order_actors(
        self.roll_order_values(
            self.actors_for_round(round_number),
            round_number=round_number,
        )
    )
)
```

At the start of the `for dango_id in order` loop in `run()`, before checking Bu King, add:

```python
if dango_id in self.skip_turns_this_round:
    continue
```

In `take_turn()`, after `dango = self.dangos[dango_id]` and before `modify_roll`, add:

```python
if dango.skill and hasattr(dango.skill, "on_turn_start"):
    dango.skill.on_turn_start(dango, self.state, self, self.rng)
```

- [ ] **Step 4: Add minimal AugustaSkill**

In `src/dango_sim/skills.py`, add:

```python
@dataclass
class AugustaSkill:
    def on_round_start(self, dango: Dango, state: RaceState, engine, rng) -> None:
        if not state.is_entered(dango.id):
            return
        position = state.position_of(dango.id)
        stack = state.stack_at(position)
        if stack and stack[-1] == dango.id:
            engine.skip_turn_this_round(dango.id)
            engine.force_last_next_round(dango.id)
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```powershell
uv run pytest tests/test_skills.py::test_augusta_skips_current_round_when_round_starts_on_top tests/test_skills.py::test_augusta_forced_last_marker_moves_it_to_next_round_end -q
```

Expected: PASS.

## Task 2: Stack Position Movement Skills

**Files:**
- Modify: `src/dango_sim/skills.py`
- Test: `tests/test_skills.py`

- [ ] **Step 1: Write failing tests for Phrolova, Jinhsi, Changli, and Calcharo**

Add these names to the import block: `CalcharoSkill`, `ChangliSkill`, `JinhsiSkill`, `PhrolovaSkill`.

Append:

```python
def test_phrolova_gets_bonus_when_at_stack_bottom():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="phrolova", name="Phrolova", skill=PhrolovaSkill()),
            Dango(id="rider", name="Rider"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng())
    engine.state = RaceState(positions={2: ["phrolova", "rider"]})

    engine.take_turn("phrolova", base_roll=1, round_rolls={"phrolova": 1, "rider": 1})

    assert engine.state.stack_at(6) == ["phrolova", "rider"]


def test_phrolova_gets_bonus_when_alone_in_stack():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[Dango(id="phrolova", name="Phrolova", skill=PhrolovaSkill())],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng())
    engine.state = RaceState(positions={2: ["phrolova"]})

    engine.take_turn("phrolova", base_roll=1, round_rolls={"phrolova": 1})

    assert engine.state.stack_at(6) == ["phrolova"]


def test_phrolova_does_not_get_bonus_when_not_at_bottom():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="base", name="Base"),
            Dango(id="phrolova", name="Phrolova", skill=PhrolovaSkill()),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng())
    engine.state = RaceState(positions={2: ["base", "phrolova"]})

    engine.take_turn("phrolova", base_roll=1, round_rolls={"base": 1, "phrolova": 1})

    assert engine.state.stack_at(3) == ["phrolova"]


def test_jinhsi_moves_to_top_at_own_turn_start_when_probability_triggers():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="base", name="Base"),
            Dango(id="jinhsi", name="Jinhsi", skill=JinhsiSkill()),
            Dango(id="rider", name="Rider"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng(randoms=[0.39]))
    engine.state = RaceState(positions={2: ["base", "jinhsi", "rider"]})

    engine.take_turn("jinhsi", base_roll=1, round_rolls={"base": 1, "jinhsi": 1, "rider": 1})

    assert engine.state.stack_at(2) == ["base", "rider"]
    assert engine.state.stack_at(3) == ["jinhsi"]


def test_jinhsi_stays_in_place_when_probability_fails():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="base", name="Base"),
            Dango(id="jinhsi", name="Jinhsi", skill=JinhsiSkill()),
            Dango(id="rider", name="Rider"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng(randoms=[0.40]))
    engine.state = RaceState(positions={2: ["base", "jinhsi", "rider"]})

    engine.take_turn("jinhsi", base_roll=1, round_rolls={"base": 1, "jinhsi": 1, "rider": 1})

    assert engine.state.stack_at(2) == ["base"]
    assert engine.state.stack_at(3) == ["jinhsi", "rider"]


def test_changli_marks_next_round_last_after_moving_with_dango_below():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="destination_base", name="Destination Base"),
            Dango(id="changli", name="Changli", skill=ChangliSkill()),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng(randoms=[0.64]))
    engine.state = RaceState(positions={2: ["changli"], 3: ["destination_base"]})

    engine.take_turn(
        "changli",
        base_roll=1,
        round_rolls={"destination_base": 1, "changli": 1},
    )

    assert engine.force_last_next_round_ids == {"changli"}


def test_changli_does_not_mark_next_round_when_no_dango_below_after_move():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[Dango(id="changli", name="Changli", skill=ChangliSkill())],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng(randoms=[0.10]))
    engine.state = RaceState(positions={2: ["changli"]})

    engine.take_turn("changli", base_roll=1, round_rolls={"changli": 1})

    assert engine.force_last_next_round_ids == set()


def test_calcharo_gets_bonus_when_ranked_last_ignoring_bu_king():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="leader", name="Leader"),
            Dango(id="calcharo", name="Calcharo", skill=CalcharoSkill()),
        ],
    )
    engine = RaceEngine(config, rng=FixedRng())
    engine.state = RaceState(positions={2: ["calcharo"], 10: ["leader"], 19: [BU_KING_ID]})

    engine.take_turn("calcharo", base_roll=1, round_rolls={"leader": 1, "calcharo": 1})

    assert engine.state.stack_at(6) == ["calcharo"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
uv run pytest tests/test_skills.py::test_phrolova_gets_bonus_when_at_stack_bottom tests/test_skills.py::test_phrolova_gets_bonus_when_alone_in_stack tests/test_skills.py::test_jinhsi_moves_to_top_at_own_turn_start_when_probability_triggers tests/test_skills.py::test_changli_marks_next_round_last_after_moving_with_dango_below tests/test_skills.py::test_calcharo_gets_bonus_when_ranked_last_ignoring_bu_king -q
```

Expected: FAIL because the new skill classes do not exist.

- [ ] **Step 3: Implement skill helpers and classes**

In `src/dango_sim/skills.py`, add helper functions near the top:

```python
def _stack_for(dango_id: str, state: RaceState) -> list[str] | None:
    if not state.is_entered(dango_id):
        return None
    return state.stack_at(state.position_of(dango_id))

def _is_bottom(dango_id: str, state: RaceState) -> bool:
    stack = _stack_for(dango_id, state)
    return bool(stack) and stack[0] == dango_id

def _has_above(dango_id: str, state: RaceState) -> bool:
    stack = _stack_for(dango_id, state)
    return bool(stack) and stack.index(dango_id) < len(stack) - 1

def _has_below(dango_id: str, state: RaceState) -> bool:
    stack = _stack_for(dango_id, state)
    return bool(stack) and stack.index(dango_id) > 0
```

Add these dataclasses:

```python
@dataclass(frozen=True)
class PhrolovaSkill:
    bonus: int = 3

    def before_move(self, dango: Dango, state: RaceState, context, rng) -> None:
        if _is_bottom(dango.id, state):
            context.movement += self.bonus


@dataclass
class JinhsiSkill:
    chance: float = 0.40

    def on_turn_start(self, dango: Dango, state: RaceState, engine, rng) -> None:
        if not _has_above(dango.id, state):
            return
        if rng.random() >= self.chance:
            return
        position = state.position_of(dango.id)
        stack = state.positions[position]
        stack.remove(dango.id)
        stack.append(dango.id)


@dataclass
class ChangliSkill:
    chance: float = 0.65

    def after_move(self, dango: Dango, state: RaceState, context, rng, engine) -> None:
        if _has_below(dango.id, state) and rng.random() < self.chance:
            engine.force_last_next_round(dango.id)


@dataclass(frozen=True)
class CalcharoSkill:
    bonus: int = 3

    def before_move(self, dango: Dango, state: RaceState, context, rng) -> None:
        rankings = list(context.engine.rankings()) if hasattr(context, "engine") else None
        if rankings is None:
            return
        if rankings and rankings[-1] == dango.id:
            context.movement += self.bonus
```

Also add `engine` to `TurnContext` in `src/dango_sim/engine.py`:

```python
engine: object | None = None
```

When constructing `TurnContext` in `take_turn()`, pass:

```python
engine=self,
```

- [ ] **Step 4: Run focused tests to verify they pass**

Run:

```powershell
uv run pytest tests/test_skills.py::test_phrolova_gets_bonus_when_at_stack_bottom tests/test_skills.py::test_phrolova_gets_bonus_when_alone_in_stack tests/test_skills.py::test_phrolova_does_not_get_bonus_when_not_at_bottom tests/test_skills.py::test_jinhsi_moves_to_top_at_own_turn_start_when_probability_triggers tests/test_skills.py::test_jinhsi_stays_in_place_when_probability_fails tests/test_skills.py::test_changli_marks_next_round_last_after_moving_with_dango_below tests/test_skills.py::test_changli_does_not_mark_next_round_when_no_dango_below_after_move tests/test_skills.py::test_calcharo_gets_bonus_when_ranked_last_ignoring_bu_king -q
```

Expected: PASS.

## Task 3: Iuno Teleport Skill and Bu-King-Aware Ranking

**Files:**
- Modify: `src/dango_sim/engine.py`
- Modify: `src/dango_sim/skills.py`
- Test: `tests/test_skills.py`

- [ ] **Step 1: Write failing Iuno tests**

Add `IunoSkill` to the import block and append:

```python
def test_iuno_teleports_direct_rank_neighbors_to_own_tile_after_midpoint():
    config = RaceConfig(
        board=Board(finish=12),
        participants=[
            Dango(id="leader", name="Leader"),
            Dango(id="iuno", name="Iuno", skill=IunoSkill()),
            Dango(id="trailer", name="Trailer"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng())
    engine.state = RaceState(positions={8: ["leader"], 5: ["iuno"], 2: ["trailer"]})

    engine.take_turn("iuno", base_roll=1, round_rolls={"leader": 1, "iuno": 1, "trailer": 1})

    assert engine.dangos["iuno"].skill.used is True
    assert engine.state.stack_at(6) == ["iuno", "leader", "trailer"]


def test_iuno_direct_bu_king_neighbor_blocks_selection_on_that_side():
    config = RaceConfig(
        board=Board(finish=12),
        participants=[
            Dango(id="leader", name="Leader"),
            Dango(id="iuno", name="Iuno", skill=IunoSkill()),
            Dango(id="trailer", name="Trailer"),
        ],
    )
    engine = RaceEngine(config, rng=FixedRng())
    engine.state = RaceState(positions={9: ["leader"], 8: [BU_KING_ID], 5: ["iuno"], 2: ["trailer"]})

    engine.take_turn("iuno", base_roll=1, round_rolls={"leader": 1, "iuno": 1, "trailer": 1})

    assert engine.dangos["iuno"].skill.used is True
    assert engine.state.stack_at(8) == [BU_KING_ID]
    assert engine.state.stack_at(9) == ["leader"]
    assert engine.state.stack_at(6) == ["iuno", "trailer"]


def test_iuno_triggers_when_carried_through_midpoint():
    config = RaceConfig(
        board=Board(finish=12),
        participants=[
            Dango(id="carrier", name="Carrier"),
            Dango(id="iuno", name="Iuno", skill=IunoSkill()),
            Dango(id="target", name="Target"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng())
    engine.state = RaceState(positions={5: ["carrier", "iuno"], 9: ["target"]})

    engine.take_turn("carrier", base_roll=1, round_rolls={"carrier": 1, "iuno": 1, "target": 1})

    assert engine.dangos["iuno"].skill.used is True
    assert engine.state.stack_at(6) == ["carrier", "iuno", "target"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
uv run pytest tests/test_skills.py::test_iuno_teleports_direct_rank_neighbors_to_own_tile_after_midpoint tests/test_skills.py::test_iuno_direct_bu_king_neighbor_blocks_selection_on_that_side tests/test_skills.py::test_iuno_triggers_when_carried_through_midpoint -q
```

Expected: FAIL because `IunoSkill` and `rankings_with_specials()` do not exist.

- [ ] **Step 3: Add Bu-King-aware ranking helper**

In `RaceEngine`, add:

```python
def rankings_with_specials(self) -> list[str]:
    normal_ids = set(self.normal_ids())
    eligible_ids = set(normal_ids)
    if self.config.include_bu_king and self.state.is_entered(BU_KING_ID):
        eligible_ids.add(BU_KING_ID)

    ordered: list[str] = []
    if self.state.finished_group is not None:
        ordered.extend(
            dango_id
            for dango_id in self.state.finished_group
            if dango_id in normal_ids
        )

    remaining_positions = sorted(
        list(self.state.positions),
        key=lambda position: self.forward_distance_to_start(position),
    )
    for position in remaining_positions:
        ordered.extend(
            dango_id
            for dango_id in reversed(self.state.stack_at(position))
            if dango_id in eligible_ids and dango_id not in ordered
        )

    ordered.extend(
        dango_id
        for dango_id in normal_ids
        if dango_id not in ordered
    )
    return ordered
```

- [ ] **Step 4: Implement IunoSkill**

In `src/dango_sim/skills.py`, add:

```python
@dataclass
class IunoSkill:
    used: bool = False
    midpoint: int | None = None

    def after_move(self, dango: Dango, state: RaceState, context, rng, engine) -> None:
        self._handle_path(dango, state, context, engine)

    def after_any_move(self, dango: Dango, state: RaceState, context, rng, engine) -> None:
        self._handle_path(dango, state, context, engine)

    def _handle_path(self, dango: Dango, state: RaceState, context, engine) -> None:
        if self.used or dango.id not in getattr(context, "group", []):
            return
        midpoint = self.midpoint if self.midpoint is not None else engine.config.board.finish // 2
        if midpoint not in getattr(context, "path", []):
            return
        self._teleport_neighbors(dango, state, engine)

    def _teleport_neighbors(self, dango: Dango, state: RaceState, engine) -> None:
        rankings = engine.rankings_with_specials()
        if dango.id not in rankings:
            return
        index = rankings.index(dango.id)
        candidates = []
        if index > 0:
            candidates.append(rankings[index - 1])
        if index < len(rankings) - 1:
            candidates.append(rankings[index + 1])
        selected = [
            candidate
            for candidate in candidates
            if candidate != BU_KING_ID and candidate in engine.normal_ids()
        ]
        if not selected:
            self.used = True
            return
        destination = state.position_of(dango.id)
        state.remove_ids(selected)
        state.place_group(selected, destination)
        self.used = True
```

Add `BU_KING_ID` to the import line at the top of `skills.py`:

```python
from dango_sim.models import BU_KING_ID, Dango, RaceState
```

- [ ] **Step 5: Run Iuno tests to verify they pass**

Run:

```powershell
uv run pytest tests/test_skills.py::test_iuno_teleports_direct_rank_neighbors_to_own_tile_after_midpoint tests/test_skills.py::test_iuno_direct_bu_king_neighbor_blocks_selection_on_that_side tests/test_skills.py::test_iuno_triggers_when_carried_through_midpoint -q
```

Expected: PASS.

## Task 4: Sample Config Wiring

**Files:**
- Modify: `main.py`
- Test: `tests/test_simulation.py` or full suite

- [ ] **Step 1: Write failing smoke test for sample config participants**

If there is no existing main smoke test, add this to `tests/test_simulation.py`:

```python
from main import build_sample_config


def test_sample_config_includes_new_dangos():
    config = build_sample_config()

    assert {dango.id for dango in config.participants} >= {
        "augusta",
        "iuno",
        "phrolova",
        "changli",
        "jinhsi",
        "calcharo",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
uv run pytest tests/test_simulation.py::test_sample_config_includes_new_dangos -q
```

Expected: FAIL because the sample config does not include the new dangos.

- [ ] **Step 3: Wire imports and participants in `main.py`**

Extend the skill import block:

```python
    AugustaSkill,
    CalcharoSkill,
    ChangliSkill,
    IunoSkill,
    JinhsiSkill,
    PhrolovaSkill,
```

Append participants in `build_sample_config()`:

```python
Dango(id="augusta", name="奥古斯塔团子", skill=AugustaSkill()),
Dango(id="iuno", name="尤诺团子", skill=IunoSkill()),
Dango(id="phrolova", name="弗洛洛团子", skill=PhrolovaSkill()),
Dango(id="changli", name="长离团子", skill=ChangliSkill()),
Dango(id="jinhsi", name="今汐团子", skill=JinhsiSkill()),
Dango(id="calcharo", name="卡卡罗团子", skill=CalcharoSkill()),
```

- [ ] **Step 4: Run smoke test to verify it passes**

Run:

```powershell
uv run pytest tests/test_simulation.py::test_sample_config_includes_new_dangos -q
```

Expected: PASS.

## Task 5: Full Regression Verification

**Files:**
- No code changes expected unless regressions reveal required fixes.

- [ ] **Step 1: Run all tests**

Run:

```powershell
uv run pytest
```

Expected: all tests pass.

- [ ] **Step 2: Run a sample simulation**

Run:

```powershell
uv run python main.py --runs 10 --seed 1
```

Expected: command exits successfully and prints win-rate summary including the new dango ids.

- [ ] **Step 3: Inspect git diff**

Run:

```powershell
git diff -- src/dango_sim/engine.py src/dango_sim/skills.py main.py tests/test_skills.py tests/test_simulation.py
```

Expected: diff contains only the new hook support, new skills, wiring, and tests described in this plan.

## Self-Review

- Spec coverage: Augusta, Iuno, Phrolova, Changli, Jinhsi, and Calcharo each have test and implementation tasks.
- Hook coverage: round-start, turn-start, after-move forced-last, and Iuno Bu-King-aware ranking are all represented.
- Placeholder scan: no TBD, TODO, or vague "add tests" steps remain.
- Type consistency: skill methods use existing hook signatures except `on_round_start` and `on_turn_start`, which are introduced in Task 1.
