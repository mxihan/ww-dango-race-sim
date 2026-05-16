# Denia, Sigrika & Engine Changes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Denia (match-dice bonus) and Sigrika (neighbor slowdown aura) skills, switch turn order to random shuffle, move default start to tile 1, and add a cross-dango penalty mechanism.

**Architecture:** Two new skill dataclasses hook into existing engine hooks (`modify_roll`, `on_round_start`). The engine gains a `round_penalties` dict cleared each round and applied in `take_turn` after `before_move`. Turn ordering switches from dice-roll-and-sort to `rng.shuffle`. Default opening stack moves from position 0 to position 1.

**Tech Stack:** Python, pytest

---

### Task 1: Shuffle-Based Turn Order + Position-1 Default Start

**Files:**
- Modify: `src/dango_sim/engine.py:192-243` (build_round_order, remove dead methods)
- Modify: `src/dango_sim/engine.py:137-148` (apply_default_opening_stack position)
- Modify: `tests/test_engine.py` (update/remove affected tests)
- Modify: `tests/test_skills.py:439-449` (remove mornye order test)

- [ ] **Step 1: Write new test for shuffle order**

Add to `tests/test_engine.py` (replace `test_round_order_uses_high_first_order_rolls_and_shuffles_ties` and `test_round_order_can_use_low_first_order_rolls`):

```python
def test_round_order_uses_random_shuffle():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="a", name="A"),
            Dango(id="b", name="B"),
            Dango(id="c", name="C"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=QueueRng([1, 1, 1], shuffles=[["c", "a", "b"]]))

    order = engine.build_round_order(1)

    assert order == ["c", "a", "b"]
```

- [ ] **Step 2: Write new test for position-1 opening stack**

Replace `test_no_starting_state_opening_stack_uses_first_round_order_before_round_start`:

```python
def test_no_starting_state_opening_stack_uses_shuffled_order():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="first", name="First"),
            Dango(id="second", name="Second"),
            Dango(id="third", name="Third"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=QueueRng([1, 1, 1], shuffles=[["first", "second", "third"]]))
    engine.state.round_number = 1
    order = engine.prepare_round(1)

    assert order == ["first", "second", "third"]
    assert engine.state.stack_at(1) == ["third", "second", "first"]
```

- [ ] **Step 3: Write new test for cached first-round shuffle order**

Replace `test_opening_stack_reuses_first_round_order_rolls_for_actual_turn_order`:

```python
def test_opening_stack_reuses_first_round_shuffle_order():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="first", name="First"),
            Dango(id="second", name="Second"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=QueueRng([1, 1], shuffles=[["first", "second"]]))
    engine.state.round_number = 1
    order = engine.prepare_round(1)

    assert order == ["first", "second"]
    assert engine.build_round_order(1) == ["first", "second"]
```

- [ ] **Step 4: Write new test for forced-last with cached shuffle order**

Replace `test_opening_stack_cached_first_round_order_applies_preexisting_forced_last`:

```python
def test_opening_stack_cached_first_round_order_applies_preexisting_forced_last():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="forced", name="Forced"),
            Dango(id="other", name="Other"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=QueueRng([1, 1], shuffles=[["forced", "other"]]))
    engine.force_last_next_round("forced")
    engine.state.round_number = 1
    order = engine.prepare_round(1)

    assert order == ["other", "forced"]
    assert engine.build_round_order(1) == ["other", "forced"]
```

- [ ] **Step 5: Run tests to verify new tests fail**

Run: `cd "F:/AI Projects/projects/ww-dango" && pytest tests/test_engine.py -v -k "test_round_order_uses_random_shuffle or test_no_starting_state_opening_stack_uses_shuffled_order or test_opening_stack_reuses_first_round_shuffle_order or test_opening_stack_cached_first_round_order_applies_preexisting_forced_last" 2>&1 | tail -20`
Expected: FAIL (new tests not yet passing, old tests still exist)

- [ ] **Step 6: Modify `build_round_order` to use shuffle**

In `src/dango_sim/engine.py`, replace the body of `build_round_order`:

```python
    def build_round_order(
        self,
        round_number: int,
        actors: Iterable[str] | None = None,
    ) -> list[str]:
        cached_order = self._cached_round_orders.get(round_number)
        if cached_order is not None and actors is None:
            return self.apply_forced_last(list(cached_order))
        if actors is None:
            actors = getattr(
                self,
                "_round_order_actors",
                self.actors_for_round(round_number),
            )
        shuffled = list(actors)
        self.rng.shuffle(shuffled)
        return self.apply_forced_last(shuffled)
```

- [ ] **Step 7: Remove dead methods from engine**

Remove these four methods from `src/dango_sim/engine.py`:
- `roll_order_values`
- `order_actors`
- `roll_for_order`
- `roll_bu_king_order`

