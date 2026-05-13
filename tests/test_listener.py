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
