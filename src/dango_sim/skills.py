from __future__ import annotations

from dataclasses import dataclass

from dango_sim.models import BU_KING_ID, Dango, RaceState


@dataclass
class CorletaSkill:
    chance: float = 0.28

    def modify_roll(self, dango: Dango, roll: int, state: RaceState, context, rng) -> int:
        return roll * 2 if rng.random() < self.chance else roll


@dataclass
class QianlianSkill:
    bonus: int = 2

    def modify_roll(self, dango: Dango, roll: int, state: RaceState, context, rng) -> int:
        return roll + self.bonus if roll == min(context.round_rolls.values()) else roll


@dataclass
class LinnaeSkill:
    blocked_chance: float = 0.20
    double_chance: float = 0.60

    def before_move(self, dango: Dango, state: RaceState, context, rng) -> None:
        blocked = rng.random() < self.blocked_chance
        doubled = rng.random() < self.double_chance
        if blocked:
            context.blocked = True
            return
        if doubled:
            context.movement *= 2


@dataclass
class MorningSkill:
    sequence: tuple[int, ...] = (3, 2, 1)
    index: int = 0

    def roll(self, dango: Dango, state: RaceState, rng) -> int:
        value = self.sequence[self.index]
        self.index = (self.index + 1) % len(self.sequence)
        return value


@dataclass(frozen=True)
class ShorekeeperSkill:
    def roll_faces(self, dango: Dango, state: RaceState) -> list[int]:
        return [2, 3]


@dataclass
class AimisSkill:
    used: bool = False

    def after_move(self, dango: Dango, state: RaceState, context, rng, engine) -> None:
        if self.used:
            return

        position = state.position_of(dango.id)
        midpoint = engine.config.board.finish / 2
        if position < midpoint:
            return

        candidates = []
        for candidate_position, stack in state.positions.items():
            if candidate_position <= position:
                continue
            if any(candidate_id != BU_KING_ID for candidate_id in stack):
                candidates.append(candidate_position)
        if not candidates:
            return

        target = min(candidates)
        group = state.lift_group_from(dango.id)
        state.place_group(group, target)
        self.used = True
