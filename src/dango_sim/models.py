from __future__ import annotations

from dataclasses import dataclass, field
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


@dataclass
class Dango:
    id: str
    name: str
    skill: Skill | None = None
    is_special: bool = False


@dataclass
class RaceConfig:
    board: Board
    participants: list[Dango]
    include_bu_king: bool = True
    max_rounds: int = 500
    max_tile_depth: int = 20

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
            if position < 0 or position > self.board.finish:
                raise ValueError("tile positions must be within 0..finish")
        if self.max_rounds <= 0:
            raise ValueError("max_rounds must be positive")
        if self.max_tile_depth <= 0:
            raise ValueError("max_tile_depth must be positive")


@dataclass
class RaceState:
    positions: dict[int, list[str]]
    round_number: int = 0

    @classmethod
    def initial(cls, dango_ids: list[str], start_position: int = 0) -> RaceState:
        return cls(positions={start_position: list(dango_ids)})

    def stack_at(self, position: int) -> list[str]:
        return list(self.positions.get(position, []))

    def position_of(self, dango_id: str) -> int:
        for position, stack in self.positions.items():
            if dango_id in stack:
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
        return group

    def remove_ids(self, dango_ids: list[str]) -> None:
        to_remove = set(dango_ids)
        empty_positions = []
        for position, stack in self.positions.items():
            self.positions[position] = [
                dango_id for dango_id in stack if dango_id not in to_remove
            ]
            if not self.positions[position]:
                empty_positions.append(position)
        for position in empty_positions:
            del self.positions[position]

    def place_group(self, group: list[str], position: int, *, bottom: bool = False) -> None:
        existing = self.positions.setdefault(position, [])
        if bottom:
            self.positions[position] = list(group) + existing
        else:
            existing.extend(group)

    def all_stacks(self) -> dict[int, list[str]]:
        return {position: list(stack) for position, stack in self.positions.items()}


@dataclass(frozen=True)
class RaceResult:
    winner_id: str
    rankings: list[str]
    rounds: int
