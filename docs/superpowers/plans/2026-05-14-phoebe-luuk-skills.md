# Phoebe and Luuk Herssen Skills Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add built-in Phoebe and Luuk Herssen dango skills with deterministic tests and sample config wiring.

**Architecture:** Phoebe uses the existing `modify_roll()` skill hook because her effect changes normal movement before the move path is built. Luuk Herssen needs a small engine extension: tile resolution carries the acting dango id to a new actor-only tile destination modifier hook, called after a tile computes its base destination and before `apply_tile_movement()` moves the group.

**Tech Stack:** Python 3.12, dataclasses, existing hook-based `dango_sim` engine, pytest via `uv run`.

---

## File Structure

- Modify `src/dango_sim/skills.py`: add `PhoebeSkill` and `LuukHerssenSkill`; import `Booster` and `Inhibitor` for Luuk tile type checks.
- Modify `src/dango_sim/engine.py`: pass `actor_id` through tile resolution and call `modify_tile_destination()` on the current actor's skill.
- Modify `src/dango_sim/sample_config.py`: import and include the two new skills in the sample participant list.
- Modify `tests/test_skills.py`: add isolated tests for Phoebe and Luuk's tile modifier method.
- Modify `tests/test_engine.py`: add integration tests proving actor-only Luuk tile behavior and single/chain semantics.
- Modify `tests/test_sample_config.py`: assert the sample config includes Phoebe and Luuk Herssen.

## Task 1: Add Phoebe Skill With Focused Unit Tests

**Files:**
- Modify: `tests/test_skills.py`
- Modify: `src/dango_sim/skills.py`

- [ ] **Step 1: Add Phoebe import in skill tests**

In `tests/test_skills.py`, update the import block from `dango_sim.skills` to include `PhoebeSkill`.

```python
from dango_sim.skills import (
    AemeathSkill,
    AugustaSkill,
    CalcharoSkill,
    CarlottaSkill,
    ChangliSkill,
    IunoSkill,
    JinhsiSkill,
    LynaeSkill,
    LuukHerssenSkill,
    MornyeSkill,
    PhoebeSkill,
    PhrolovaSkill,
    ChisaSkill,
    ShorekeeperSkill,
)
```

- [ ] **Step 2: Write failing Phoebe tests**

Add these tests near the existing `test_carlotta_doubles_roll_when_probability_triggers()` test in `tests/test_skills.py`.

```python
def test_phoebe_adds_one_when_probability_triggers():
    skill = PhoebeSkill()
    context = TurnContext(round_rolls={"phoebe": 2}, base_roll=2, movement=2)

    movement = skill.modify_roll(
        Dango(id="phoebe", name="Phoebe"),
        2,
        RaceState.initial(["phoebe"]),
        context,
        FixedRng(randoms=[0.49]),
    )

    assert movement == 3


def test_phoebe_keeps_roll_when_probability_misses():
    skill = PhoebeSkill()
    context = TurnContext(round_rolls={"phoebe": 2}, base_roll=2, movement=2)

    movement = skill.modify_roll(
        Dango(id="phoebe", name="Phoebe"),
        2,
        RaceState.initial(["phoebe"]),
        context,
        FixedRng(randoms=[0.50]),
    )

    assert movement == 2
```

- [ ] **Step 3: Run Phoebe tests and verify they fail**

Run:

```powershell
uv run pytest tests/test_skills.py::test_phoebe_adds_one_when_probability_triggers tests/test_skills.py::test_phoebe_keeps_roll_when_probability_misses -q
```

Expected: both tests fail with an import error or name error for `PhoebeSkill`.

- [ ] **Step 4: Implement `PhoebeSkill`**

In `src/dango_sim/skills.py`, add this class after `CarlottaSkill` and before `ChisaSkill`.

```python
@dataclass
class PhoebeSkill:
    chance: float = 0.50
    bonus: int = 1

    def modify_roll(self, dango: Dango, roll: int, state: RaceState, context, rng) -> int:
        return roll + self.bonus if rng.random() < self.chance else roll
```

- [ ] **Step 5: Run Phoebe tests and verify they pass**

Run:

```powershell
uv run pytest tests/test_skills.py::test_phoebe_adds_one_when_probability_triggers tests/test_skills.py::test_phoebe_keeps_roll_when_probability_misses -q
```

Expected: both tests pass.

- [ ] **Step 6: Commit Phoebe skill**

