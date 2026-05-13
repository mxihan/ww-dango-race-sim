from __future__ import annotations

import random

from dango_sim.engine import RaceEngine
from dango_sim.listener import RaceTrace, SimulationStats, StatsCollector, TraceEvent, TraceRecorder
from dango_sim.models import Board, Dango, RaceConfig, RaceState


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


# --- TraceRecorder tests ---


def test_trace_recorder_captures_move():
    recorder = TraceRecorder()
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="a", name="A")],
        include_bu_king=False,
    )
    engine = RaceEngine(config, random.Random(0), listeners=[recorder])
    engine.run()
    move_events = [e for e in recorder.events if e.kind == "move"]
    assert len(move_events) >= 1
    assert move_events[0].data["dango_id"] == "a"


def test_trace_event_has_state_snapshot():
    recorder = TraceRecorder()
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="a", name="A")],
        include_bu_king=False,
    )
    engine = RaceEngine(config, random.Random(0), listeners=[recorder])
    engine.run()
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
    recorder = TraceRecorder()
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="a", name="A")],
        include_bu_king=False,
    )
    engine = RaceEngine(config, random.Random(0), listeners=[recorder])
    engine.run()
    finish_events = [e for e in recorder.events if e.kind == "finish"]
    assert len(finish_events) == 1
    assert "a" in finish_events[0].data["group"]


def test_trace_recorder_as_trace():
    recorder = TraceRecorder()
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="a", name="A")],
        include_bu_king=False,
    )
    engine = RaceEngine(config, random.Random(0), listeners=[recorder])
    engine.run()
    trace = recorder.as_trace()
    assert isinstance(trace, RaceTrace)
    assert len(trace.events) == len(recorder.events)


# --- StatsCollector tests ---


def test_stats_collector_skill_triggers():
    state = RaceState(positions={0: ["a", "b"]}, laps_completed={"a": 0, "b": 0})
    state.round_number = 1
    collector = StatsCollector()
    collector.on_skill(dango_id="a", hook_name="modify_roll", state=state)
    collector.on_skill(dango_id="a", hook_name="modify_roll", state=state)
    collector.on_skill(dango_id="b", hook_name="before_move", state=state)
    assert collector.skill_triggers["a"]["modify_roll"] == 2
    assert collector.skill_triggers["b"]["before_move"] == 1


def test_stats_collector_position_heatmap():
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
    state = RaceState(positions={0: ["a"]}, laps_completed={"a": 0})
    state.round_number = 1
    collector = StatsCollector()
    collector.on_move(dango_id="a", from_pos=0, to_pos=3, group=["a"], path=[1, 2, 3], state=state)
    collector.on_move(dango_id="a", from_pos=3, to_pos=5, group=["a"], path=[4, 5], state=state)
    assert collector.position_counts["a"][3] == 1


def test_stats_collector_compute_heatmap():
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
