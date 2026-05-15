# Phrolova Round Start Opening Stack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make no-starting-state races build the first-round start stack from the first-round action order, with the first actor on top, and move Phrolova's stack-bottom skill check to round start.

**Architecture:** Keep the existing `RaceEngine` and hook system. Add one engine helper for opening-stack order caching and placement, then let `run()` use that cached first-round order after `start_round()` skip markers are known. Move Phrolova's rule decision into `on_round_start`, while keeping `before_move` as the movement mutation point.

**Tech Stack:** Python 3.12, dataclasses, pytest via `uv run`.

---

## File Structure

- Modify `src/dango_sim/engine.py`
  - Add engine state for whether the no-starting-state opening stack has been applied.
  - Add an opening-order cache so the first-round action order is rolled once and reused.
  - Adjust the `run()` round setup sequence for first-round no-starting-state races.
- Modify `src/dango_sim/skills.py`
  - Change `PhrolovaSkill` so `on_round_start` records a per-round pending bonus.
  - Change `before_move` to consume the pending bonus rather than inspect the current stack.
- Modify `tests/test_engine.py`
  - Add integration coverage for opening stack order, round-start visibility, no duplicate order rolls, and `starting_state` bypass.
- Modify `tests/test_skills.py`
  - Update Phrolova unit tests from `before_move` state checks to round-start decision plus action-time consumption.
- Modify `README.md`
  - Update the no-starting-state opening behavior description.
- Modify `src/dango_sim/AGENTS.md`
  - Update the local architecture note about no-start races.

---

### Task 1: Add Failing Engine Tests For Default Opening Stack

**Files:**
- Modify: `tests/test_engine.py`
- Test: `tests/test_engine.py`

- [ ] **Step 1: Add helper skill and deterministic RNG test support**

In `tests/test_engine.py`, add these helper classes near the existing `RecordingRollsSkill`:

```python
class RecordingRoundStartSkill:
    def __init__(self):
        self.observed_stacks = []

    def on_round_start(self, dango, state, engine, rng):
        self.observed_stacks.append(state.stack_at(0))


class RecordingOrderSkill:
    def __init__(self, value):
        self.value = value
        self.rolls = 0

    def roll(self, dango, state, rng):
        self.rolls += 1
        return self.value
```

- [ ] **Step 2: Add test for opening stack order and round-start visibility**

Append this test to `tests/test_engine.py` near the turn-order tests:

```python
def test_no_starting_state_opening_stack_uses_first_round_order_before_round_start():
    probe = RecordingRoundStartSkill()
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="first", name="First", skill=RecordingOrderSkill(3)),
            Dango(id="middle", name="Middle", skill=RecordingOrderSkill(2)),
            Dango(id="last", name="Last", skill=probe),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng([1, 1, 1]))

    engine.state.round_number = 1
    order = engine.prepare_round(1)

    assert order == ["first", "middle", "last"]
    assert engine.state.stack_at(0) == ["last", "middle", "first"]
    assert probe.observed_stacks == [["last", "middle", "first"]]
```

This uses `order_direction="high_first"` by default. `first` rolls 3 and must act first, so it must be at the top of the bottom-to-top stack.

- [ ] **Step 3: Add test that first-round order rolls are not duplicated**

Append:

```python
def test_opening_stack_reuses_first_round_order_rolls_for_actual_turn_order():
    first_skill = RecordingOrderSkill(3)
    second_skill = RecordingOrderSkill(1)
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="first", name="First", skill=first_skill),
            Dango(id="second", name="Second", skill=second_skill),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng([1, 1]))

    engine.state.round_number = 1
    order = engine.prepare_round(1)

    assert order == ["first", "second"]
    assert engine.build_round_order(1) == ["first", "second"]
    assert engine.dangos["first"].skill.rolls == 1
    assert engine.dangos["second"].skill.rolls == 1
```

- [ ] **Step 4: Add test that `starting_state` bypasses default opening stack**

Append:

