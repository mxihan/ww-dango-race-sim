from __future__ import annotations

from dataclasses import dataclass

from dango_sim.models import BU_KING_ID, Dango, RaceState


@dataclass
class CarlottaSkill:
    chance: float = 0.28

    def modify_roll(self, dango: Dango, roll: int, state: RaceState, context, rng) -> int:
        return roll * 2 if rng.random() < self.chance else roll


@dataclass
class ChisaSkill:
    bonus: int = 2

    def modify_roll(self, dango: Dango, roll: int, state: RaceState, context, rng) -> int:
        return roll + self.bonus if roll == min(context.round_rolls.values()) else roll


@dataclass
class LynaeSkill:
    blocked_chance: float = 0.20
    double_chance: float = 0.60

    def before_move(self, dango: Dango, state: RaceState, context, rng) -> None:
        r = rng.random()
        if r < self.blocked_chance:
            context.blocked = True
        elif r < self.blocked_chance + self.double_chance:
            context.movement *= 2


@dataclass
class MornyeSkill:
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
class AemeathSkill:
    used: bool = False
    consume_on_fail: bool = True

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
            if self.consume_on_fail:
                self.used = True
            return

        target = min(candidates)
        source = state.position_of(dango.id)
        source_stack = state.positions[source]
        source_stack.remove(dango.id)
        if not source_stack:
            del state.positions[source]
        state.place_group([dango.id], target)
        self.used = True
