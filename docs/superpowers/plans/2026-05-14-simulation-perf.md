# Simulation Performance Optimization — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce wall-clock time for a 1000-run Monte Carlo simulation by 8-20x without changing semantics or public API.

**Architecture:** Four independent optimizations applied in dependency order: (1) O(1) position lookups via a reverse index on RaceState, (2) pre-computed hook dispatch tables to skip non-matching participants, (3) rankings cache invalidated on movement, (4) ProcessPoolExecutor-based parallel simulation runs. All changes are internal — public API signatures are unchanged.

**Tech Stack:** Python 3.12+, stdlib only (`concurrent.futures`), `pytest` for testing.

---

## File Structure

| File | Responsibility | Change type |
|---|---|---|
| `src/dango_sim/models.py` | Position index on `RaceState`, optimized `remove_ids` | Modify |
| `src/dango_sim/engine.py` | Hook dispatch tables, rankings cache | Modify |
| `src/dango_sim/simulation.py` | Parallel execution via `ProcessPoolExecutor` | Modify |
| `tests/test_engine.py` | Unchanged — validates correctness | — |
| `tests/test_skills.py` | Unchanged — validates correctness | — |

---

## Task 1: Position Index on RaceState

**Files:**
- Modify: `src/dango_sim/models.py` (entire `RaceState` class)

**Why first:** `position_of()` is the single most-called method (~720k calls per 1000-run batch). The index also enables the optimized `remove_ids` and feeds into every other optimization.

### Design

Add `_pos_index: dict[str, int]` to `RaceState`. Maintain it in all mutation methods. Use a lazy fallback in `position_of` for the rare case where tests assign `positions` directly.

- [ ] **Step 1: Run tests to verify baseline**

Run: `pytest tests/ -v`
Expected: All tests pass.

- [ ] **Step 2: Add `_pos_index` field and `__post_init__` to `RaceState`**

In `src/dango_sim/models.py`, add after the `laps_completed` field (line 131) and add `__post_init__` + `_rebuild_index`:

```python
@dataclass
class RaceState:
    positions: dict[int, list[str]]
    round_number: int = 0
    finished_group: list[str] | None = None
    finished_position: int | None = None
    laps_completed: dict[str, int] = field(default_factory=dict)
    _pos_index: dict[str, int] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self._rebuild_index()

    def _rebuild_index(self) -> None:
        self._pos_index = {}
        for position, stack in self.positions.items():
            for dango_id in stack:
                self._pos_index[dango_id] = position
```

- [ ] **Step 3: Update `position_of` to use index with fallback**

Replace the existing `position_of` method:

```python
def position_of(self, dango_id: str) -> int:
    pos = self._pos_index.get(dango_id)
    if pos is not None:
        stack = self.positions.get(pos)
        if stack is not None and dango_id in stack:
            return pos
    for position, stack in self.positions.items():
        if dango_id in stack:
            self._pos_index[dango_id] = position
            return position
    raise KeyError(dango_id)
```

- [ ] **Step 4: Update `is_entered` to use index**

Replace the existing `is_entered` method:

```python
def is_entered(self, dango_id: str) -> bool:
    pos = self._pos_index.get(dango_id)
    if pos is not None:
        return pos in self.positions and dango_id in self.positions[pos]
    return False
```

- [ ] **Step 5: Update `place_group` to maintain index**

Replace the existing `place_group` method:

```python
def place_group(self, group: list[str], position: int, *, bottom: bool = False) -> None:
    existing = self.positions.setdefault(position, [])
    if bottom:
        self.positions[position] = list(group) + existing
    else:
        existing.extend(group)
    for dango_id in group:
        self._pos_index[dango_id] = position
```

- [ ] **Step 6: Update `remove_ids` to use index for targeted removal**

Replace the existing `remove_ids` method:

```python
def remove_ids(self, dango_ids: list[str]) -> None:
    to_remove = set(dango_ids)
    affected: set[int] = set()
    for dango_id in to_remove:
        pos = self._pos_index.get(dango_id)
        if pos is not None:
            affected.add(pos)
    empty_positions: list[int] = []
    for position in affected:
        self.positions[position] = [
            dango_id for dango_id in self.positions[position] if dango_id not in to_remove
        ]
        if not self.positions[position]:
            empty_positions.append(position)
    for position in empty_positions:
        del self.positions[position]
    for dango_id in to_remove:
        self._pos_index.pop(dango_id, None)
```

- [ ] **Step 7: Update `lift_group_from` to maintain index**

Replace the existing `lift_group_from` method:

```python
def lift_group_from(self, dango_id: str) -> list[str]:
    position = self.position_of(dango_id)
    stack = self.positions[position]
    index = stack.index(dango_id)
    group = stack[index:]
    self.positions[position] = stack[:index]
    if not self.positions[position]:
        del self.positions[position]
    for gid in group:
        self._pos_index.pop(gid, None)
    return group
```

