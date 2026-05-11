from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable

from dango_sim.models import Dango, RaceConfig, RaceResult, RaceState


@dataclass
class TurnContext:
    round_rolls: dict[str, int]
    base_roll: int
    movement: int
    blocked: bool = False


class RaceEngine:
    def __init__(self, config: RaceConfig, rng: random.Random | None = None):
        config.validate()
        self.config = config
        self.rng = rng or random.Random()
        self.dangos: dict[str, Dango] = {
            dango.id: dango for dango in config.participants
        }
        self.state = RaceState.initial(self.normal_ids())

    def run(self) -> RaceResult:
        for round_number in range(1, self.config.max_rounds + 1):
            self.state.round_number = round_number
            order = self.normal_ids()
            self.rng.shuffle(order)
            round_rolls = self.roll_round_values(order)

            for dango_id in order:
                if self.has_finished():
                    break
                self.take_turn(
                    dango_id,
                    base_roll=round_rolls[dango_id],
                    round_rolls=round_rolls,
                )
                if self.has_finished():
                    rankings = self.rankings()
                    return RaceResult(
                        winner_id=rankings[0],
                        rankings=rankings,
                        rounds=round_number,
                    )

        raise RuntimeError("race did not finish within max_rounds")

    def normal_ids(self) -> list[str]:
        return [
            dango.id for dango in self.config.participants if not dango.is_special
        ]

    def roll_round_values(self, order: Iterable[str]) -> dict[str, int]:
        return {dango_id: self.roll_for(dango_id) for dango_id in order}

    def roll_for(self, dango_id: str) -> int:
        dango = self.dangos[dango_id]
        faces = [1, 2, 3]
        if dango.skill and hasattr(dango.skill, "roll_faces"):
            faces = list(dango.skill.roll_faces(dango, self.state))
        if dango.skill and hasattr(dango.skill, "roll"):
            return int(dango.skill.roll(dango, self.state, self.rng))
        return int(self.rng.choice(faces))

    def take_turn(
        self,
        dango_id: str,
        *,
        base_roll: int | None = None,
        round_rolls: dict[str, int] | None = None,
    ) -> None:
        if base_roll is None:
            base_roll = self.roll_for(dango_id)

        context = TurnContext(
            round_rolls=round_rolls or {dango_id: base_roll},
            base_roll=base_roll,
            movement=base_roll,
        )
        dango = self.dangos[dango_id]
        if dango.skill and hasattr(dango.skill, "modify_roll"):
            context.movement = int(
                dango.skill.modify_roll(
                    dango,
                    context.movement,
                    self.state,
                    context,
                    self.rng,
                )
            )
        if dango.skill and hasattr(dango.skill, "before_move"):
            dango.skill.before_move(dango, self.state, context, self.rng)
        if context.blocked or context.movement <= 0:
            return

        source = self.state.position_of(dango_id)
        group = self.state.lift_group_from(dango_id)
        destination = source + context.movement
        self.move_group_to(group, destination)

        if dango.skill and hasattr(dango.skill, "after_move"):
            dango.skill.after_move(dango, self.state, context, self.rng, self)

    def move_group_to(self, group: list[str], destination: int) -> None:
        self.state.remove_ids(group)
        self.state.place_group(group, destination)
        self.resolve_tiles(group, destination)

    def resolve_tiles(self, group: list[str], position: int) -> None:
        current = position
        for _ in range(self.config.max_tile_depth):
            tile = self.config.board.tiles.get(current)
            if tile is None:
                return

            next_position = tile.on_landed(group, current, self.state, self.rng)
            if next_position == current:
                return

            self.state.remove_ids(group)
            self.state.place_group(group, next_position)
            current = next_position

        raise RuntimeError("tile resolution exceeded maximum depth")

    def has_finished(self) -> bool:
        for dango_id in self.normal_ids():
            if self.state.position_of(dango_id) >= self.config.board.finish:
                return True
        return False

    def rankings(self) -> list[str]:
        normal_ids = set(self.normal_ids())
        ordered: list[str] = []

        finish_positions = sorted(
            [
                position
                for position in self.state.positions
                if position >= self.config.board.finish
            ],
            reverse=True,
        )
        for position in finish_positions:
            ordered.extend(
                dango_id
                for dango_id in reversed(self.state.stack_at(position))
                if dango_id in normal_ids
            )

        remaining_positions = sorted(
            [
                position
                for position in self.state.positions
                if position < self.config.board.finish
            ],
            reverse=True,
        )
        for position in remaining_positions:
            ordered.extend(
                dango_id
                for dango_id in reversed(self.state.stack_at(position))
                if dango_id in normal_ids and dango_id not in ordered
            )

        return ordered