- [ ] **Step 8: Change default starting position to tile 1**

In `src/dango_sim/engine.py`, in `apply_default_opening_stack`, change:

```python
        self.state.place_group(stack, 1)
```

(was `self.state.place_group(stack, 0)`)

- [ ] **Step 9: Remove/rewrite affected existing tests in test_engine.py**

Remove these tests entirely (they test removed methods):
- `test_round_order_uses_high_first_order_rolls_and_shuffles_ties`
- `test_round_order_can_use_low_first_order_rolls`
- `test_bu_king_uses_configurable_order_faces_and_fixed_movement_faces_from_round_three`

Remove these helper classes (no longer used):
- `RecordingOrderSkill` — but keep if `test_opening_stack_can_trigger_phrolova_round_start_bonus` still uses it (it does, keep it)
- `RecordingRoundStartSkill` — no longer used, remove

Update `test_bu_king_in_starting_state_does_not_roll_before_round_three` — remove `roll_order_values` usage, keep the actors/move_rolls checks:

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
    engine = RaceEngine(config, rng=QueueRng([2]))

    actors = engine.actors_for_round(1)
    move_rolls = engine.roll_round_values(actors)

    assert actors == ["a"]
    assert move_rolls == {"a": 2}
    assert engine.state.position_of(BU_KING_ID) == 5
```

Update `test_round_rolls_are_materialized_before_first_turn` — change `FixedRng([1, 1, 1, 1, 2, 3])` to `FixedRng([1, 2, 3])` (no order rolls consumed):

```python
    engine = RaceEngine(config, rng=FixedRng([1, 2, 3]))
```

Update `test_opening_stack_can_trigger_phrolova_round_start_bonus` — change board finish from 4 to 5 (position-1 start changes dynamics):

```python
    config = RaceConfig(
        board=Board(finish=5),
        ...
    )
```

Update `test_run_loop_only_rolls_skipped_stateful_skill_for_opening_order` — rename and change expected index from 1 to 0 (no order roll consumed), change FixedRng choices from `[1, 1]` to `[1]`:

```python
def test_shuffle_order_does_not_roll_for_skipped_skill():
    skill = StatefulSkipRoundStartSkill()
    config = RaceConfig(
        board=Board(finish=1),
        participants=[
            Dango(id="skipped", name="Skipped", skill=skill),
            Dango(id="winner", name="Winner"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng(choices=[1]))
    result = engine.run()

    assert result.winner_id == "winner"
    assert engine.dangos["skipped"].skill.index == 0
```

- [ ] **Step 10: Remove affected test in test_skills.py**

Remove `test_mornye_rolls_once_for_order_and_once_for_movement` (tests removed `roll_for_order` method).

- [ ] **Step 11: Run all tests**

Run: `cd "F:/AI Projects/projects/ww-dango" && pytest -v --tb=short 2>&1 | tail -30`
Expected: ALL PASS

- [ ] **Step 12: Commit**

```bash
git add src/dango_sim/engine.py tests/test_engine.py tests/test_skills.py
git commit -m "feat: shuffle-based turn order, position-1 default start"
```

---

### Task 2: Cross-Dango Penalty Mechanism

**Files:**
- Modify: `src/dango_sim/engine.py` (__init__, start_round, take_turn)
- Modify: `tests/test_engine.py` (add penalty tests)

- [ ] **Step 1: Write failing test for penalty mechanism**

Add to `tests/test_engine.py`:

```python
def test_round_penalties_reduce_movement_with_floor_of_one():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="a", name="A"),
            Dango(id="b", name="B"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng([3, 1]))
    engine.state = RaceState(positions={0: ["a", "b"]})

    engine.start_round(1)
    engine.round_penalties["a"] = 1

    engine.take_turn("a", base_roll=3, round_rolls={"a": 3, "b": 1})

    assert engine.state.position_of("a") == 2


def test_round_penalties_do_not_reduce_movement_below_one():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="a", name="A"),
            Dango(id="b", name="B"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng([1, 1]))
    engine.state = RaceState(positions={0: ["a", "b"]})

    engine.start_round(1)
    engine.round_penalties["a"] = 5

    engine.take_turn("a", base_roll=1, round_rolls={"a": 1, "b": 1})

    assert engine.state.position_of("a") == 1


def test_round_penalties_clear_at_round_start():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[Dango(id="a", name="A")],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng([]))
    engine.round_penalties["a"] = 3

    engine.start_round(1)

    assert engine.round_penalties == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "F:/AI Projects/projects/ww-dango" && pytest tests/test_engine.py -v -k "round_penalties" 2>&1 | tail -15`
Expected: FAIL

- [ ] **Step 3: Add `round_penalties` to engine __init__**

In `src/dango_sim/engine.py`, in `__init__`, add after `self._cached_round_orders`:

```python
        self.round_penalties: dict[str, int] = {}