- [ ] **Step 8: Update `enter_at_start` to maintain index**

Replace the existing `enter_at_start` method:

```python
def enter_at_start(self, dango_id: str) -> None:
    if self.is_entered(dango_id):
        return
    self.place_group([dango_id], 0)
    self.laps_completed.setdefault(dango_id, 0)
```

- [ ] **Step 9: Run tests to verify no regressions**

Run: `pytest tests/ -v`
Expected: All tests pass.

- [ ] **Step 10: Commit**

```bash
git add src/dango_sim/models.py
git commit -m "perf: add position index to RaceState for O(1) lookups"
```

---

## Task 2: Hook Dispatch Table on RaceEngine

**Files:**
- Modify: `src/dango_sim/engine.py`

**Why:** Eliminates iterating all participants + `hasattr` checks on every broadcast hook call. Pre-compute once at init which participants implement each hook.

### Design

Build three lists at init time — one per broadcast hook (`on_round_start`, `after_group_stacked`, `after_any_move`). Replace the `for dango in self.participants: if hasattr(...)` loops with `for dango in self._on_round_start_hooks:`.

- [ ] **Step 1: Add dispatch table fields in `RaceEngine.__init__`**

In `src/dango_sim/engine.py`, add after line 46 (after the Bu King placement block):

```python
        # Pre-computed hook dispatch tables
        self._on_round_start_hooks = [
            d for d in self.participants
            if d.skill and hasattr(d.skill, "on_round_start")
        ]
        self._after_group_stacked_hooks = [
            d for d in self.participants
            if d.skill and hasattr(d.skill, "after_group_stacked")
        ]
        self._after_any_move_hooks = [
            d for d in self.participants
            if d.skill and hasattr(d.skill, "after_any_move")
        ]
```

- [ ] **Step 2: Replace `start_round` dispatch loop**

In `src/dango_sim/engine.py`, replace lines 99-101:

```python
        # Before:
        # for dango in self.participants:
        #     if dango.skill and hasattr(dango.skill, "on_round_start"):
        #         dango.skill.on_round_start(dango, self.state, self, self.rng)

        # After:
        for dango in self._on_round_start_hooks:
            dango.skill.on_round_start(dango, self.state, self, self.rng)
```

- [ ] **Step 3: Replace `after_group_stacked` dispatch loop**

In `src/dango_sim/engine.py`, replace lines 310-318:

```python
        # Before:
        # for dango in self.participants:
        #     if dango.skill and hasattr(dango.skill, "after_group_stacked"):
        #         dango.skill.after_group_stacked(dango, self.state, context, self.rng, self)

        # After:
        for dango in self._after_group_stacked_hooks:
            dango.skill.after_group_stacked(dango, self.state, context, self.rng, self)
```

- [ ] **Step 4: Replace `after_any_move` dispatch loop**

In `src/dango_sim/engine.py`, replace lines 333-335:

```python
        # Before:
        # for dango in self.participants:
        #     if dango.skill and hasattr(dango.skill, "after_any_move"):
        #         dango.skill.after_any_move(dango, self.state, context, self.rng, self)

        # After:
        for dango in self._after_any_move_hooks:
            dango.skill.after_any_move(dango, self.state, context, self.rng, self)
```

- [ ] **Step 5: Run tests to verify no regressions**

Run: `pytest tests/ -v`
Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/dango_sim/engine.py
git commit -m "perf: pre-compute hook dispatch tables to skip non-matching participants"
```

---

## Task 3: Rankings Cache on RaceEngine

**Files:**
- Modify: `src/dango_sim/engine.py`

**Why:** `CalcharoSkill.before_move()` calls `engine.rankings()` on every turn. `IunoSkill` calls `rankings_with_specials()`. Rankings involve sorting + multiple list comprehensions. Cache them per round and invalidate on movement.

### Design

Add two cache fields (`_rankings_cache`, `_rankings_specials_cache`). Set to `None` on init and on any movement. Compute on first access.

- [ ] **Step 1: Add cache fields and invalidation method**

In `src/dango_sim/engine.py`, add to `__init__` after the dispatch table fields from Task 2:

```python
        self._rankings_cache: list[str] | None = None
        self._rankings_specials_cache: list[str] | None = None
```

Add a new method to the class:

```python
    def _invalidate_rankings_cache(self) -> None:
        self._rankings_cache = None
        self._rankings_specials_cache = None
```

- [ ] **Step 2: Wire invalidation into movement methods**

Add `self._invalidate_rankings_cache()` call at the start of these three methods:

In `move_group_to` (line 280), as the first line of the method body:

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
        self._invalidate_rankings_cache()
        destination = self.normalize_position(destination)
        ...
```

