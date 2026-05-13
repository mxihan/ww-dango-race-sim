# Race Trace & Rich Statistics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in event trace system and lightweight aggregate statistics (skill trigger rates, position heatmaps) to the dango race simulator.

**Architecture:** Engine-level listener protocol with two composable consumers. TraceRecorder captures full event histories with state snapshots for individual race inspection. StatsCollector accumulates skill trigger counts and position frequencies with negligible overhead for any run count.

**Tech Stack:** Python stdlib only (dataclasses, copy, collections). No new dependencies.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `src/dango_sim/listener.py` | Create | TraceEvent, RaceTrace, TraceRecorder, StatsCollector, SimulationStats, `_snapshot` helper |
| `src/dango_sim/engine.py` | Modify | Add `listeners` param, `_emit` method, emit calls at engine event points |
| `src/dango_sim/simulation.py` | Modify | Add `stats`/`trace`/`trace_limit` params, aggregate stats into SimulationSummary |
| `src/dango_sim/__init__.py` | Modify | Export new public types |
| `main.py` | Modify | Add `--no-stats` and `--trace` CLI flags, print stats |
| `tests/test_listener.py` | Create | Tests for listener dispatch, TraceRecorder, StatsCollector, simulation integration |

---

### Task 1: Engine Listener System

**Files:**
- Modify: `src/dango_sim/engine.py`
- Test: `tests/test_listener.py`

This task adds the listener infrastructure to the engine. No consumers yet — just the protocol and emit points.

- [ ] **Step 1: Write tests for engine listener dispatch**

```python
# tests/test_listener.py
from __future__ import annotations

import random

from dango_sim.engine import RaceEngine
from dango_sim.models import Board, Dango, RaceConfig


class _SpyListener:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    def on_move(self, **kw):
        self.calls.append(("move", kw))

    def on_tile(self, **kw):
        self.calls.append(("tile", kw))

    def on_skill(self, **kw):
        self.calls.append(("skill", kw))

    def on_finish(self, **kw):
        self.calls.append(("finish", kw))

    def on_bu_king(self, **kw):
        self.calls.append(("bu_king", kw))


def _engine_with_spy(**config_kwargs) -> tuple[RaceEngine, _SpyListener]:
    spy = _SpyListener()
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
        include_bu_king=False,
        **config_kwargs,
    )
    engine = RaceEngine(config, random.Random(0), listeners=[spy])
    return engine, spy


def test_engine_emits_move_on_normal_turn():
    engine, spy = _engine_with_spy()
    engine.run()
    move_events = [c for c in spy.calls if c[0] == "move"]
    assert len(move_events) >= 1
    event = move_events[0][1]
    assert event["dango_id"] in ("a", "b")
    assert "from_pos" in event
    assert "to_pos" in event
    assert "group" in event
    assert "path" in event
    assert "state" in event


def test_engine_emits_finish():
    engine, spy = _engine_with_spy()
    engine.run()
    finish_events = [c for c in spy.calls if c[0] == "finish"]
    assert len(finish_events) == 1
    assert len(finish_events[0][1]["group"]) >= 1


def test_engine_no_listeners_no_error():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="a", name="A")],
        include_bu_king=False,
    )
    engine = RaceEngine(config, random.Random(0))
    result = engine.run()
    assert result.winner_id == "a"


def test_engine_listener_ignores_missing_methods():
    """A listener without on_* methods should not cause errors."""
    class EmptyListener:
        pass
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="a", name="A")],
        include_bu_king=False,
    )
    engine = RaceEngine(config, random.Random(0), listeners=[EmptyListener()])
    result = engine.run()
    assert result.winner_id == "a"


def test_engine_multiple_listeners():
    spy1 = _SpyListener()
    spy2 = _SpyListener()
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="a", name="A")],
        include_bu_king=False,
    )
    engine = RaceEngine(config, random.Random(0), listeners=[spy1, spy2])
    engine.run()
    assert len(spy1.calls) > 0
    assert len(spy2.calls) > 0
    assert [c[0] for c in spy1.calls] == [c[0] for c in spy2.calls]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_listener.py -v`
Expected: FAIL — `_emit` not defined, `listeners` param not accepted

