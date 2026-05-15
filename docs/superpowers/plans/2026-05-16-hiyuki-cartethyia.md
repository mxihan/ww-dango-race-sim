# Hiyuki & Cartethyia Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add HiyukiSkill and CartethyiaSkill, update the participant roster, and add viewer colors.

**Architecture:** Two new skill dataclasses following existing patterns in `skills.py`. Hiyuki uses `after_any_move` + `before_move` hooks. Cartethyia uses `after_move` + `before_move` hooks. TDD cycle per skill.

**Tech Stack:** Python, pytest

---

### Task 1: HiyukiSkill — TDD implementation

**Files:**
- Modify: `src/dango_sim/skills.py` (append new class after `IunoSkill`)
- Modify: `tests/test_skills.py` (append new tests)

- [ ] **Step 1: Write failing tests for HiyukiSkill**

Append to `tests/test_skills.py`, adding `HiyukiSkill` to the import from `dango_sim.skills`:

```python
def test_hiyuki_encounters_bu_king_when_path_passes_through():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="hiyuki", name="绯雪团子", skill=HiyukiSkill()),
            Dango(id="other", name="Other"),
        ],
    )
    engine = RaceEngine(config, rng=FixedRng())
    engine.state = RaceState(positions={3: ["hiyuki"], 5: [BU_KING_ID], 10: ["other"]})

    engine.take_turn("hiyuki", base_roll=4, round_rolls={"hiyuki": 4, "other": 1})

    assert engine.dangos["hiyuki"].skill.encountered_bu_king is True


def test_hiyuki_encounters_bu_king_when_landing_on_same_position():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="hiyuki", name="绯雪团子", skill=HiyukiSkill()),
            Dango(id="other", name="Other"),
        ],
    )
    engine = RaceEngine(config, rng=FixedRng())
    engine.state = RaceState(positions={3: ["hiyuki"], 5: [BU_KING_ID], 10: ["other"]})

    engine.take_turn("hiyuki", base_roll=2, round_rolls={"hiyuki": 2, "other": 1})

    assert engine.dangos["hiyuki"].skill.encountered_bu_king is True


def test_hiyuki_encounters_bu_king_when_carried_to_bu_king():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="carrier", name="Carrier"),
            Dango(id="hiyuki", name="绯雪团子", skill=HiyukiSkill()),
            Dango(id="other", name="Other"),
        ],
    )
    engine = RaceEngine(config, rng=FixedRng())
    engine.state = RaceState(
        positions={5: ["carrier", "hiyuki"], 8: [BU_KING_ID], 10: ["other"]}
    )

    engine.take_turn(
        "carrier", base_roll=3, round_rolls={"carrier": 3, "hiyuki": 1, "other": 1}
    )

    assert engine.dangos["hiyuki"].skill.encountered_bu_king is True


def test_hiyuki_no_encounter_without_bu_king_contact():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="hiyuki", name="绯雪团子", skill=HiyukiSkill()),
            Dango(id="other", name="Other"),
        ],
    )
    engine = RaceEngine(config, rng=FixedRng())
    engine.state = RaceState(positions={3: ["hiyuki"], 10: [BU_KING_ID], 5: ["other"]})

    engine.take_turn("hiyuki", base_roll=2, round_rolls={"hiyuki": 2, "other": 1})

    assert engine.dangos["hiyuki"].skill.encountered_bu_king is False


def test_hiyuki_bonus_persists_after_encounter():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="hiyuki", name="绯雪团子", skill=HiyukiSkill()),
            Dango(id="other", name="Other"),
        ],
    )
    engine = RaceEngine(config, rng=FixedRng())
    engine.state = RaceState(positions={3: ["hiyuki"], 5: [BU_KING_ID], 10: ["other"]})

    engine.take_turn("hiyuki", base_roll=4, round_rolls={"hiyuki": 4, "other": 1})
    assert engine.dangos["hiyuki"].skill.encountered_bu_king is True
    assert engine.state.stack_at(7) == ["hiyuki"]

    engine.take_turn("hiyuki", base_roll=2, round_rolls={"hiyuki": 2, "other": 1})
    assert engine.state.stack_at(10) == ["hiyuki"]
```

Also add `HiyukiSkill` to the import block at top of file:

```python
from dango_sim.skills import (
    ...,
    HiyukiSkill,
)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_skills.py -k "hiyuki" -v`
Expected: FAIL — `ImportError: cannot import name 'HiyukiSkill'`

- [ ] **Step 3: Implement HiyukiSkill**

Append to `src/dango_sim/skills.py` after `IunoSkill`:

```python
@dataclass
class HiyukiSkill:
    encountered_bu_king: bool = False

    def after_any_move(self, dango: Dango, state: RaceState, context, rng, engine) -> None:
        if self.encountered_bu_king:
            return
        if not state.is_entered(BU_KING_ID):
            return

        bu_king_pos = state.position_of(BU_KING_ID)

        if state.is_entered(dango.id) and state.position_of(dango.id) == bu_king_pos:
            self.encountered_bu_king = True
            return

        group = getattr(context, "group", [])
        if dango.id in group and bu_king_pos in getattr(context, "path", []):
            self.encountered_bu_king = True

    def before_move(self, dango: Dango, state: RaceState, context, rng) -> None:
        if self.encountered_bu_king:
            context.movement += 1
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_skills.py -k "hiyuki" -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/dango_sim/skills.py tests/test_skills.py
git commit -m "feat: add HiyukiSkill — encounter Bu King for +1 movement"
```

---

### Task 2: CartethyiaSkill — TDD implementation

**Files:**
- Modify: `src/dango_sim/skills.py` (append after `HiyukiSkill`)
- Modify: `tests/test_skills.py` (append new tests)

- [ ] **Step 1: Write failing tests for CartethyiaSkill**

Append to `tests/test_skills.py`, adding `CartethyiaSkill` to the import:

```python
def test_cartethyia_triggers_when_last_after_own_move():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="leader", name="Leader"),
            Dango(id="middle", name="Middle"),
            Dango(id="cartethyia", name="卡提希娅团子", skill=CartethyiaSkill()),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng())
    engine.state = RaceState(positions={8: ["leader"], 5: ["middle"], 2: ["cartethyia"]})

    engine.take_turn(
        "cartethyia",
        base_roll=1,
        round_rolls={"leader": 1, "middle": 1, "cartethyia": 1},
    )

    assert engine.dangos["cartethyia"].skill.triggered is True


def test_cartethyia_does_not_trigger_when_not_last():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="cartethyia", name="卡提希娅团子", skill=CartethyiaSkill()),
            Dango(id="middle", name="Middle"),
            Dango(id="trailer", name="Trailer"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng())
    engine.state = RaceState(
        positions={8: ["cartethyia"], 5: ["middle"], 2: ["trailer"]}
    )

    engine.take_turn(
        "cartethyia",
        base_roll=1,
        round_rolls={"cartethyia": 1, "middle": 1, "trailer": 1},
    )

    assert engine.dangos["cartethyia"].skill.triggered is False


def test_cartethyia_gains_bonus_when_triggered_and_lucky():
    skill = CartethyiaSkill(triggered=True)
    context = TurnContext(round_rolls={"c": 2}, base_roll=2, movement=2)

    skill.before_move(
        Dango(id="c", name="Cartethyia"),
        RaceState.initial(["c"]),
        context,
        FixedRng(randoms=[0.59]),
    )

    assert context.movement == 4


def test_cartethyia_no_bonus_when_unlucky():
    skill = CartethyiaSkill(triggered=True)
    context = TurnContext(round_rolls={"c": 2}, base_roll=2, movement=2)

    skill.before_move(
        Dango(id="c", name="Cartethyia"),
        RaceState.initial(["c"]),
        context,
        FixedRng(randoms=[0.60]),
    )

    assert context.movement == 2


def test_cartethyia_triggers_only_once():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="leader", name="Leader"),
            Dango(id="cartethyia", name="卡提希娅团子", skill=CartethyiaSkill()),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng())
    engine.state = RaceState(positions={10: ["leader"], 2: ["cartethyia"]})

    engine.take_turn(
        "cartethyia", base_roll=1, round_rolls={"leader": 1, "cartethyia": 1}
    )
    assert engine.dangos["cartethyia"].skill.triggered is True

    engine.take_turn(
        "cartethyia", base_roll=1, round_rolls={"leader": 1, "cartethyia": 1}
    )
    assert engine.dangos["cartethyia"].skill.triggered is True


def test_cartethyia_excludes_bu_king_from_ranking():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="leader", name="Leader"),
            Dango(id="cartethyia", name="卡提希娅团子", skill=CartethyiaSkill()),
        ],
    )
    engine = RaceEngine(config, rng=FixedRng())
    engine.state = RaceState(
        positions={10: ["leader"], 2: ["cartethyia"], 1: [BU_KING_ID]}
    )

    engine.take_turn(
        "cartethyia", base_roll=1, round_rolls={"leader": 1, "cartethyia": 1}
    )

    assert engine.dangos["cartethyia"].skill.triggered is True
```