Run:

```powershell
git add src/dango_sim/skills.py tests/test_skills.py
git commit -m "feat: add Phoebe skill"
```

Expected: commit succeeds with only `src/dango_sim/skills.py` and `tests/test_skills.py` staged.

## Task 2: Add Luuk Herssen Tile Modifier Hook and Integration Tests

**Files:**
- Modify: `tests/test_skills.py`
- Modify: `tests/test_engine.py`
- Modify: `src/dango_sim/skills.py`
- Modify: `src/dango_sim/engine.py`

- [ ] **Step 1: Add Luuk and tile imports for tests**

In `tests/test_skills.py`, ensure the `dango_sim.skills` import includes `LuukHerssenSkill` as shown in Task 1 Step 1.

Update the tile import in `tests/test_skills.py` from:

```python
from dango_sim.tiles import Booster
```

to:

```python
from dango_sim.tiles import Booster, Inhibitor, SpaceTimeRift
```

In `tests/test_engine.py`, add `LuukHerssenSkill` below the existing imports:

```python
from dango_sim.skills import LuukHerssenSkill
```

- [ ] **Step 2: Write failing isolated Luuk tests**

Add these tests in `tests/test_skills.py` near the other simple skill unit tests.

```python
def test_luuk_herssen_extends_booster_destination():
    skill = LuukHerssenSkill()
    context = TurnContext(round_rolls={"luuk_herssen": 1}, base_roll=1, movement=1)

    destination = skill.modify_tile_destination(
        Dango(id="luuk_herssen", name="Luuk Herssen"),
        Booster(),
        3,
        4,
        RaceState.initial(["luuk_herssen"]),
        context,
        FixedRng(),
    )

    assert destination == 7


def test_luuk_herssen_extends_inhibitor_destination_backward():
    skill = LuukHerssenSkill()
    context = TurnContext(round_rolls={"luuk_herssen": 1}, base_roll=1, movement=1)

    destination = skill.modify_tile_destination(
        Dango(id="luuk_herssen", name="Luuk Herssen"),
        Inhibitor(),
        10,
        9,
        RaceState.initial(["luuk_herssen"]),
        context,
        FixedRng(),
    )

    assert destination == 8


def test_luuk_herssen_ignores_non_booster_inhibitor_tile():
    skill = LuukHerssenSkill()
    context = TurnContext(round_rolls={"luuk_herssen": 1}, base_roll=1, movement=1)

    destination = skill.modify_tile_destination(
        Dango(id="luuk_herssen", name="Luuk Herssen"),
        SpaceTimeRift(),
        6,
        6,
        RaceState.initial(["luuk_herssen"]),
        context,
        FixedRng(),
    )

    assert destination == 6
```

- [ ] **Step 3: Write failing engine integration tests**

Add these tests in `tests/test_engine.py` near the existing tile resolution tests.