- [ ] **Step 3: Add listeners parameter and _emit method to engine**

In `src/dango_sim/engine.py`, modify `RaceEngine.__init__` signature (line 24):

```python
def __init__(self, config: RaceConfig, rng: random.Random | None = None, listeners: list[object] | None = None):
    config.validate()
    self.config = config
    self.rng = rng or random.Random()
    self._listeners: list[object] = list(listeners or [])
    self.participants = deepcopy(config.participants)
    # ... rest unchanged ...
```

Add `_emit` method after `_invalidate_rankings_cache` (after line 483):

```python
def _emit(self, event: str, **kwargs) -> None:
    for listener in self._listeners:
        handler = getattr(listener, f"on_{event}", None)
        if handler is not None:
            handler(**kwargs)
```

- [ ] **Step 4: Add _emit calls at engine event points**

**`start_round` (line 118)** — after each skill hook call in the loop:

```python
for dango in self._on_round_start_hooks:
    dango.skill.on_round_start(dango, self.state, self, self.rng)
    self._emit("skill", dango_id=dango.id, hook_name="on_round_start", state=self.state)
```

**`take_turn` (lines 261-295)** — after each skill hook call, and after movement:

After `on_turn_start` call (line 263, after the existing if block for skip_turns check):
```python
if dango.skill and hasattr(dango.skill, "on_turn_start"):
    dango.skill.on_turn_start(dango, self.state, context, self.rng, self)
    self._emit("skill", dango_id=dango_id, hook_name="on_turn_start", state=self.state)
    if dango_id in self.skip_turns_this_round:
        return
```

After `modify_roll` call (line 274):
```python
if dango.skill and hasattr(dango.skill, "modify_roll"):
    context.movement = int(
        dango.skill.modify_roll(
            dango, context.movement, self.state, context, self.rng,
        )
    )
    self._emit("skill", dango_id=dango_id, hook_name="modify_roll", state=self.state)
```

After `before_move` call (line 276):
```python
if dango.skill and hasattr(dango.skill, "before_move"):
    dango.skill.before_move(dango, self.state, context, self.rng)
    self._emit("skill", dango_id=dango_id, hook_name="before_move", state=self.state)
```

After `finish_group_at_start` call (line 289):
```python
if self.path_passes_start(path):
    self.finish_group_at_start(group)
    self._emit("finish", group=list(group), position=0, state=self.state)
    self.after_any_move(group, path, dango_id)
    return
```

After `move_group_to` call (line 292):
```python
self.move_group_to(group, path[-1], actor_id=dango_id, path=path)
self._emit("move", dango_id=dango_id, from_pos=source, to_pos=path[-1], group=list(group), path=list(path), state=self.state)
```

After `after_move` skill call (line 295):
```python
if dango.skill and hasattr(dango.skill, "after_move"):
    dango.skill.after_move(dango, self.state, context, self.rng, self)
    self._emit("skill", dango_id=dango_id, hook_name="after_move", state=self.state)
```

**`after_group_stacked` (line 329)** — after each dispatch table hook:

```python
for dango in self._after_group_stacked_hooks:
    dango.skill.after_group_stacked(dango, self.state, context, self.rng, self)
    self._emit("skill", dango_id=dango.id, hook_name="after_group_stacked", state=self.state)
```

**`after_any_move` (line 351)** — after each dispatch table hook:

```python
for dango in self._after_any_move_hooks:
    dango.skill.after_any_move(dango, self.state, context, self.rng, self)
    self._emit("skill", dango_id=dango.id, hook_name="after_any_move", state=self.state)
```

**`take_bu_king_turn` (line 387)** — after `after_any_move` call:

```python
self.after_any_move(final_group, path, BU_KING_ID)
self._emit("bu_king", roll=roll, path=list(path), state=self.state)
```

**`resolve_single_tile` (line 434)** — after `on_landed`, before `apply_tile_movement`:

```python
next_position = tile.on_landed(group, current, self.state, self.rng)
self._emit("tile", group=list(group), position=current, tile=tile, next_position=next_position, state=self.state)
self.apply_tile_movement(group, current, next_position)
```