Also add `CartethyiaSkill` to the import block at top of file.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_skills.py -k "cartethyia" -v`
Expected: FAIL — `ImportError: cannot import name 'CartethyiaSkill'`

- [ ] **Step 3: Implement CartethyiaSkill**

Append to `src/dango_sim/skills.py` after `HiyukiSkill`:

```python
@dataclass
class CartethyiaSkill:
    triggered: bool = False
    chance: float = 0.60
    bonus: int = 2

    def after_move(self, dango: Dango, state: RaceState, context, rng, engine) -> None:
        if self.triggered:
            return
        if not state.is_entered(dango.id):
            return
        my_distance = engine.forward_distance_to_start(state.position_of(dango.id))
        for other_id in engine.normal_ids():
            if other_id == dango.id or not state.is_entered(other_id):
                continue
            if engine.forward_distance_to_start(state.position_of(other_id)) > my_distance:
                return
        self.triggered = True

    def before_move(self, dango: Dango, state: RaceState, context, rng) -> None:
        if self.triggered and rng.random() < self.chance:
            context.movement += self.bonus
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_skills.py -k "cartethyia" -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/dango_sim/skills.py tests/test_skills.py
git commit -m "feat: add CartethyiaSkill — last-place pursuit mode"
```

---

### Task 3: Update participant roster

**Files:**
- Modify: `src/dango_sim/sample_config.py`

- [ ] **Step 1: Update imports and participants**

Replace the imports in `sample_config.py` to add `HiyukiSkill` and `CartethyiaSkill`, and update the `participants` list:

```python
from dango_sim.skills import (
    AugustaSkill,
    CalcharoSkill,
    CartethyiaSkill,
    HiyukiSkill,
    IunoSkill,
    JinhsiSkill,
)
```

Replace the `participants` list with:

```python
participants=[
    Dango(id="augusta", name="奥古斯塔团子", skill=AugustaSkill()),
    Dango(id="jinhsi", name="今汐团子", skill=JinhsiSkill()),
    Dango(id="hiyuki", name="绯雪团子", skill=HiyukiSkill()),
    Dango(id="iuno", name="尤诺团子", skill=IunoSkill()),
    Dango(id="calcharo", name="卡卡罗团子", skill=CalcharoSkill()),
    Dango(id="cartethyia", name="卡提希娅团子", skill=CartethyiaSkill()),
],
```

Remove unused imports (`AemeathSkill`, `CarlottaSkill`, `ChangliSkill`, `ChisaSkill`, `LuukHerssenSkill`, `LynaeSkill`, `MornyeSkill`, `PhoebeSkill`, `PhrolovaSkill`, `ShorekeeperSkill`).

- [ ] **Step 2: Run full test suite**

Run: `pytest -v`
Expected: All existing tests PASS (sample_config tests may need verification)

- [ ] **Step 3: Commit**

```bash
git add src/dango_sim/sample_config.py
git commit -m "feat: update participant roster to new six-dango lineup"
```

---

### Task 4: Add viewer colors

**Files:**
- Modify: `viewer/src/colors.ts`

- [ ] **Step 1: Add color entries**

Add two entries to `DANGO_COLORS` in `viewer/src/colors.ts`, after the existing `calcharo` entry:

```typescript
  hiyuki: '#b3e0ff',
  cartethyia: '#4a5568',
```

- [ ] **Step 2: Commit**

```bash
git add viewer/src/colors.ts
git commit -m "feat: add viewer colors for Hiyuki and Cartethyia"
```
