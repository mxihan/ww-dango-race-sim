# Race Trace & Rich Statistics Design

**Goal:** Add an opt-in event trace system and lightweight aggregate statistics collection to the dango race simulator, enabling race debugging/replay and cross-run statistical analysis.

**Architecture:** Engine-level listener protocol with two composable consumers. TraceRecorder captures full event histories with state snapshots for individual race inspection. StatsCollector accumulates skill trigger counts and position frequencies with negligible overhead for any run count.

**Tech Stack:** Python stdlib only (dataclasses, copy, collections). No new dependencies.

---

## Listener System

The engine accepts optional `listeners` in its constructor. Each listener is any object implementing `on_*` methods matching event names.

### Engine changes (`src/dango_sim/engine.py`)

Add `listeners: list[object] | None = None` parameter to `RaceEngine.__init__`. Store as `self._listeners`.

Add `_emit` method:

```python
def _emit(self, event: str, **kwargs) -> None:
    for listener in self._listeners:
        handler = getattr(listener, f"on_{event}", None)
        if handler is not None:
            handler(**kwargs)
```

Call `_emit` at these engine points:

| Engine method | Event name | kwargs |
|---|---|---|
| `take_turn` after movement | `move` | `dango_id, from_pos, to_pos, group, path, state` |
| `take_bu_king_turn` after each step | `bu_king` | `roll, path, state` |
| `resolve_single_tile` / `resolve_chained_tiles` after tile fires | `tile` | `group, position, tile, next_position, state` |
| `take_turn` after each skill hook call | `skill` | `dango_id, hook_name, state` |
| `finish_group_at_start` | `finish` | `group, position, state` |

When `self._listeners` is empty (the default), `_emit` is a no-op — zero overhead.

---

## TraceRecorder (`src/dango_sim/listener.py`)

Records full event history for a single race with deep-copied state snapshots.

### TraceEvent dataclass

```python
@dataclass(frozen=True)
class TraceEvent:
    kind: str            # "move", "tile", "skill", "finish", "bu_king"
    round_number: int
    data: dict           # event-specific (dango_id, from_pos, to_pos, etc.)
    state_snapshot: dict # serialized RaceState: positions, laps, round_number
```

`state_snapshot` stores a lightweight dict copy (not a deep copy of the full RaceState object) to keep memory manageable:

```python
{"positions": {0: ["a", "b"], 5: ["c"]}, "laps_completed": {"a": 0, "b": 0, "c": 1}, "round_number": 3}
```

### TraceRecorder class

```python
@dataclass
class TraceRecorder:
    events: list[TraceEvent] = field(default_factory=list)

    def on_move(self, *, dango_id, from_pos, to_pos, group, path, state, **_kw):
        self.events.append(TraceEvent(
            kind="move", round_number=state.round_number,
            data={"dango_id": dango_id, "from": from_pos, "to": to_pos, "group": group, "path": path},
            state_snapshot=_snapshot(state),
        ))

    # on_tile, on_skill, on_finish, on_bu_king follow same pattern
```

Helper to extract a snapshot dict from RaceState:

```python
def _snapshot(state: RaceState) -> dict:
    return {
        "positions": {pos: list(stack) for pos, stack in state.positions.items()},
        "laps_completed": dict(state.laps_completed),
        "round_number": state.round_number,
    }
```

### RaceTrace container

```python
@dataclass(frozen=True)
class RaceTrace:
    events: tuple[TraceEvent, ...]
```

---

## StatsCollector (`src/dango_sim/listener.py`)

Lightweight accumulator for cross-run statistics.

### Collected data

**Skill triggers:** Count of hook invocations per dango per hook name.

```python
skill_triggers: dict[str, dict[str, int]]
# {"augusta": {"on_round_start": 45230}, "carlotta": {"modify_roll": 89542}}
```

**Position heatmap:** Total rounds each dango spent at each position. Normalized to frequencies by dividing by total rounds across all runs.

```python
position_counts: dict[str, dict[int, int]]
position_heatmap: dict[str, dict[int, float]]
# {"carlotta": {0: 15234, 1: 892, ...}}
# {"carlotta": {0: 0.31, 1: 0.02, ...}}
```

Position is recorded at round end via `on_move` and `on_finish` events. For `on_finish`, position is 0 (finish line).

### StatsCollector class