**`resolve_chained_tiles` (line 444)** — after `on_landed`, before `apply_tile_movement`:

```python
next_position = tile.on_landed(group, current, self.state, self.rng)
self._emit("tile", group=list(group), position=current, tile=tile, next_position=next_position, state=self.state)
moved_position = self.apply_tile_movement(group, current, next_position)
```

- [ ] **Step 5: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All existing tests pass, new listener tests pass

- [ ] **Step 6: Commit**

```bash
git add src/dango_sim/engine.py tests/test_listener.py
git commit -m "feat: add listener protocol to RaceEngine for event observation"
```

---

### Task 2: TraceRecorder

**Files:**
- Create: `src/dango_sim/listener.py` (partial — TraceEvent, RaceTrace, TraceRecorder, `_snapshot`)
- Test: `tests/test_listener.py` (append tests)

- [ ] **Step 1: Write TraceRecorder tests**

Append to `tests/test_listener.py`:

```python
from dango_sim.listener import TraceEvent, TraceRecorder, RaceTrace


def test_trace_recorder_captures_move():
    engine = RaceEngine(
        RaceConfig(
            board=Board(finish=10),
            participants=[Dango(id="a", name="A")],
            include_bu_king=False,
        ),
        random.Random(0),
        listeners=[TraceRecorder()],
    )
    engine.run()
    recorder = engine._listeners[0]
    move_events = [e for e in recorder.events if e.kind == "move"]
    assert len(move_events) >= 1
    assert move_events[0].data["dango_id"] == "a"


def test_trace_event_has_state_snapshot():
    engine = RaceEngine(
        RaceConfig(
            board=Board(finish=10),
            participants=[Dango(id="a", name="A")],
            include_bu_king=False,
        ),
        random.Random(0),
        listeners=[TraceRecorder()],
    )
    engine.run()
    recorder = engine._listeners[0]
    assert len(recorder.events) > 0
    snap = recorder.events[0].state_snapshot
    assert "positions" in snap
    assert "laps_completed" in snap
    assert "round_number" in snap


def test_race_trace_freeze():
    events = [
        TraceEvent(kind="move", round_number=1, data={}, state_snapshot={}),
        TraceEvent(kind="finish", round_number=1, data={}, state_snapshot={}),
    ]
    trace = RaceTrace(events=tuple(events))
    assert len(trace.events) == 2


def test_trace_recorder_finish_event():
    engine = RaceEngine(
        RaceConfig(
            board=Board(finish=10),
            participants=[Dango(id="a", name="A")],
            include_bu_king=False,
        ),
        random.Random(0),
        listeners=[TraceRecorder()],
    )
    engine.run()
    recorder = engine._listeners[0]
    finish_events = [e for e in recorder.events if e.kind == "finish"]
    assert len(finish_events) == 1
    assert "a" in finish_events[0].data.get("group", finish_events[0].state_snapshot.get("positions", {}).get("0", []))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_listener.py::test_trace_recorder_captures_move -v`
Expected: FAIL — `dango_sim.listener` module not found

- [ ] **Step 3: Create `src/dango_sim/listener.py` with TraceEvent, RaceTrace, TraceRecorder**