```python
def test_starting_state_does_not_apply_default_opening_stack():
    starting_state = RaceStartingState(
        positions={4: ["a"], 5: ["b"]},
        laps_completed={"a": 0, "b": 0},
    )
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="a", name="A", skill=RecordingOrderSkill(3)),
            Dango(id="b", name="B", skill=RecordingOrderSkill(1)),
        ],
        include_bu_king=False,
        starting_state=starting_state,
    )
    engine = RaceEngine(config, rng=FixedRng([1, 1]))

    engine.state.round_number = 1
    order = engine.prepare_round(1)

    assert order == ["a", "b"]
    assert engine.state.stack_at(0) == []
    assert engine.state.stack_at(4) == ["a"]
    assert engine.state.stack_at(5) == ["b"]
```

- [ ] **Step 5: Run tests and verify they fail for missing helper**

Run:

```bash
uv run pytest tests/test_engine.py::test_no_starting_state_opening_stack_uses_first_round_order_before_round_start tests/test_engine.py::test_opening_stack_reuses_first_round_order_rolls_for_actual_turn_order tests/test_engine.py::test_starting_state_does_not_apply_default_opening_stack -q
```

Expected: fail with `AttributeError: 'RaceEngine' object has no attribute 'prepare_round'`.

---

### Task 2: Implement Engine Opening Stack Preparation

**Files:**
- Modify: `src/dango_sim/engine.py`
- Test: `tests/test_engine.py`

- [ ] **Step 1: Add engine state in `RaceEngine.__init__`**

In `src/dango_sim/engine.py`, after the forced-last sets are initialized, add:

```python
self.opening_stack_applied = self.config.starting_state is not None
self._cached_round_orders: dict[int, list[str]] = {}
```

- [ ] **Step 2: Add `prepare_round()` and `apply_default_opening_stack()` methods**

Add these methods above `start_round()`:

```python
def prepare_round(self, round_number: int) -> list[str]:
    self.state.round_number = round_number
    actors = self.actors_for_round(round_number)
    if round_number == 1 and not self.opening_stack_applied:
        order = self.build_round_order(round_number, actors)
        self._cached_round_orders[round_number] = list(order)
        self.apply_default_opening_stack(order)
    self.start_round(round_number)

    actors = [
        actor_id
        for actor_id in self.actors_for_round(round_number)
        if actor_id not in self.skip_turns_this_round
    ]
    if round_number in self._cached_round_orders:
        order = [
            actor_id
            for actor_id in self._cached_round_orders[round_number]
            if actor_id in actors
        ]
    else:
        order = self.build_round_order(round_number, actors)
    self._cached_round_orders[round_number] = list(order)
    return order

def apply_default_opening_stack(self, order: list[str]) -> None:
    normal_ids = set(self.normal_ids())
    stack = [
        dango_id
        for dango_id in reversed(order)
        if dango_id in normal_ids
    ]
    if stack:
        self.state.positions[0] = stack
        for dango_id in stack:
            self.state.laps_completed.setdefault(dango_id, 0)
        self.state._rebuild_index()
    self.opening_stack_applied = True
```

This intentionally stores bottom-to-top order. If the action order is `["first", "middle", "last"]`, the stored stack is `["last", "middle", "first"]`.

- [ ] **Step 3: Make `build_round_order()` reuse cached orders**

At the top of `build_round_order()`, after the method signature and before resolving `actors`, add:

```python
cached_order = self._cached_round_orders.get(round_number)
if cached_order is not None and actors is None:
    return self.apply_forced_last(list(cached_order))
```

This preserves existing direct calls while avoiding duplicate first-round order rolls after `prepare_round(1)`.

- [ ] **Step 4: Update `run()` to use `prepare_round()`**

Replace the current round setup block:

```python
self.state.round_number = round_number
self.start_round(round_number)
actors = [
    actor_id
    for actor_id in self.actors_for_round(round_number)
    if actor_id not in self.skip_turns_this_round
]
self._round_order_actors = actors
try:
    order = self.build_round_order(round_number)
finally:
    del self._round_order_actors
round_rolls = self.roll_round_values(actors)
```

with:

```python
order = self.prepare_round(round_number)
actors = list(order)
round_rolls = self.roll_round_values(actors)
```