```

- [ ] **Step 4: Clear penalties in `start_round`**

In `start_round`, add as the first line (before `self.force_last_this_round_ids = ...`):

```python
        self.round_penalties.clear()
```

- [ ] **Step 5: Apply penalties in `take_turn` after `before_move`**

In `take_turn`, after the `before_move` hook block (after `self._emit("skill", dango_id=dango_id, hook_name="before_move", state=self.state)`) and before `if context.blocked or context.movement <= 0:`, add:

```python
        penalty = self.round_penalties.get(dango_id, 0)
        if penalty:
            context.movement = max(1, context.movement - penalty)
```

- [ ] **Step 6: Run penalty tests**

Run: `cd "F:/AI Projects/projects/ww-dango" && pytest tests/test_engine.py -v -k "round_penalties" 2>&1 | tail -15`
Expected: ALL PASS

- [ ] **Step 7: Run all tests**

Run: `cd "F:/AI Projects/projects/ww-dango" && pytest -v --tb=short 2>&1 | tail -30`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add src/dango_sim/engine.py tests/test_engine.py
git commit -m "feat: add cross-dango penalty mechanism (round_penalties)"
```

---

### Task 3: DeniaSkill

**Files:**
- Modify: `src/dango_sim/skills.py` (add DeniaSkill)
- Modify: `tests/test_skills.py` (add Denia tests)

- [ ] **Step 1: Write failing tests for DeniaSkill**

Add to `tests/test_skills.py`:

```python
from dango_sim.skills import DeniaSkill


def test_denia_first_roll_never_triggers():
    skill = DeniaSkill()
    context = TurnContext(round_rolls={"d": 2}, base_roll=2, movement=2)

    movement = skill.modify_roll(
        Dango(id="d", name="Denia"),
        2,
        RaceState.initial(["d"]),
        context,
        FixedRng(),
    )

    assert movement == 2
    assert skill.last_roll == 2


def test_denia_matching_previous_roll_gives_bonus():
    skill = DeniaSkill()
    dango = Dango(id="d", name="Denia")
    state = RaceState.initial(["d"])

    skill.modify_roll(dango, 2, state, TurnContext(round_rolls={"d": 2}, base_roll=2, movement=2), FixedRng())

    context = TurnContext(round_rolls={"d": 2}, base_roll=2, movement=2)
    movement = skill.modify_roll(dango, 2, state, context, FixedRng())

    assert movement == 4
    assert skill.last_roll == 2


def test_denia_non_matching_roll_gives_no_bonus():
    skill = DeniaSkill()
    dango = Dango(id="d", name="Denia")
    state = RaceState.initial(["d"])

    skill.modify_roll(dango, 3, state, TurnContext(round_rolls={"d": 3}, base_roll=3, movement=3), FixedRng())

    context = TurnContext(round_rolls={"d": 2}, base_roll=2, movement=2)
    movement = skill.modify_roll(dango, 2, state, context, FixedRng())

    assert movement == 2
    assert skill.last_roll == 2


def test_denia_consecutive_matches_trigger_each_time():
    skill = DeniaSkill()
    dango = Dango(id="d", name="Denia")
    state = RaceState.initial(["d"])

    first = TurnContext(round_rolls={"d": 2}, base_roll=2, movement=2)
    skill.modify_roll(dango, 2, state, first, FixedRng())

    second = TurnContext(round_rolls={"d": 2}, base_roll=2, movement=2)
    skill.modify_roll(dango, 2, state, second, FixedRng())

    third = TurnContext(round_rolls={"d": 2}, base_roll=2, movement=2)
    result = skill.modify_roll(dango, 2, state, third, FixedRng())

    assert second.movement == 4
    assert result == 4
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "F:/AI Projects/projects/ww-dango" && pytest tests/test_skills.py -v -k "denia" 2>&1 | tail -15`
Expected: FAIL (ImportError)

- [ ] **Step 3: Add DeniaSkill to skills.py**

Add to `src/dango_sim/skills.py`:

```python
@dataclass
class DeniaSkill:
    last_roll: int | None = None
    bonus: int = 2

    def modify_roll(self, dango, roll, state, context, rng) -> int:
        result = roll
        if self.last_roll is not None and self.last_roll == roll:
            result = roll + self.bonus
        self.last_roll = roll
        return result
```

- [ ] **Step 4: Run Denia tests**

Run: `cd "F:/AI Projects/projects/ww-dango" && pytest tests/test_skills.py -v -k "denia" 2>&1 | tail -15`
Expected: ALL PASS

- [ ] **Step 5: Run all tests**