```python
from __future__ import annotations

from dataclasses import dataclass, field

from dango_sim.models import RaceState


def _snapshot(state: RaceState) -> dict:
    return {
        "positions": {pos: list(stack) for pos, stack in state.positions.items()},
        "laps_completed": dict(state.laps_completed),
        "round_number": state.round_number,
    }


@dataclass(frozen=True)
class TraceEvent:
    kind: str
    round_number: int
    data: dict
    state_snapshot: dict


@dataclass(frozen=True)
class RaceTrace:
    events: tuple[TraceEvent, ...]


@dataclass
class TraceRecorder:
    events: list[TraceEvent] = field(default_factory=list)

    def on_move(self, *, dango_id, from_pos, to_pos, group, path, state, **_kw):
        self.events.append(TraceEvent(
            kind="move",
            round_number=state.round_number,
            data={"dango_id": dango_id, "from": from_pos, "to": to_pos, "group": list(group), "path": list(path)},
            state_snapshot=_snapshot(state),
        ))

    def on_tile(self, *, group, position, tile, next_position, state, **_kw):
        self.events.append(TraceEvent(
            kind="tile",
            round_number=state.round_number,
            data={"group": list(group), "position": position, "next_position": next_position, "tile": type(tile).__name__},
            state_snapshot=_snapshot(state),
        ))

    def on_skill(self, *, dango_id, hook_name, state, **_kw):
        self.events.append(TraceEvent(
            kind="skill",
            round_number=state.round_number,
            data={"dango_id": dango_id, "hook_name": hook_name},
            state_snapshot=_snapshot(state),
        ))

    def on_finish(self, *, group, position, state, **_kw):
        self.events.append(TraceEvent(
            kind="finish",
            round_number=state.round_number,
            data={"group": list(group), "position": position},
            state_snapshot=_snapshot(state),
        ))

    def on_bu_king(self, *, roll, path, state, **_kw):
        self.events.append(TraceEvent(
            kind="bu_king",
            round_number=state.round_number,
            data={"roll": roll, "path": list(path)},
            state_snapshot=_snapshot(state),
        ))

    def as_trace(self) -> RaceTrace:
        return RaceTrace(events=tuple(self.events))
```

- [ ] **Step 4: Run all tests**

Run: `python -m pytest tests/test_listener.py -v`
Expected: All TraceRecorder tests pass, all previous tests pass

- [ ] **Step 5: Commit**

```bash
git add src/dango_sim/listener.py tests/test_listener.py
git commit -m "feat: add TraceRecorder for full event capture during races"
```

---

### Task 3: StatsCollector and SimulationStats

**Files:**
- Modify: `src/dango_sim/listener.py` (append StatsCollector, SimulationStats)
- Test: `tests/test_listener.py` (append tests)

- [ ] **Step 1: Write StatsCollector tests**

Append to `tests/test_listener.py`:

```python
from dango_sim.listener import StatsCollector, SimulationStats


def test_stats_collector_skill_triggers():
    from dango_sim.models import RaceState
    state = RaceState(positions={0: ["a", "b"]}, laps_completed={"a": 0, "b": 0})
    state.round_number = 1
    collector = StatsCollector()
    collector.on_skill(dango_id="a", hook_name="modify_roll", state=state)
    collector.on_skill(dango_id="a", hook_name="modify_roll", state=state)
    collector.on_skill(dango_id="b", hook_name="before_move", state=state)
    assert collector.skill_triggers["a"]["modify_roll"] == 2
    assert collector.skill_triggers["b"]["before_move"] == 1


def test_stats_collector_position_heatmap():
    from dango_sim.models import RaceState
    state = RaceState(positions={0: ["a"], 5: ["b"]}, laps_completed={"a": 0, "b": 0})
    state.round_number = 1
    collector = StatsCollector()
    collector.on_move(dango_id="a", from_pos=0, to_pos=3, group=["a"], path=[1, 2, 3], state=state)
    collector.on_move(dango_id="b", from_pos=5, to_pos=7, group=["b"], path=[6, 7], state=state)
    state.round_number = 2
    collector.on_move(dango_id="a", from_pos=3, to_pos=5, group=["a"], path=[4, 5], state=state)
    assert collector.position_counts["a"][3] == 1
    assert collector.position_counts["a"][5] == 1
    assert collector.position_counts["b"][7] == 1


def test_stats_collector_records_once_per_round():
    """A dango should only be recorded once per round even with multiple moves."""
    from dango_sim.models import RaceState
    state = RaceState(positions={0: ["a"]}, laps_completed={"a": 0})
    state.round_number = 1
    collector = StatsCollector()
    collector.on_move(dango_id="a", from_pos=0, to_pos=3, group=["a"], path=[1, 2, 3], state=state)
    collector.on_move(dango_id="a", from_pos=3, to_pos=5, group=["a"], path=[4, 5], state=state)
    assert collector.position_counts["a"][3] == 1


def test_stats_collector_compute_heatmap():
    from dango_sim.models import RaceState
    state = RaceState(positions={0: ["a"]}, laps_completed={"a": 0})
    state.round_number = 1
    collector = StatsCollector()
    collector.on_move(dango_id="a", from_pos=0, to_pos=3, group=["a"], path=[1, 2, 3], state=state)
    state.round_number = 2
    collector.on_move(dango_id="a", from_pos=3, to_pos=5, group=["a"], path=[4, 5], state=state)
    heatmap = collector.compute_heatmap(total_rounds=2)
    assert abs(heatmap["a"][3] - 0.5) < 0.001
    assert abs(heatmap["a"][5] - 0.5) < 0.001


def test_stats_collector_finish_records_position():
    from dango_sim.models import RaceState
    state = RaceState(positions={0: ["a"]}, laps_completed={"a": 0})
    state.round_number = 5
    collector = StatsCollector()
    collector.on_finish(group=["a"], position=0, state=state)
    assert collector.position_counts["a"][0] == 1


def test_simulation_stats_immutable():
    stats = SimulationStats(
        skill_triggers={"a": {"modify_roll": 10}},
        position_heatmap={"a": {0: 0.5}},
    )
    assert stats.skill_triggers["a"]["modify_roll"] == 10
    assert stats.position_heatmap["a"][0] == 0.5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_listener.py::test_stats_collector_skill_triggers -v`
