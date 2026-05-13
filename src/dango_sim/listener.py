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
