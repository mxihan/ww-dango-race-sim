# Denia & Sigrika — Two New Dango Skills + Engine Changes

## Overview

Add two new characters (Denia, Sigrika) and three engine-level changes: random-shuffle turn order, position-1 default start, and a cross-dango penalty mechanism.

## New Characters

### 达妮娅 — Denia

**Ability**: When Denia's raw dice roll matches her previous raw dice roll, she gains +2 extra movement. First round never triggers (no previous roll to compare against).

**Hook**: `modify_roll`

- Compare current `roll` against `self.last_roll`
- If match: return `roll + 2`
- Always update `self.last_roll = roll` (stores raw value, before bonus)

**Skill class**:

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

**Ranking dependency**: None.

### 西格莉卡 — Sigrika

**Ability**: At the start of each round, Sigrika marks up to 2 dangos ranked immediately above her in the global position-based ranking. Marked dangos get -1 movement applied after their own `before_move` hook, with minimum effective movement of 1.

**Marking rules**:
- Ranking is `engine.rankings()` (normal dangos only, Bu King excluded)
- If Sigrika is ranked Nth, she marks positions N-1 and N-2 (two immediate neighbors above)
- If Sigrika is 1st, no targets exist — marks nobody
- If Sigrika is 2nd, only 1 target (the 1st-place dango)
- `max_targets` caps the number of marks (default 2)

**Penalty application** (in `take_turn`, after `before_move`):
- Engine checks `round_penalties[dango_id]`
- `context.movement = max(1, context.movement - penalty)`
- This runs after the dango's own skill hooks, so Sigrika's penalty always applies regardless of other movement bonuses

**Hook**: `on_round_start`

**Skill class**:

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

**Ranking dependency**: Position-based ranking via `engine.rankings()`.

## Engine Changes

### 1. Random-Shuffle Turn Order

**Current**: `build_round_order` rolls dice for each actor via `roll_order_values`, sorts by roll value, shuffles ties. Dice skills (MornyeSkill `roll`, ShorekeeperSkill `roll_faces`) can affect order rolls.

**New**: `build_round_order` randomly shuffles the actor list. No dice rolling for order determination. Dice skills still affect movement rolls — only ordering is decoupled from dice.

**Implementation**: Replace the roll+sort logic in `build_round_order` with `self.rng.shuffle(shuffled)`. Keep `apply_forced_last` for skills that reorder (Augusta, Changli). Bu King is included in the shuffle like any other actor.

**Dead code**: `roll_order_values`, `order_actors`, `roll_for_order`, and `roll_bu_king_order` become unused and can be removed.

### 2. Default Starting Position: Tile 1

**Current**: When no `starting_state` is provided, `apply_default_opening_stack` places all normal dangos at position 0. Stack order: first to act is at the top (ranked first).

**New**: Place at position 1 instead of position 0.

**Implementation**: Change `self.state.place_group(stack, 0)` to `self.state.place_group(stack, 1)` in `apply_default_opening_stack`.

**Bu King**: Remains at position 0 (`bottom=True`). This is unchanged.

**Stack order**: Unchanged — first to act is at the top.

### 3. Cross-Dango Penalty Mechanism

**New engine state**: `self.round_penalties: dict[str, int]` — maps dango ID to movement penalty for the current round.

**Lifecycle**:
- Cleared at the start of each round in `start_round`
- Skills register penalties via `engine.round_penalties[target_id] += amount`
- Applied in `take_turn` after the dango's own `before_move` hook

**Application in `take_turn`**:
```python
penalty = self.round_penalties.get(dango_id, 0)
if penalty:
    context.movement = max(1, context.movement - penalty)
```

**Floor guarantee**: `max(1, ...)` ensures movement never drops to 0 or below.

## Participant Roster Update

Add Denia and Sigrika to `sample_config.py` (8 total):

1. 奥古斯塔 (`augusta`) — `AugustaSkill`
2. 今汐 (`jinhsi`) — `JinhsiSkill`
3. 绯雪 (`hiyuki`) — `HiyukiSkill`
4. 尤诺 (`iuno`) — `IunoSkill`
5. 卡卡罗 (`calcharo`) — `CalcharoSkill`
6. 卡提希娅 (`cartethyia`) — `CartethyiaSkill`
7. 达妮娅 (`denia`) — `DeniaSkill` **(new)**
8. 西格莉卡 (`sigrika`) — `SigrikaSkill` **(new)**

## Files to Modify

| File | Change |
|---|---|
| `src/dango_sim/skills.py` | Add `DeniaSkill`, `SigrikaSkill` dataclasses |
| `src/dango_sim/engine.py` | Add `round_penalties`; shuffle-based `build_round_order`; penalty application in `take_turn`; position-1 default start; clear penalties in `start_round`; remove `roll_order_values`/`order_actors` |
| `src/dango_sim/sample_config.py` | Add Denia and Sigrika to participants |
| `tests/test_skills.py` | Add unit and integration tests for both skills |

## Test Coverage

### Denia tests

- First roll never triggers (last_roll is None)
- Matching previous roll → +2 bonus
- Non-matching roll → no bonus, last_roll updated
- Multiple consecutive matches → bonus each time
- Different dice faces (1, 2, 3) all work for matching

### Sigrika tests

- Ranked 4th → marks 3rd and 2nd place, they get -1 movement
- Ranked 1st → no targets marked
- Ranked 2nd → only 1 target marked
- Marked dango with movement 1 → stays at 1 (floor)
- Marked dango with movement 3 → reduced to 2
- Penalty applied after target's own before_move skill
- Multiple rounds: penalties reset each round

### Engine change tests

- Turn order is random shuffle, not dice-based
- No two consecutive rounds have identical order (statistical check)
- Default starting position is tile 1, not tile 0
- Bu King still starts at position 0
- Stack order preserved (first to act at top)