- [ ] **Step 5: Run focused engine tests**

Run:

```bash
uv run pytest tests/test_engine.py::test_no_starting_state_opening_stack_uses_first_round_order_before_round_start tests/test_engine.py::test_opening_stack_reuses_first_round_order_rolls_for_actual_turn_order tests/test_engine.py::test_starting_state_does_not_apply_default_opening_stack -q
```

Expected: all pass.

- [ ] **Step 6: Run existing turn-order and Bu King regression tests**

Run:

```bash
uv run pytest tests/test_engine.py::test_round_rolls_are_materialized_before_first_turn tests/test_engine.py::test_bu_king_starts_at_zero_and_is_excluded_from_ranking tests/test_engine.py::test_round_order_excludes_bu_king_before_round_three tests/test_engine.py::test_bu_king_uses_configurable_order_faces_and_fixed_movement_faces_from_round_three -q
```

Expected: all pass.

- [ ] **Step 7: Commit engine change**

Run:

```bash
git add src/dango_sim/engine.py tests/test_engine.py
git commit -m "feat: apply first round opening stack"
```

---

### Task 3: Move Phrolova Decision To Round Start

**Files:**
- Modify: `src/dango_sim/skills.py`
- Modify: `tests/test_skills.py`
- Test: `tests/test_skills.py`

- [ ] **Step 1: Replace direct Phrolova unit tests**

In `tests/test_skills.py`, replace these tests:

- `test_phrolova_gains_three_when_bottom_with_rider_above`
- `test_phrolova_does_not_gain_bonus_when_alone_in_stack`
- `test_phrolova_does_not_gain_bonus_when_not_bottom`
- `test_phrolova_does_not_gain_bonus_when_unentered`

with:

```python
def test_phrolova_records_bonus_at_round_start_when_bottom_with_rider_above():
    skill = PhrolovaSkill()
    state = RaceState(positions={4: ["phrolova", "rider"]}, round_number=2)

    skill.on_round_start(
        Dango(id="phrolova", name="Phrolova"),
        state,
        engine=None,
        rng=FixedRng(),
    )
    context = TurnContext(round_rolls={"phrolova": 2}, base_roll=2, movement=2)
    skill.before_move(
        Dango(id="phrolova", name="Phrolova"),
        RaceState(positions={6: ["rider"], 8: ["phrolova"]}, round_number=2),
        context,
        FixedRng(),
    )

    assert context.movement == 5


def test_phrolova_consumes_round_start_bonus_once():
    skill = PhrolovaSkill()
    state = RaceState(positions={4: ["phrolova", "rider"]}, round_number=2)
    dango = Dango(id="phrolova", name="Phrolova")
    skill.on_round_start(dango, state, engine=None, rng=FixedRng())

    first = TurnContext(round_rolls={"phrolova": 2}, base_roll=2, movement=2)
    second = TurnContext(round_rolls={"phrolova": 2}, base_roll=2, movement=2)
    skill.before_move(dango, state, first, FixedRng())
    skill.before_move(dango, state, second, FixedRng())

    assert first.movement == 5
    assert second.movement == 2


def test_phrolova_does_not_record_bonus_when_alone_in_stack():
    skill = PhrolovaSkill()
    state = RaceState(positions={4: ["phrolova"]}, round_number=2)
    dango = Dango(id="phrolova", name="Phrolova")
    skill.on_round_start(dango, state, engine=None, rng=FixedRng())

    context = TurnContext(round_rolls={"phrolova": 2}, base_roll=2, movement=2)
    skill.before_move(dango, state, context, FixedRng())

    assert context.movement == 2


def test_phrolova_does_not_record_bonus_when_not_bottom():
    skill = PhrolovaSkill()
    state = RaceState(positions={4: ["base", "phrolova"]}, round_number=2)
    dango = Dango(id="phrolova", name="Phrolova")
    skill.on_round_start(dango, state, engine=None, rng=FixedRng())

    context = TurnContext(round_rolls={"phrolova": 2}, base_roll=2, movement=2)
    skill.before_move(dango, state, context, FixedRng())

    assert context.movement == 2


def test_phrolova_does_not_record_bonus_when_unentered():
    skill = PhrolovaSkill()
    state = RaceState.empty(["phrolova"])
    state.round_number = 2
    dango = Dango(id="phrolova", name="Phrolova")
    skill.on_round_start(dango, state, engine=None, rng=FixedRng())

    context = TurnContext(round_rolls={"phrolova": 2}, base_roll=2, movement=2)
    skill.before_move(dango, state, context, FixedRng())

    assert context.movement == 2
```