Run: `cd "F:/AI Projects/projects/ww-dango" && pytest -v --tb=short 2>&1 | tail -30`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add src/dango_sim/skills.py tests/test_skills.py
git commit -m "feat: add DeniaSkill — matching dice bonus"
```

---

### Task 4: SigrikaSkill

**Files:**
- Modify: `src/dango_sim/skills.py` (add SigrikaSkill)
- Modify: `tests/test_skills.py` (add Sigrika tests)

Note: No engine change needed — `on_round_start` is auto-discovered by the existing `_on_round_start_hooks` dispatch table.

- [ ] **Step 1: Write failing tests for SigrikaSkill**

Add to `tests/test_skills.py`:

```python
from dango_sim.skills import SigrikaSkill


def test_sigrika_marks_two_neighbors_above():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="first", name="First"),
            Dango(id="second", name="Second"),
            Dango(id="sigrika", name="Sigrika", skill=SigrikaSkill()),
            Dango(id="fourth", name="Fourth"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng())
    engine.state = RaceState(positions={8: ["first"], 6: ["second"], 4: ["sigrika"], 2: ["fourth"]})

    engine.start_round(1)

    assert engine.round_penalties.get("first") == 1
    assert engine.round_penalties.get("second") == 1
    assert "fourth" not in engine.round_penalties


def test_sigrika_ranked_first_marks_nobody():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="sigrika", name="Sigrika", skill=SigrikaSkill()),
            Dango(id="other", name="Other"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng())
    engine.state = RaceState(positions={8: ["sigrika"], 4: ["other"]})

    engine.start_round(1)

    assert engine.round_penalties == {}


def test_sigrika_ranked_second_marks_only_one():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="first", name="First"),
            Dango(id="sigrika", name="Sigrika", skill=SigrikaSkill()),
            Dango(id="third", name="Third"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng())
    engine.state = RaceState(positions={8: ["first"], 6: ["sigrika"], 2: ["third"]})

    engine.start_round(1)

    assert engine.round_penalties.get("first") == 1
    assert "third" not in engine.round_penalties


def test_sigrika_penalties_reset_each_round():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="first", name="First"),
            Dango(id="sigrika", name="Sigrika", skill=SigrikaSkill()),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng())
    engine.state = RaceState(positions={8: ["first"], 4: ["sigrika"]})

    engine.start_round(1)
    assert engine.round_penalties.get("first") == 1

    engine.state = RaceState(positions={8: ["sigrika"], 4: ["first"]})
    engine.start_round(2)
    assert engine.round_penalties == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "F:/AI Projects/projects/ww-dango" && pytest tests/test_skills.py -v -k "sigrika" 2>&1 | tail -15`
Expected: FAIL (ImportError)

- [ ] **Step 3: Add SigrikaSkill to skills.py**

Add to `src/dango_sim/skills.py`:

```python
@dataclass
class SigrikaSkill:
    max_targets: int = 2
    penalty: int = 1

    def on_round_start(self, dango, state, engine, rng) -> None:
        rankings = engine.rankings()
        if dango.id not in rankings:
            return
        my_index = rankings.index(dango.id)
        targets = []
        for i in range(my_index - 1, max(my_index - self.max_targets - 1, -1), -1):
            targets.append(rankings[i])
        for target_id in targets[:self.max_targets]:
            engine.round_penalties[target_id] = (
                engine.round_penalties.get(target_id, 0) + self.penalty
            )
```

- [ ] **Step 4: Run Sigrika tests**

Run: `cd "F:/AI Projects/projects/ww-dango" && pytest tests/test_skills.py -v -k "sigrika" 2>&1 | tail -15`
Expected: ALL PASS

- [ ] **Step 5: Run all tests**

Run: `cd "F:/AI Projects/projects/ww-dango" && pytest -v --tb=short 2>&1 | tail -30`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add src/dango_sim/skills.py tests/test_skills.py
git commit -m "feat: add SigrikaSkill — neighbor slowdown aura"
```

---

### Task 5: Update Participant Roster

**Files:**
- Modify: `src/dango_sim/sample_config.py`

- [ ] **Step 1: Add Denia and Sigrika imports and participants**

Update `src/dango_sim/sample_config.py`:

Add to imports:
```python
    DeniaSkill,
    SigrikaSkill,
```

Add to participants list (after cartethyia):
```python
            Dango(id="denia", name="达妮娅团子", skill=DeniaSkill()),
            Dango(id="sigrika", name="西格莉卡团子", skill=SigrikaSkill()),
```

- [ ] **Step 2: Run all tests**

Run: `cd "F:/AI Projects/projects/ww-dango" && pytest -v --tb=short 2>&1 | tail -30`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add src/dango_sim/sample_config.py
git commit -m "feat: add Denia and Sigrika to participant roster"
```