```python
def test_luuk_herssen_extends_booster_only_on_own_turn():
    config = RaceConfig(
        board=Board(finish=12, tiles={3: Booster()}),
        participants=[
            Dango(id="luuk_herssen", name="Luuk Herssen", skill=LuukHerssenSkill()),
            Dango(id="carrier", name="Carrier"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config)
    engine.state.positions = {2: ["luuk_herssen"], 1: ["carrier"]}

    engine.take_turn("luuk_herssen", base_roll=1, round_rolls={"luuk_herssen": 1, "carrier": 1})

    assert engine.state.position_of("luuk_herssen") == 7


def test_luuk_herssen_extends_inhibitor_only_on_own_turn():
    config = RaceConfig(
        board=Board(finish=12, tiles={10: Inhibitor()}),
        participants=[Dango(id="luuk_herssen", name="Luuk Herssen", skill=LuukHerssenSkill())],
        include_bu_king=False,
    )
    engine = RaceEngine(config)
    engine.state.positions = {9: ["luuk_herssen"]}

    engine.take_turn("luuk_herssen", base_roll=1, round_rolls={"luuk_herssen": 1})

    assert engine.state.position_of("luuk_herssen") == 8


def test_luuk_herssen_does_not_trigger_when_carried_by_another_dango():
    config = RaceConfig(
        board=Board(finish=12, tiles={3: Booster()}),
        participants=[
            Dango(id="carrier", name="Carrier"),
            Dango(id="luuk_herssen", name="Luuk Herssen", skill=LuukHerssenSkill()),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config)
    engine.state.positions = {2: ["carrier", "luuk_herssen"]}

    engine.take_turn("carrier", base_roll=1, round_rolls={"carrier": 1, "luuk_herssen": 1})

    assert engine.state.position_of("carrier") == 4
    assert engine.state.position_of("luuk_herssen") == 4


def test_luuk_herssen_extra_single_tile_movement_does_not_chain_by_default():
    config = RaceConfig(
        board=Board(finish=12, tiles={3: Booster(), 7: Booster()}),
        participants=[Dango(id="luuk_herssen", name="Luuk Herssen", skill=LuukHerssenSkill())],
        include_bu_king=False,
    )
    engine = RaceEngine(config)
    engine.state.positions = {2: ["luuk_herssen"]}

    engine.take_turn("luuk_herssen", base_roll=1, round_rolls={"luuk_herssen": 1})

    assert engine.state.position_of("luuk_herssen") == 7


def test_luuk_herssen_extra_chain_tile_movement_can_continue_chaining():
    config = RaceConfig(
        board=Board(finish=12, tiles={3: Booster(), 7: Booster()}),
        participants=[Dango(id="luuk_herssen", name="Luuk Herssen", skill=LuukHerssenSkill())],
        include_bu_king=False,
        tile_resolution="chain",
    )
    engine = RaceEngine(config)
    engine.state.positions = {2: ["luuk_herssen"]}

    engine.take_turn("luuk_herssen", base_roll=1, round_rolls={"luuk_herssen": 1})

    assert engine.state.position_of("luuk_herssen") == 11
```

- [ ] **Step 4: Run Luuk tests and verify they fail**

Run:

```powershell
uv run pytest tests/test_skills.py::test_luuk_herssen_extends_booster_destination tests/test_skills.py::test_luuk_herssen_extends_inhibitor_destination_backward tests/test_skills.py::test_luuk_herssen_ignores_non_booster_inhibitor_tile tests/test_engine.py::test_luuk_herssen_extends_booster_only_on_own_turn tests/test_engine.py::test_luuk_herssen_extends_inhibitor_only_on_own_turn tests/test_engine.py::test_luuk_herssen_does_not_trigger_when_carried_by_another_dango tests/test_engine.py::test_luuk_herssen_extra_single_tile_movement_does_not_chain_by_default tests/test_engine.py::test_luuk_herssen_extra_chain_tile_movement_can_continue_chaining -q
```

Expected: tests fail because `LuukHerssenSkill` or `modify_tile_destination` does not exist yet.

- [ ] **Step 5: Implement `LuukHerssenSkill`**

In `src/dango_sim/skills.py`, add this import near the top:

```python
from dango_sim.tiles import Booster, Inhibitor
```

Add this class after `PhoebeSkill` and before `ChisaSkill`.

```python
@dataclass(frozen=True)
class LuukHerssenSkill:
    booster_bonus: int = 3
    inhibitor_penalty: int = 1

    def modify_tile_destination(
        self,
        dango: Dango,
        tile,
        current: int,
        next_position: int,
        state: RaceState,
        context,
        rng,
    ) -> int:
        if isinstance(tile, Booster):
            return next_position + self.booster_bonus
        if isinstance(tile, Inhibitor):
            return next_position - self.inhibitor_penalty
        return next_position
```

- [ ] **Step 6: Extend engine tile resolution with actor id**

In `src/dango_sim/engine.py`, update `move_group_to()` so it passes the actor id to tile resolution.

```python
        self.after_group_stacked(group, destination, actor_id)
        self.resolve_tiles(group, destination, actor_id=actor_id)
        self.after_any_move(group, path or [destination], actor_id)
```

Update `take_bu_king_turn()` so Bu King remains explicit as the tile actor.

```python
        final_position = self.state.position_of(BU_KING_ID)
        final_group = self.bu_king_group()
        self.resolve_tiles(final_group, final_position, actor_id=BU_KING_ID)
        self.after_any_move(final_group, path, BU_KING_ID)
        self._emit("bu_king", roll=roll, path=list(path), state=self.state)
```

Replace the existing tile resolution methods with these versions.

