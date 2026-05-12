from __future__ import annotations

from dataclasses import dataclass

from dango_sim.models import Dango, RaceState


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
class AugustaSkill:
    def on_round_start(self, dango: Dango, state: RaceState, engine, rng) -> None:
        if not state.is_entered(dango.id):
            return
        position = state.position_of(dango.id)
        stack = state.stack_at(position)
        if stack and stack[-1] == dango.id:
            engine.skip_turn_this_round(dango.id)
            engine.force_last_next_round(dango.id)


@dataclass
class AemeathSkill:
    used: bool = False
    consume_on_fail: bool = False
    waiting: bool = False
    midpoint: int | None = None

    def after_move(self, dango: Dango, state: RaceState, context, rng, engine) -> None:
        self._handle_move_path(dango, state, context, engine)

    def after_any_move(self, dango: Dango, state: RaceState, context, rng, engine) -> None:
        self._handle_move_path(dango, state, context, engine)
        if self.used or not self.waiting:
            return
        self.try_teleport(dango, state, engine, enter_wait=False)

    def _handle_move_path(self, dango: Dango, state: RaceState, context, engine) -> None:
        if self.used:
            return

        group = getattr(context, "group", [])
        if dango.id not in group:
            return

        path = getattr(context, "path", [])
        midpoint = self.midpoint if self.midpoint is not None else engine.config.board.finish // 2
        if midpoint not in path:
            return

        self.try_teleport(dango, state, engine, enter_wait=True)

    def try_teleport(self, dango: Dango, state: RaceState, engine, *, enter_wait: bool) -> None:
        if self.used:
            return

        position = state.position_of(dango.id)
        target = engine.nearest_normal_dango_ahead(position, exclude_id=dango.id)
        if target is None:
            if self.consume_on_fail:
                self.used = True
                self.waiting = False
            elif enter_wait:
                self.waiting = True
            return

        target_position, _target_id = target
        state.remove_ids([dango.id])
        state.place_group([dango.id], target_position)
        self.used = True
        self.waiting = False
