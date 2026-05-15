# Hiyuki & Cartethyia — Two New Dango Skills

## Overview

Add two new characters to the dango race simulation and update the default participant roster to six characters.

## New Characters

### 绯雪 — Hiyuki

**Ability**: After encountering Bu King, every own-turn move gains +1 extra movement for the rest of the race.

**Encounter condition** (any one suffices):
- Hiyuki's movement path passes through Bu King's position (checked in `after_move` via `context.path`)
- Hiyuki ends up at the same position as Bu King (checked in `after_move` and `after_any_move`)

**Encounter is permanent**: once `encountered_bu_king` is set to `True`, it stays `True` for the remainder of the race.

**Hooks**:

| Hook | Purpose |
|---|---|
| `after_move` | Detect encounter via path overlap or shared destination with Bu King on Hiyuki's own turn |
| `after_any_move` | Detect encounter via shared position after any movement event (Bu King carrying, tile effects, etc.) |
| `before_move` | If `encountered_bu_king`, add +1 to `context.movement` (own turn only) |

**Skill class**:

```python
@dataclass
class HiyukiSkill:
    encountered_bu_king: bool = False
```

**Ranking check**: Not applicable — no ranking dependency.

### 卡提希娅 — Cartethyia

**Ability**: Once per race, after Cartethyia's own move, if she is ranked last among normal dangos (excluding Bu King), she enters pursuit mode. For the rest of the race, every own-turn move has a 60% chance to gain +2 extra movement.

**Trigger condition** (checked in `after_move`, own turn only):
- `triggered` is `False`
- Cartethyia is ranked last among all normal participants (excluding `bu_king`)
- Ranking is determined by `state.positions` — highest position value = furthest ahead; lowest = last

**Trigger is deterministic**: the check always runs; only the per-turn bonus is probabilistic.

**Effect** (applied in `before_move`, own turn only):
- If `triggered` is `True`: `rng.random() < 0.6` → `context.movement += 2`

**Hooks**:

| Hook | Purpose |
|---|---|
| `after_move` | Check if Cartethyia is last among normal dangos; set `triggered = True` if so |
| `before_move` | If `triggered`, 60% chance to add +2 to `context.movement` |

**Skill class**:

```python
@dataclass
class CartethyiaSkill:
    triggered: bool = False
```

## Participant Roster Update

Replace `sample_config.py` participants with:

1. 奥古斯塔 (`augusta`) — `AugustaSkill`
2. 今汐 (`jinhsi`) — `JinhsiSkill`
3. 绯雪 (`hiyuki`) — `HiyukiSkill` **(new)**
4. 尤诺 (`iuno`) — `IunoSkill`
5. 卡卡罗 (`calcharo`) — `CalcharoSkill`
6. 卡提希娅 (`cartethyia`) — `CartethyiaSkill` **(new)**

## Viewer Colors

Add to `viewer/src/colors.ts`:

- `hiyuki`: `'#b3e0ff'` (ice blue — matches snow imagery)
- `cartethyia`: `'#4a5568'` (slate blue-gray — matches pursuit/shadow theme)

## Files to Modify

| File | Change |
|---|---|
| `src/dango_sim/skills.py` | Add `HiyukiSkill`, `CartethyiaSkill` dataclasses |
| `src/dango_sim/sample_config.py` | Update participants list to the six characters above |
| `viewer/src/colors.ts` | Add two color entries |
| `tests/test_skills.py` | Add unit and integration tests for both skills |

## Test Coverage

### Hiyuki tests

- Path passes through Bu King → `encountered_bu_king` becomes `True`, next move gets +1
- Hiyuki lands on Bu King's position → encounter detected
- Bu King carries Hiyuki (passive same position via `after_any_move`) → encounter detected
- No encounter → no bonus
- Bonus persists across multiple rounds after encounter

### Cartethyia tests

- Last place after own move → `triggered` becomes `True`
- Not last place → `triggered` stays `False`
- Triggered + lucky roll (rng < 0.6) → +2 movement
- Triggered + unlucky roll (rng >= 0.6) → no bonus
- Only triggers once per race (no double trigger)
- Bu King excluded from ranking comparison