- [ ] **Step 2: Run Phrolova tests and verify failure**

Run:

```bash
uv run pytest tests/test_skills.py::test_phrolova_records_bonus_at_round_start_when_bottom_with_rider_above tests/test_skills.py::test_phrolova_consumes_round_start_bonus_once tests/test_skills.py::test_phrolova_does_not_record_bonus_when_alone_in_stack tests/test_skills.py::test_phrolova_does_not_record_bonus_when_not_bottom tests/test_skills.py::test_phrolova_does_not_record_bonus_when_unentered -q
```

Expected: fail with `AttributeError: 'PhrolovaSkill' object has no attribute 'on_round_start'`.

- [ ] **Step 3: Update `PhrolovaSkill` implementation**

In `src/dango_sim/skills.py`, replace `PhrolovaSkill` with:

```python
@dataclass
class PhrolovaSkill:
    bonus: int = 3
    pending_round: int | None = None

    def on_round_start(self, dango: Dango, state: RaceState, engine, rng) -> None:
        if _is_bottom(dango, state):
            self.pending_round = state.round_number

    def before_move(self, dango: Dango, state: RaceState, context, rng) -> None:
        if self.pending_round == state.round_number:
            context.movement += self.bonus
            self.pending_round = None
```

This uses the current `_is_bottom()` helper, so the criteria remain "entered, bottom, stack size at least 2". The check happens only during `on_round_start`; `before_move` consumes the stored result.

- [ ] **Step 4: Run Phrolova tests**

Run:

```bash
uv run pytest tests/test_skills.py::test_phrolova_records_bonus_at_round_start_when_bottom_with_rider_above tests/test_skills.py::test_phrolova_consumes_round_start_bonus_once tests/test_skills.py::test_phrolova_does_not_record_bonus_when_alone_in_stack tests/test_skills.py::test_phrolova_does_not_record_bonus_when_not_bottom tests/test_skills.py::test_phrolova_does_not_record_bonus_when_unentered -q
```

Expected: all pass.

- [ ] **Step 5: Add integration test for opening stack triggering Phrolova**

Append this test to `tests/test_engine.py`:

```python
def test_opening_stack_can_trigger_phrolova_round_start_bonus():
    config = RaceConfig(
        board=Board(finish=4),
        participants=[
            Dango(id="top", name="Top", skill=RecordingOrderSkill(3)),
            Dango(id="phrolova", name="Phrolova", skill=PhrolovaSkill()),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng([1, 1, 1]))

    result = engine.run()

    assert result.winner_id == "phrolova"
    assert result.rounds == 1
```

Also add `PhrolovaSkill` to the imports at the top of `tests/test_engine.py`:

```python
from dango_sim.skills import LuukHerssenSkill, PhrolovaSkill
```

Default high-first ordering makes `top` act first and places Phrolova at the bottom of the opening stack. `top` moves away, then Phrolova consumes its round-start bonus: movement roll `1` becomes `4`, so it passes start on a `finish=4` board and wins in round 1.

- [ ] **Step 6: Run integration test**

Run:

```bash
uv run pytest tests/test_engine.py::test_opening_stack_can_trigger_phrolova_round_start_bonus -q
```

Expected: pass.

- [ ] **Step 7: Run skill and engine focused tests together**

Run:

```bash
uv run pytest tests/test_skills.py::test_phrolova_records_bonus_at_round_start_when_bottom_with_rider_above tests/test_skills.py::test_phrolova_consumes_round_start_bonus_once tests/test_skills.py::test_phrolova_does_not_record_bonus_when_alone_in_stack tests/test_skills.py::test_phrolova_does_not_record_bonus_when_not_bottom tests/test_skills.py::test_phrolova_does_not_record_bonus_when_unentered tests/test_engine.py::test_opening_stack_can_trigger_phrolova_round_start_bonus -q
```

Expected: all pass.

- [ ] **Step 8: Commit Phrolova change**

Run:

```bash
git add src/dango_sim/skills.py tests/test_skills.py tests/test_engine.py
git commit -m "feat: check phrolova at round start"
```

---

### Task 4: Update Documentation

**Files:**
- Modify: `README.md`
- Modify: `src/dango_sim/AGENTS.md`

- [ ] **Step 1: Update README starting-state section**

In `README.md`, after the `Starting states` heading and before the JSON example, add:

```markdown
When no `--starting-state` file is supplied, the first round rolls action
order first, places all normal dangos on position `0`, and starts the race from
that stack. The first actor in the first-round order is placed on top of the
stack. Round-start skills then run before any dango moves.
```

- [ ] **Step 2: Update `src/dango_sim/AGENTS.md` common patterns**

Replace this bullet:

```markdown
- Starting states are editable JSON via `state_io.py`; no-start races begin with normal dango unentered until their first action.
```

with:

```markdown
- Starting states are editable JSON via `state_io.py`; no-start races roll first-round action order, stack normal dangos on position `0` with the first actor on top, then run round-start hooks before movement.
```

- [ ] **Step 3: Run diff check**

Run:

```bash
git diff --check README.md src/dango_sim/AGENTS.md
```

Expected: no output.

- [ ] **Step 4: Commit docs**

Run:

```bash
git add README.md src/dango_sim/AGENTS.md
git commit -m "docs: describe opening stack startup"
```

---

### Task 5: Full Verification

**Files:**
- Verify repository state only.

- [ ] **Step 1: Run full test suite**

Run:

```bash
uv run pytest
```

Expected: all tests pass.

- [ ] **Step 2: Run baseline CLI smoke**

Run:

```bash
uv run python main.py --runs 20 --seed 42 --top-n 3 4
```

Expected: command exits 0 and prints win-rate / top-N summary.

- [ ] **Step 3: Run starting-state CLI smoke**

Create a temporary starting-state smoke file for the current sample participants:

```powershell
@'
{
  "positions": {
    "0": ["augusta"],
    "1": ["iuno"],
    "2": ["phrolova"],
    "3": ["changli"],
    "4": ["jinhsi"],
    "5": ["calcharo"]
  },
  "laps_completed": {
    "augusta": 0,
    "iuno": 0,
    "phrolova": 0,
    "changli": 0,
    "jinhsi": 0,
    "calcharo": 0
  }
}
'@ | Set-Content -Path .\second-half-smoke.json -Encoding utf8
```

Then run:

```bash
uv run python main.py --runs 5 --seed 42 --starting-state .\second-half-smoke.json --top-n 3
```

Expected: command exits 0 and prints top-3 probability summary.

- [ ] **Step 4: Review git status**

Run:

```bash
git status --short
```

Expected: only intentional tracked-file changes from this plan are present, plus any unrelated pre-existing untracked files that were already in the workspace.

---

## Self-Review

- Spec coverage: Task 1 and Task 2 cover default first-round order stacking, first actor on top, round-start visibility, no duplicate order rolls, `starting_state` bypass, and Bu King regression. Task 3 covers Phrolova's round-start decision and action-time movement mutation. Task 4 covers README and AGENTS docs. Task 5 covers full verification.
- Placeholder scan: This plan contains no unresolved placeholders or ambiguous implementation steps.
- Type consistency: The plan uses existing `RaceEngine`, `RaceState`, `RaceConfig`, `RaceStartingState`, `Dango`, `TurnContext`, `PhrolovaSkill`, `build_round_order()`, `start_round()`, `roll_round_values()`, and `FixedRng` names. New names are `prepare_round()`, `apply_default_opening_stack()`, `opening_stack_applied`, `_cached_round_orders`, and `pending_round`.