In `finish_group_at_start` (line 512), as the first line of the method body:

```python
    def finish_group_at_start(self, group: list[str]) -> None:
        self._invalidate_rankings_cache()
        normal_ids = set(self.normal_ids())
        ...
```

In `take_bu_king_turn` (line 342), as the first line after the early-return guard:

```python
    def take_bu_king_turn(self, base_roll: int | None = None) -> None:
        if not self.config.include_bu_king or self.state.round_number < 3:
            return
        self._invalidate_rankings_cache()
        ...
```

- [ ] **Step 3: Update `rankings()` to use cache**

Replace the existing `rankings` method:

```python
    def rankings(self) -> list[str]:
        if self._rankings_cache is None:
            self._rankings_cache = self._rankings(include_specials=False)
        return self._rankings_cache
```

Replace the existing `rankings_with_specials` method:

```python
    def rankings_with_specials(self) -> list[str]:
        if self._rankings_specials_cache is None:
            self._rankings_specials_cache = self._rankings(include_specials=True)
        return self._rankings_specials_cache
```

- [ ] **Step 4: Run tests to verify no regressions**

Run: `pytest tests/ -v`
Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/dango_sim/engine.py
git commit -m "perf: cache rankings, invalidate on movement only"
```

---

## Task 4: Parallel Simulations

**Files:**
- Modify: `src/dango_sim/simulation.py`

**Why:** Each simulation run is completely independent — embarrassingly parallel. ProcessPoolExecutor distributes across CPU cores for near-linear speedup.

### Design

Pre-generate all configs and seeds in the main process, then distribute to workers. `max_workers=None` (default) = sequential, any positive int = parallel with that many workers. The aggregation loop is the same regardless of execution mode.

- [ ] **Step 1: Add top-level worker function and import**

In `src/dango_sim/simulation.py`, add the import at the top and a module-level function before `run_simulations`:

```python
from __future__ import annotations

import random
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Callable, Iterable, Mapping

from dango_sim.engine import RaceEngine
from dango_sim.models import RaceConfig


def _run_single(args: tuple) -> object:
    config, seed, engine_cls = args
    return engine_cls(config, random.Random(seed)).run()
```

- [ ] **Step 2: Rewrite `run_simulations` with parallel support**

Replace the entire `run_simulations` function:

```python
def run_simulations(
    *,
    config_factory: Callable[[], RaceConfig],
    runs: int,
    seed: int | None = None,
    engine_cls=RaceEngine,
    max_workers: int | None = None,
    top_n: Iterable[int] = (),
) -> SimulationSummary:
    if runs <= 0:
        raise ValueError("runs must be positive")

    master_rng = random.Random(seed)
    top_n_values = sorted({int(value) for value in top_n})
    if any(value <= 0 for value in top_n_values):
        raise ValueError("top_n values must be positive")

    configs = [config_factory() for _ in range(runs)]
    seeds = [master_rng.randrange(2**63) for _ in range(runs)]

    if max_workers is not None and max_workers > 1:
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(
                _run_single,
                [(c, s, engine_cls) for c, s in zip(configs, seeds)],
            ))
    else:
        results = [
            engine_cls(config, random.Random(seed)).run()
            for config, seed in zip(configs, seeds)
        ]

    wins: dict[str, int] = {}
    rank_totals: dict[str, int] = {}
    rank_counts: dict[str, int] = {}
    total_rounds = 0
    top_n_counts: dict[int, dict[str, int]] = {
        value: {} for value in top_n_values
    }

    for result in results:
        wins[result.winner_id] = wins.get(result.winner_id, 0) + 1
        total_rounds += result.rounds

        for rank, dango_id in enumerate(result.rankings, start=1):
            wins.setdefault(dango_id, 0)
            rank_totals[dango_id] = rank_totals.get(dango_id, 0) + rank
            rank_counts[dango_id] = rank_counts.get(dango_id, 0) + 1

        for n in top_n_values:
            for dango_id in result.rankings[:n]:
                top_n_counts[n][dango_id] = top_n_counts[n].get(dango_id, 0) + 1
            for dango_id in result.rankings:
                top_n_counts[n].setdefault(dango_id, 0)

    win_rates = {dango_id: count / runs for dango_id, count in wins.items()}
    average_rank = {
        dango_id: rank_totals[dango_id] / rank_counts[dango_id]
        for dango_id in rank_totals
    }
    top_n_rates = {
        n: {
            dango_id: count / runs
            for dango_id, count in counts.items()
        }
        for n, counts in top_n_counts.items()
    }

    return SimulationSummary(
        runs=runs,
        wins=wins,
        win_rates=win_rates,
        average_rank=average_rank,
        average_rounds=total_rounds / runs,
        top_n_rates=top_n_rates,
    )