Expected: FAIL — `StatsCollector` not found

- [ ] **Step 3: Add StatsCollector and SimulationStats to `src/dango_sim/listener.py`**

Append to `src/dango_sim/listener.py`:

```python
from types import MappingProxyType
from typing import Mapping


@dataclass
class StatsCollector:
    skill_triggers: dict[str, dict[str, int]] = field(default_factory=dict)
    position_counts: dict[str, dict[int, int]] = field(default_factory=dict)
    _current_round: int = 0
    _recorded_this_round: set[str] = field(default_factory=set)

    def _ensure_dango(self, dango_id: str) -> None:
        if dango_id not in self.skill_triggers:
            self.skill_triggers[dango_id] = {}
        if dango_id not in self.position_counts:
            self.position_counts[dango_id] = {}

    def on_skill(self, *, dango_id, hook_name, state, **_kw):
        self._ensure_dango(dango_id)
        counts = self.skill_triggers[dango_id]
        counts[hook_name] = counts.get(hook_name, 0) + 1

    def on_move(self, *, dango_id, to_pos, group, state, **_kw):
        self._record_position(dango_id, to_pos, state)

    def on_finish(self, *, group, position, state, **_kw):
        for dango_id in group:
            self._record_position(dango_id, position, state)

    def on_bu_king(self, *, roll, path, state, **_kw):
        pass

    def on_tile(self, **_kw):
        pass

    def _record_position(self, dango_id: str, position: int, state: RaceState) -> None:
        if state.round_number != self._current_round:
            self._current_round = state.round_number
            self._recorded_this_round.clear()
        if dango_id not in self._recorded_this_round:
            self._ensure_dango(dango_id)
            counts = self.position_counts[dango_id]
            counts[position] = counts.get(position, 0) + 1
            self._recorded_this_round.add(dango_id)

    def compute_heatmap(self, total_rounds: int) -> dict[str, dict[int, float]]:
        return {
            dango_id: {pos: count / total_rounds for pos, count in positions.items()}
            for dango_id, positions in self.position_counts.items()
        }


@dataclass(frozen=True)
class SimulationStats:
    skill_triggers: Mapping[str, Mapping[str, int]]
    position_heatmap: Mapping[str, Mapping[int, float]]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "skill_triggers",
            MappingProxyType(
                {k: MappingProxyType(v) for k, v in self.skill_triggers.items()}
            ),
        )
        object.__setattr__(
            self,
            "position_heatmap",
            MappingProxyType(
                {k: MappingProxyType(v) for k, v in self.position_heatmap.items()}
            ),
        )
```

Add `Mapping` to imports at the top of `listener.py` — the `from types import MappingProxyType` and `from typing import Mapping` lines need to be added.

- [ ] **Step 4: Run all tests**

Run: `python -m pytest tests/test_listener.py -v`
Expected: All StatsCollector tests pass, all previous tests pass

- [ ] **Step 5: Commit**

```bash
git add src/dango_sim/listener.py tests/test_listener.py
git commit -m "feat: add StatsCollector and SimulationStats for aggregate race statistics"
```

