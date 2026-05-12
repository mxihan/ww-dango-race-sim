from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from dango_sim.models import BU_KING_ID, RaceState


class TileEffect(Protocol):
    def on_landed(self, group: list[str], position: int, state: RaceState, rng) -> int:
        raise NotImplementedError


@dataclass(frozen=True)
class Booster:
    steps: int = 1

    def on_landed(self, group: list[str], position: int, state: RaceState, rng) -> int:
        return position + self.steps


@dataclass(frozen=True)
class Inhibitor:
    steps: int = 1

    def on_landed(self, group: list[str], position: int, state: RaceState, rng) -> int:
        return position - self.steps


@dataclass(frozen=True)
class SpaceTimeRift:
    def on_landed(self, group: list[str], position: int, state: RaceState, rng) -> int:
        stack = state.stack_at(position)
        has_bu_king = BU_KING_ID in stack
        normal_stack = [dango_id for dango_id in stack if dango_id != BU_KING_ID]
        rng.shuffle(normal_stack)
        state.positions[position] = (
            [BU_KING_ID, *normal_stack] if has_bu_king else normal_stack
        )
        return position