```

- [ ] **Step 3: Run tests to verify no regressions**

Run: `pytest tests/ -v`
Expected: All tests pass. The default `max_workers=None` uses the sequential path, so existing behavior is identical.

- [ ] **Step 4: Verify determinism**

Run a quick check that seeds produce identical results:

```python
from dango_sim import run_simulations, Dango, RaceConfig, Board

def factory():
    return RaceConfig(
        board=Board(finish=10),
        participants=[
            Dango(id="a", name="A"),
            Dango(id="b", name="B"),
            Dango(id="c", name="C"),
        ],
        include_bu_king=False,
    )

seq = run_simulations(config_factory=factory, runs=100, seed=42)
par = run_simulations(config_factory=factory, runs=100, seed=42, max_workers=4)

assert seq.win_rates == par.win_rates
assert seq.average_rank == par.average_rank
assert seq.average_rounds == par.average_rounds
```

Expected: No assertion errors. Results are identical.

- [ ] **Step 5: Commit**

```bash
git add src/dango_sim/simulation.py
git commit -m "perf: add ProcessPoolExecutor parallel execution to run_simulations"
```

---

## Task 5: Full Verification & Benchmark

**Files:**
- No code changes — verification only

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests pass.

- [ ] **Step 2: Run determinism verification**

```bash
python -c "
from dango_sim import run_simulations, Dango, RaceConfig, Board

def factory():
    return RaceConfig(
        board=Board(finish=10),
        participants=[
            Dango(id='a', name='A'),
            Dango(id='b', name='B'),
            Dango(id='c', name='C'),
        ],
        include_bu_king=False,
    )

baseline = run_simulations(config_factory=factory, runs=200, seed=99)
current = run_simulations(config_factory=factory, runs=200, seed=99)
assert baseline.win_rates == current.win_rates, f'win_rates differ: {baseline.win_rates} vs {current.win_rates}'
assert baseline.average_rank == current.average_rank, f'avg_rank differs'
assert baseline.average_rounds == current.average_rounds, f'avg_rounds differs'
print('Determinism check PASSED')
"
```

Expected: `Determinism check PASSED`

- [ ] **Step 3: Run benchmark**

```bash
python -c "
import time
from dango_sim import run_simulations, Dango, RaceConfig, Board

def factory():
    return RaceConfig(
        board=Board(finish=10),
        participants=[
            Dango(id='a', name='A'),
            Dango(id='b', name='B'),
            Dango(id='c', name='C'),
            Dango(id='d', name='D'),
            Dango(id='e', name='E'),
            Dango(id='f', name='F'),
        ],
        include_bu_king=False,
    )

start = time.perf_counter()
run_simulations(config_factory=factory, runs=1000, seed=42)
elapsed = time.perf_counter() - start
print(f'1000 runs (sequential): {elapsed:.2f}s')

start = time.perf_counter()
run_simulations(config_factory=factory, runs=1000, seed=42, max_workers=4)
elapsed_par = time.perf_counter() - start
print(f'1000 runs (4 workers):  {elapsed_par:.2f}s')
print(f'Speedup: {elapsed / elapsed_par:.1f}x')
"
```

Expected: Sequential time should be measurably faster than pre-optimization baseline. Parallel time should show ~3-4x additional speedup.

- [ ] **Step 4: Final commit (if any fixups needed)**

If any issues were found and fixed during verification, commit them:

```bash
git add -A
git commit -m "fix: address verification issues from performance optimization"
```

---

## Self-Review

### 1. Spec Coverage

| Spec optimization | Plan task | Status |
|---|---|---|
| Position index | Task 1 | Covered |
| Hook dispatch table | Task 2 | Covered |
| Rankings cache | Task 3 | Covered |
| Parallel simulations | Task 4 | Covered |
| Eliminate deepcopy | — | **Dropped** — marginal (1.1x), adds risk for stateful skill isolation |
| Micro-optimizations (remove_ids) | Task 1 (Step 6) | Covered (index-based removal) |
| Micro-optimizations (stack_at, forward_path) | — | **Dropped** — stack_at defensive copy prevents subtle bugs; forward_path list needed for context.path |

### 2. Placeholder Scan

No TBD, TODO, "implement later", "add validation", or "similar to Task N" patterns found.

### 3. Type Consistency

- `_pos_index: dict[str, int]` — used consistently across all methods
- `_on_round_start_hooks: list[Dango]` — `Dango` type from models.py, consistent with `self.participants` type
- `_rankings_cache: list[str] | None` — matches return type of `_rankings() -> list[str]`
- `_run_single(args: tuple)` — receives `(RaceConfig, int, type)` tuple, consistent with construction in Task 4 Step 2