```python
    def resolve_tiles(
        self,
        group: list[str],
        position: int,
        *,
        actor_id: str | None = None,
    ) -> None:
        if self.config.tile_resolution == "single":
            self.resolve_single_tile(group, position, actor_id=actor_id)
            return

        self.resolve_chained_tiles(group, position, actor_id=actor_id)

    def resolve_single_tile(
        self,
        group: list[str],
        position: int,
        *,
        actor_id: str | None = None,
    ) -> None:
        current = self.normalize_position(position)
        tile = self.config.board.tiles.get(current)
        if tile is None:
            return

        next_position = tile.on_landed(group, current, self.state, self.rng)
        next_position = self.modify_tile_destination(
            actor_id,
            group,
            tile,
            current,
            next_position,
        )
        self._emit("tile", group=list(group), position=current, tile=tile, next_position=next_position, state=self.state)
        self.apply_tile_movement(group, current, next_position)

    def resolve_chained_tiles(
        self,
        group: list[str],
        position: int,
        *,
        actor_id: str | None = None,
    ) -> None:
        current = position
        for _ in range(self.config.max_tile_depth):
            current = self.normalize_position(current)
            tile = self.config.board.tiles.get(current)
            if tile is None:
                return

            next_position = tile.on_landed(group, current, self.state, self.rng)
            next_position = self.modify_tile_destination(
                actor_id,
                group,
                tile,
                current,
                next_position,
            )
            self._emit("tile", group=list(group), position=current, tile=tile, next_position=next_position, state=self.state)
            moved_position = self.apply_tile_movement(group, current, next_position)
            if moved_position == current or self.has_finished():
                return

            current = moved_position

        if self.config.board.tiles.get(current) is None:
            return
        raise RuntimeError("tile resolution exceeded maximum depth")
```

Add this helper after `resolve_chained_tiles()` and before `apply_tile_movement()`.

```python
    def modify_tile_destination(
        self,
        actor_id: str | None,
        group: list[str],
        tile,
        current: int,
        next_position: int,
    ) -> int:
        if actor_id is None or actor_id not in self.dangos:
            return next_position
        if actor_id not in group:
            return next_position

        dango = self.dangos[actor_id]
        if not dango.skill or not hasattr(dango.skill, "modify_tile_destination"):
            return next_position

        context = TurnContext(
            round_rolls={},
            base_roll=0,
            movement=0,
            group=list(group),
            destination=self.normalize_position(current),
            engine=self,
        )
        modified = dango.skill.modify_tile_destination(
            dango,
            tile,
            current,
            next_position,
            self.state,
            context,
            self.rng,
        )
        self._emit("skill", dango_id=actor_id, hook_name="modify_tile_destination", state=self.state)
        return int(modified)
```

- [ ] **Step 7: Run Luuk tests and verify they pass**

Run:

```powershell
uv run pytest tests/test_skills.py::test_luuk_herssen_extends_booster_destination tests/test_skills.py::test_luuk_herssen_extends_inhibitor_destination_backward tests/test_skills.py::test_luuk_herssen_ignores_non_booster_inhibitor_tile tests/test_engine.py::test_luuk_herssen_extends_booster_only_on_own_turn tests/test_engine.py::test_luuk_herssen_extends_inhibitor_only_on_own_turn tests/test_engine.py::test_luuk_herssen_does_not_trigger_when_carried_by_another_dango tests/test_engine.py::test_luuk_herssen_extra_single_tile_movement_does_not_chain_by_default tests/test_engine.py::test_luuk_herssen_extra_chain_tile_movement_can_continue_chaining -q
```

Expected: all listed tests pass.

- [ ] **Step 8: Run existing tile and engine regression subset**

Run:

```powershell
uv run pytest tests/test_tiles.py tests/test_engine.py::test_single_tile_resolution_does_not_chain_by_default tests/test_engine.py::test_chain_tile_resolution_remains_opt_in tests/test_engine.py::test_chain_tile_resolution_wraps_tile_movement tests/test_engine.py::test_booster_tile_finishes_when_forward_path_passes_start tests/test_engine.py::test_inhibitor_tile_wraps_backward_without_finishing -q
```

Expected: all listed tests pass, proving existing tile semantics were not changed.

- [ ] **Step 9: Commit Luuk skill and engine hook**

Run:

```powershell
git add src/dango_sim/skills.py src/dango_sim/engine.py tests/test_skills.py tests/test_engine.py
git commit -m "feat: add Luuk Herssen tile skill"
```

Expected: commit succeeds with the Luuk skill, engine hook, and tests.

## Task 3: Wire Sample Config and Verify End-to-End