```python
@dataclass
class StatsCollector:
    skill_triggers: dict[str, dict[str, int]] = field(default_factory=lambda: defaultdict(lambda: defaultdict(int)))
    position_counts: dict[str, dict[int, int]] = field(default_factory=lambda: defaultdict(lambda: defaultdict(int)))
    _current_round: int = 0
    _recorded_this_round: set[str] = field(default_factory=set)

    def on_skill(self, *, dango_id, hook_name, **_kw):
        self.skill_triggers[dango_id][hook_name] += 1

    def on_move(self, *, dango_id, to_pos, group, state, **_kw):
        self._record_position(dango_id, to_pos, state)

    def on_finish(self, *, group, position, state, **_kw):
        for dango_id in group:
            self._record_position(dango_id, position, state)

    def _record_position(self, dango_id, position, state):
        if state.round_number != self._current_round:
            self._current_round = state.round_number
            self._recorded_this_round.clear()
        if dango_id not in self._recorded_this_round:
            self.position_counts[dango_id][position] += 1
            self._recorded_this_round.add(dango_id)

    def compute_heatmap(self, total_rounds: int) -> dict[str, dict[int, float]]:
        return {
            dango_id: {pos: count / total_rounds for pos, count in positions.items()}
            for dango_id, positions in self.position_counts.items()
        }
```

### SimulationStats container

```python
@dataclass(frozen=True)
class SimulationStats:
    skill_triggers: Mapping[str, Mapping[str, int]]
    position_heatmap: Mapping[str, Mapping[int, float]]
```

---

## run_simulations Integration (`src/dango_sim/simulation.py`)

### New parameters

```python
def run_simulations(
    *,
    config_factory,
    runs,
    seed=None,
    engine_cls=RaceEngine,
    max_workers=None,
    top_n=(),
    stats: bool = True,           # NEW: collect aggregate stats (default on)
    trace: bool = False,          # NEW: enable trace recording
    trace_limit: int | None = None,  # NEW: max races to trace (default: all)
) -> SimulationSummary:
```

### Stats aggregation

When `stats=True` (default):
1. Each run creates a fresh `StatsCollector` as a listener
2. After all runs complete, aggregate skill trigger counts and position counts across all collectors
3. Normalize position counts to frequencies using total rounds
4. Store in `SimulationSummary.stats`

For parallel execution (`max_workers > 1`): StatsCollector must be picklable. Use plain dicts instead of defaultdicts. The `_run_single` worker returns both the `RaceResult` and the `StatsCollector` data.

### Trace recording

When `trace=True`:
1. Create a `TraceRecorder` for the first `trace_limit` races (or all if None)
2. Store traces in `SimulationSummary.traces`

Traces are only meaningful for small batches (memory). For parallel execution, traces are only collected in the sequential fallback path, or trace_limit must be small enough to fit in memory.

---

## SimulationSummary Changes (`src/dango_sim/simulation.py`)

Add two optional fields:

```python
@dataclass(frozen=True)
class SimulationSummary:
    runs: int
    wins: Mapping[str, int]
    win_rates: Mapping[str, float]
    average_rank: Mapping[str, float]
    average_rounds: float
    top_n_rates: Mapping[int, Mapping[str, float]] = field(default_factory=dict)
    stats: SimulationStats | None = None          # NEW
    traces: tuple[RaceTrace, ...] | None = None    # NEW
```

---

## CLI Changes (`main.py`)

Add `--stats` flag (default on) and `--trace` flag with optional limit:

```bash
# Default: stats on, no trace
python main.py --runs 5000

# Stats + trace first 5 races
python main.py --runs 5000 --trace 5

# Disable stats (raw speed)
python main.py --runs 50000 --no-stats
```

Print stats after results:

```
Skill triggers:
  augusta: on_round_start=4523
  carlotta: modify_roll=8954
  ...

Position heatmap (carlotta):
  pos 0: 31.2%  pos 3: 8.5%  pos 6: 12.1%  ...
```

---

## Files Summary

| File | Action |
|---|---|
| `src/dango_sim/listener.py` | Create: TraceEvent, RaceTrace, TraceRecorder, StatsCollector, SimulationStats |
| `src/dango_sim/engine.py` | Modify: add listeners param, _emit calls at 5 engine points |
| `src/dango_sim/simulation.py` | Modify: add stats/trace/trace_limit params, aggregate logic |
| `src/dango_sim/__init__.py` | Modify: export new public types |
| `main.py` | Modify: add --stats/--no-stats, --trace flags, print stats |
| `tests/test_listener.py` | Create: tests for TraceRecorder, StatsCollector, integration |

---

## Constraints

- Zero new dependencies (stdlib only)
- No change to existing public API when stats/trace are not used
- StatsCollector overhead must be negligible (<5% even at 100k runs)
- TraceRecorder is explicitly opt-in; never created by default
- All new types must be picklable for parallel execution support
