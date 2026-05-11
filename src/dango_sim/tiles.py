from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from dango_sim.models import RaceState


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
        rng.shuffle(stack)
        state.positions[position] = stack
        return position