**Files:**
- Modify: `src/dango_sim/sample_config.py`
- Modify: `tests/test_sample_config.py`
- Optionally modify: `README.md` only if it has an explicit built-in skill roster that is now stale.

- [ ] **Step 1: Add sample config imports**

In `src/dango_sim/sample_config.py`, update the skill import block to include `LuukHerssenSkill` and `PhoebeSkill`.

```python
from dango_sim.skills import (
    AemeathSkill,
    AugustaSkill,
    CalcharoSkill,
    CarlottaSkill,
    ChangliSkill,
    ChisaSkill,
    IunoSkill,
    JinhsiSkill,
    LuukHerssenSkill,
    LynaeSkill,
    MornyeSkill,
    PhoebeSkill,
    PhrolovaSkill,
    ShorekeeperSkill,
)
```

- [ ] **Step 2: Add Phoebe and Luuk to sample participants**

In `src/dango_sim/sample_config.py`, add the two active participants after the existing active six dangos.

```python
            Dango(id="augusta", name="奥古斯塔团子", skill=AugustaSkill()),
            Dango(id="iuno", name="尤诺团子", skill=IunoSkill()),
            Dango(id="phrolova", name="弗洛洛团子", skill=PhrolovaSkill()),
            Dango(id="changli", name="长离团子", skill=ChangliSkill()),
            Dango(id="jinhsi", name="今汐团子", skill=JinhsiSkill()),
            Dango(id="calcharo", name="卡卡罗团子", skill=CalcharoSkill()),
            Dango(id="phoebe", name="菲比团子", skill=PhoebeSkill()),
            Dango(id="luuk_herssen", name="陆·赫斯团子", skill=LuukHerssenSkill()),
```

- [ ] **Step 3: Update sample config tests**

In `tests/test_sample_config.py`, update the import block.

```python
from dango_sim.skills import (
    AugustaSkill,
    CalcharoSkill,
    ChangliSkill,
    IunoSkill,
    JinhsiSkill,
    LuukHerssenSkill,
    PhoebeSkill,
    PhrolovaSkill,
)
```

Add these assertions to `test_sample_config_includes_new_dango_skills()`.

```python
    assert isinstance(skills_by_id["phoebe"], PhoebeSkill)
    assert isinstance(skills_by_id["luuk_herssen"], LuukHerssenSkill)
```

- [ ] **Step 4: Run sample config test**

Run:

```powershell
uv run pytest tests/test_sample_config.py -q
```

Expected: sample config test passes and confirms both new dangos are present.

- [ ] **Step 5: Check README for stale skill roster**

Run:

```powershell
rg -n "Augusta|Iuno|Phrolova|Changli|Jinhsi|Calcharo|Phoebe|Luuk|技能|skill" README.md
```

Expected: if README has no explicit built-in skill roster, no README edit is needed. If it lists built-in sample participants, update that list to include Phoebe and Luuk Herssen in the same style before continuing.

- [ ] **Step 6: Run full test suite**

Run:

```powershell
uv run pytest
```

Expected: full suite passes.

- [ ] **Step 7: Run CLI smoke test**

Run:

```powershell
uv run python main.py --runs 20 --seed 42
```

Expected: command exits successfully and prints simulation results. The sample config should run with the two new participants included.

- [ ] **Step 8: Commit sample config and verification updates**

Run:

```powershell
git add src/dango_sim/sample_config.py tests/test_sample_config.py README.md
git diff --cached --name-only
git commit -m "feat: include Phoebe and Luuk in sample config"
```

Expected: commit succeeds. If README did not change, `git add README.md` is harmless and `git diff --cached --name-only` should list only `src/dango_sim/sample_config.py` and `tests/test_sample_config.py`.

## Final Verification

- [ ] **Step 1: Confirm working tree state**

Run:

```powershell
git status --short
```

Expected: no modified tracked files remain. Pre-existing untracked files may remain if they were already present before this work.

- [ ] **Step 2: Run final verification**

Run:

```powershell
uv run pytest
uv run python main.py --runs 20 --seed 42
```

Expected: both commands succeed.

- [ ] **Step 3: Summarize implementation**

Prepare a final summary with:

- The new skill classes and hook names.
- The key actor-only Luuk rule: Luuk triggers only when `actor_id == "luuk_herssen"` and he is in the moving group.
- Verification commands and results.
- Any remaining untracked files that were present and intentionally left untouched.