---

### Task 4: Simulation Integration

**Files:**
- Modify: `src/dango_sim/simulation.py`
- Test: `tests/test_listener.py` (append tests), `tests/test_simulation.py` (append tests)

Wire `run_simulations` to create listeners, aggregate stats, and produce traces.

- [ ] **Step 1: Write simulation integration tests**

Append to `tests/test_simulation.py`:

```python
from dango_sim.listener import SimulationStats, TraceRecorder


def test_run_simulations_returns_stats_by_default():
    summary = run_simulations(
        config_factory=lambda: RaceConfig(
            board=Board(finish=10),
            participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
            include_bu_king=False,
        ),
        runs=5,
        seed=1,
    )
    assert summary.stats is not None
    assert isinstance(summary.stats, SimulationStats)
    assert len(summary.stats.skill_triggers) == 0  # no skills configured


def test_run_simulations_stats_disabled():
    summary = run_simulations(
        config_factory=lambda: RaceConfig(
            board=Board(finish=10),
            participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
            include_bu_king=False,
        ),
        runs=3,
        seed=1,
        stats=False,
    )
    assert summary.stats is None


def test_run_simulations_traces():
    summary = run_simulations(
        config_factory=lambda: RaceConfig(
            board=Board(finish=10),
            participants=[Dango(id="a", name="A")],
            include_bu_king=False,
        ),
        runs=3,
        seed=1,
        trace=True,
    )
    assert summary.traces is not None
    assert len(summary.traces) == 3
    for trace in summary.traces:
        assert len(trace.events) > 0


def test_run_simulations_trace_limit():
    summary = run_simulations(
        config_factory=lambda: RaceConfig(
            board=Board(finish=10),
            participants=[Dango(id="a", name="A")],
            include_bu_king=False,
        ),
        runs=10,
        seed=1,
        trace=True,
        trace_limit=2,
    )
    assert summary.traces is not None
    assert len(summary.traces) == 2


def test_run_simulations_stats_with_skills():
    from dango_sim.skills import CarlottaSkill
    summary = run_simulations(
        config_factory=lambda: RaceConfig(
            board=Board(finish=10),
            participants=[
                Dango(id="a", name="A", skill=CarlottaSkill()),
                Dango(id="b", name="B"),
            ],
            include_bu_king=False,
        ),
        runs=10,
        seed=1,
    )
    assert summary.stats is not None
    assert "a" in summary.stats.skill_triggers
    assert "modify_roll" in summary.stats.skill_triggers["a"]
    assert summary.stats.skill_triggers["a"]["modify_roll"] > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_simulation.py::test_run_simulations_returns_stats_by_default -v`
Expected: FAIL — `stats` parameter not accepted by `run_simulations`

- [ ] **Step 3: Modify `src/dango_sim/simulation.py`**

Add import at top:

```python
from dango_sim.listener import RaceTrace, StatsCollector, TraceRecorder, TraceEvent
```

Modify `run_simulations` signature:

```python
def run_simulations(
    *,
    config_factory: Callable[[], RaceConfig],
    runs: int,
    seed: int | None = None,
    engine_cls=RaceEngine,
    max_workers: int | None = None,
    top_n: Iterable[int] = (),
    stats: bool = True,
    trace: bool = False,
    trace_limit: int | None = None,
) -> SimulationSummary:
```

Modify `_run_single` to return result + stats data:

```python
def _run_single(args: tuple) -> object:
    config, seed, engine_cls, collect_stats = args
    listeners: list[object] = []
    collector = StatsCollector() if collect_stats else None
    if collector is not None:
        listeners.append(collector)
    engine = engine_cls(config, random.Random(seed), listeners=listeners or None)
    result = engine.run()
    stats_data = None
    if collector is not None:
        stats_data = {
            "skill_triggers": collector.skill_triggers,
            "position_counts": collector.position_counts,
        }
    return result, stats_data
```

Update the main execution paths in `run_simulations`. Replace the configs/seeds preparation and both execution paths:

```python
configs = [config_factory() for _ in range(runs)]
seeds = [master_rng.randrange(2**63) for _ in range(runs)]
collect_stats_flag = stats

if max_workers is not None and max_workers > 1:
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        raw_results = list(executor.map(
            _run_single,
            [(c, s, engine_cls, collect_stats_flag) for c, s in zip(configs, seeds)],
        ))
else:
    raw_results = [
        _run_single((c, s, engine_cls, collect_stats_flag))
        for c, s in zip(configs, seeds)
    ]

# Separate traces (sequential only, limited)
trace_results: list[RaceTrace] = []
if trace:
    limit = trace_limit if trace_limit is not None else runs
    for i in range(min(limit, runs)):
        recorder = TraceRecorder()
        engine = engine_cls(configs[i], random.Random(seeds[i]), listeners=[recorder])
        engine.run()
        trace_results.append(recorder.as_trace())

results = [r[0] for r in raw_results]
stats_datas = [r[1] for r in raw_results if r[1] is not None]
```

Add stats aggregation after the existing aggregation loop (after `total_rounds` computation):

```python
# Aggregate stats
sim_stats = None
if stats and stats_datas:
    agg_skill: dict[str, dict[str, int]] = {}
    agg_pos: dict[str, dict[int, int]] = {}
    for sd in stats_datas:
        for dango_id, hooks in sd["skill_triggers"].items():
            if dango_id not in agg_skill:
                agg_skill[dango_id] = {}
            for hook_name, count in hooks.items():
                agg_skill[dango_id][hook_name] = agg_skill[dango_id].get(hook_name, 0) + count
        for dango_id, positions in sd["position_counts"].items():
            if dango_id not in agg_pos:
                agg_pos[dango_id] = {}
            for pos, count in positions.items():
                agg_pos[dango_id][pos] = agg_pos[dango_id].get(pos, 0) + count

    from dango_sim.listener import SimulationStats
    total_rounds_count = int(total_rounds)
    heatmap = {
        dango_id: {pos: count / total_rounds_count for pos, count in positions.items()}
        for dango_id, positions in agg_pos.items()
    }
    sim_stats = SimulationStats(
        skill_triggers=agg_skill,
        position_heatmap=heatmap,
    )
```

Modify the return to include `stats` and `traces`:

```python
return SimulationSummary(
    runs=runs,
    wins=wins,
    win_rates=win_rates,
    average_rank=average_rank,
    average_rounds=total_rounds / runs,
    top_n_rates=top_n_rates,
    stats=sim_stats,
    traces=tuple(trace_results) if trace_results else None,
)
```

Modify `SimulationSummary` to add the two new fields:

```python
@dataclass(frozen=True)
class SimulationSummary:
    runs: int
    wins: Mapping[str, int]
    win_rates: Mapping[str, float]
    average_rank: Mapping[str, float]
    average_rounds: float
    top_n_rates: Mapping[int, Mapping[str, float]] = field(default_factory=dict)
    stats: SimulationStats | None = None
    traces: tuple[RaceTrace, ...] | None = None
```

Note: `SimulationStats` and `RaceTrace` need to be imported at the top of `simulation.py`. The `SimulationStats` import is used inside the function body to avoid circular imports; alternatively import at module level from `dango_sim.listener`.

- [ ] **Step 4: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add src/dango_sim/simulation.py tests/test_simulation.py
git commit -m "feat: integrate stats and trace collection into run_simulations"
```

---

### Task 5: CLI Flags and Package Exports

**Files:**
- Modify: `main.py`
- Modify: `src/dango_sim/__init__.py`

- [ ] **Step 1: Update `src/dango_sim/__init__.py` exports**

```python
"""Dango race simulator package."""

from dango_sim.listener import (
    RaceTrace,
    SimulationStats,
    StatsCollector,
    TraceEvent,
    TraceRecorder,
)
from dango_sim.models import (
    Board,
    Dango,
    RaceConfig,
    RaceResult,
    RaceStartingState,
)
from dango_sim.simulation import SimulationSummary, run_simulations
from dango_sim.state_io import dump_starting_state, load_starting_state

