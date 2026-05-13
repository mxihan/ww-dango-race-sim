from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

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

    def on_bu_king(self, **_kw):
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
