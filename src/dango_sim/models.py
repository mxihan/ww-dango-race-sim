from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping, Protocol


BU_KING_ID = "bu_king"


class Skill(Protocol):
    pass


class TileEffect(Protocol):
    pass


@dataclass(frozen=True)
class Board:
    finish: int
    tiles: Mapping[int, TileEffect] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "tiles", MappingProxyType(dict(self.tiles)))


@dataclass
class Dango:
    id: str
    name: str
    skill: Skill | None = None
    is_special: bool = False


@dataclass(frozen=True)
class RaceStartingState:
    positions: Mapping[int, tuple[str, ...] | list[str]]
    laps_completed: Mapping[str, int]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "positions",
            MappingProxyType(
                {
                    int(position): tuple(stack)
                    for position, stack in self.positions.items()
                }
            ),
        )
        object.__setattr__(
            self,
            "laps_completed",
            MappingProxyType(
                {
                    str(dango_id): int(laps)
                    for dango_id, laps in self.laps_completed.items()
                }
            ),
        )


@dataclass
class RaceConfig:
    board: Board
    participants: list[Dango]
    include_bu_king: bool = True
    max_rounds: int = 500
    max_tile_depth: int = 20
    tile_resolution: str = "single"
    order_direction: str = "high_first"
    bu_king_order_faces: str = "d3"
    starting_state: RaceStartingState | None = None

    def validate(self) -> None:
        if self.board.finish <= 0:
            raise ValueError("board finish must be positive")
        normal_ids = [dango.id for dango in self.participants if not dango.is_special]
        if not normal_ids:
            raise ValueError("at least one normal dango must participate")
        if len(normal_ids) != len(set(normal_ids)):
            raise ValueError("normal dango ids must be unique")
        if any(dango.id == BU_KING_ID for dango in self.participants):
            raise ValueError("Bu King is managed by the engine and must not be provided")
        for position in self.board.tiles:
            if not (0 < position < self.board.finish):
                raise ValueError("tile positions must be within 1..(finish-1)")
        if self.max_rounds <= 0:
            raise ValueError("max_rounds must be positive")
        if self.max_tile_depth <= 0:
            raise ValueError("max_tile_depth must be positive")
        if self.tile_resolution not in {"single", "chain"}:
            raise ValueError("tile_resolution must be 'single' or 'chain'")
        if self.order_direction not in {"high_first", "low_first"}:
            raise ValueError("order_direction must be 'high_first' or 'low_first'")
        if self.bu_king_order_faces not in {"d3", "d6"}:
            raise ValueError("bu_king_order_faces must be 'd3' or 'd6'")
        if self.starting_state is not None:
            self._validate_starting_state(normal_ids)

    def _validate_starting_state(self, normal_ids: list[str]) -> None:
        assert self.starting_state is not None
        seen: list[str] = []
        for position, stack in self.starting_state.positions.items():
            if not (0 <= position < self.board.finish):
                raise ValueError("starting_state positions must be within 0..(finish-1)")
            if not stack:
                raise ValueError("starting_state stacks must not be empty")
            seen.extend(dango_id for dango_id in stack if dango_id != BU_KING_ID)

        if sorted(seen) != sorted(normal_ids):
            raise ValueError("starting_state must include every normal dango exactly once")
        if len(seen) != len(set(seen)):
            raise ValueError("starting_state normal dango ids must be unique")

        lap_ids = set(self.starting_state.laps_completed)
        if lap_ids != set(normal_ids):
            raise ValueError("starting_state laps_completed must include every normal dango")
        for dango_id, laps in self.starting_state.laps_completed.items():
            if laps < 0:
                raise ValueError("starting_state laps_completed values must be non-negative")


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

    @classmethod
    def initial(cls, dango_ids: list[str], start_position: int = 0) -> RaceState:
        return cls(
            positions={start_position: list(dango_ids)},
            laps_completed={dango_id: 0 for dango_id in dango_ids},
        )

    @classmethod
    def empty(cls, dango_ids: list[str]) -> RaceState:
        return cls(
            positions={},
            laps_completed={dango_id: 0 for dango_id in dango_ids},
        )

    @classmethod
    def from_starting_state(cls, starting_state: RaceStartingState) -> RaceState:
        return cls(
            positions={
                position: list(stack)
                for position, stack in starting_state.positions.items()
            },
            laps_completed=dict(starting_state.laps_completed),
        )

    def is_entered(self, dango_id: str) -> bool:
        pos = self._pos_index.get(dango_id)
        if pos is not None:
            if pos in self.positions and dango_id in self.positions[pos]:
                return True
        # Lazy fallback for stale index
        for position, stack in self.positions.items():
            if dango_id in stack:
                # Rebuild index entry
                self._pos_index[dango_id] = position
                return True
        return False

    def enter_at_start(self, dango_id: str) -> None:
        if self.is_entered(dango_id):
            return
        self.place_group([dango_id], 0)
        self.laps_completed.setdefault(dango_id, 0)

    def stack_at(self, position: int) -> list[str]:
        return list(self.positions.get(position, []))

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

    def stack_index(self, dango_id: str) -> int:
        position = self.position_of(dango_id)
        return self.positions[position].index(dango_id)

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

    def remove_ids(self, dango_ids: list[str]) -> None:
        to_remove = set(dango_ids)
        affected: set[int] = set()
        # Try to use index for targeted removal
        for dango_id in to_remove:
            pos = self._pos_index.get(dango_id)
            if pos is not None:
                affected.add(pos)
        # Fallback to full scan if index is stale (no positions found or dangos not in index)
        if not affected or any(d_id not in self._pos_index for d_id in to_remove):
            affected = set(self.positions.keys())
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

    def place_group(self, group: list[str], position: int, *, bottom: bool = False) -> None:
        existing = self.positions.setdefault(position, [])
        if bottom:
            self.positions[position] = list(group) + existing
        else:
            existing.extend(group)
        for dango_id in group:
            self._pos_index[dango_id] = position

    def all_stacks(self) -> dict[int, list[str]]:
        return {position: list(stack) for position, stack in self.positions.items()}


@dataclass(frozen=True)
class RaceResult:
    winner_id: str
    rankings: tuple[str, ...]
    rounds: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "rankings", tuple(self.rankings))