__all__ = [
    "Board",
    "Dango",
    "RaceConfig",
    "RaceResult",
    "RaceStartingState",
    "RaceTrace",
    "SimulationStats",
    "SimulationSummary",
    "StatsCollector",
    "TraceEvent",
    "TraceRecorder",
    "dump_starting_state",
    "load_starting_state",
    "run_simulations",
]
```

- [ ] **Step 2: Update `main.py` CLI**

Add `--no-stats` and `--trace` flags. Print stats after results.

```python
from __future__ import annotations

import argparse
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from dango_sim.sample_config import build_sample_config
from dango_sim.simulation import run_simulations
from dango_sim.state_io import load_starting_state


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser(description="Run dango race simulations.")
    parser.add_argument(
        "--runs",
        type=positive_int,
        default=1000,
        help="number of simulations to run",
    )
    parser.add_argument("--seed", type=int, default=None, help="random seed")
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
    parser.add_argument(
        "--workers",
        type=positive_int,
        default=None,
        help="number of parallel workers (default: sequential)",
    )
    parser.add_argument(
        "--no-stats",
        action="store_true",
        default=False,
        help="disable statistics collection for maximum throughput",
    )
    parser.add_argument(
        "--trace",
        type=positive_int,
        nargs="?",
        const=10,
        default=None,
        help="record race traces (optional: number of races to trace, default: 10)",
    )
    args = parser.parse_args()

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
        max_workers=args.workers,
        stats=not args.no_stats,
        trace=args.trace is not None,
        trace_limit=args.trace,
    )
    print(f"Runs: {summary.runs}")
    print(f"Average rounds: {summary.average_rounds:.2f}")
    for dango_id, wins in sorted(
        summary.wins.items(),
        key=lambda item: (-item[1], item[0]),
    ):
        win_rate = summary.win_rates[dango_id] * 100
        avg_rank = summary.average_rank[dango_id]
        print(
            f"{dango_id}: wins={wins}, "
            f"win_rate={win_rate:.2f}%, average_rank={avg_rank:.2f}"
        )
    for n, rates in sorted(summary.top_n_rates.items()):
        print(f"Top {n} rates:")
        for dango_id, rate in sorted(rates.items(), key=lambda item: (-item[1], item[0])):
            print(f"  {dango_id}: {rate * 100:.2f}%")

    if summary.stats is not None:
        print("\nSkill triggers:")
        for dango_id in sorted(summary.stats.skill_triggers):
            hooks = summary.stats.skill_triggers[dango_id]
            parts = [f"{hook}={count}" for hook, count in sorted(hooks.items())]
            print(f"  {dango_id}: {', '.join(parts)}")

        print("\nPosition heatmap:")
        for dango_id in sorted(summary.stats.position_heatmap):
            heatmap = summary.stats.position_heatmap[dango_id]
            top_positions = sorted(heatmap.items(), key=lambda item: -item[1])[:5]
            parts = [f"pos {pos}: {freq * 100:.1f}%" for pos, freq in top_positions]
            print(f"  {dango_id}: {', '.join(parts)}")

    if summary.traces is not None:
        print(f"\nTraces: {len(summary.traces)} races recorded")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run all tests and verify CLI**

Run: `python -m pytest tests/ -v`
Expected: All tests pass

Run: `python main.py --runs 50 --seed 42`
Expected: Output includes "Skill triggers:" and "Position heatmap:" sections

Run: `python main.py --runs 50 --seed 42 --no-stats`
Expected: No stats sections in output

Run: `python main.py --runs 50 --seed 42 --trace 5`
Expected: Output includes "Traces: 5 races recorded"

- [ ] **Step 4: Commit**

```bash
git add src/dango_sim/__init__.py main.py
git commit -m "feat: add --no-stats and --trace CLI flags, export listener types"
```

---

## Verification

After all tasks:

1. **Full test suite**: `python -m pytest tests/ -v` — all 128+ tests pass
2. **CLI smoke test**: `python main.py --runs 100 --seed 42 --trace 3` — produces results with stats and trace info
3. **No-stats mode**: `python main.py --runs 100 --seed 42 --no-stats` — produces results without stats
4. **Parallel + stats**: `python main.py --runs 100 --seed 42 --workers 4` — produces results with stats
5. **Determinism**: Sequential and parallel with same seed produce same stats
