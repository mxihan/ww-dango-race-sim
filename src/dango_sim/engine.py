from __future__ import annotations

import random
from copy import deepcopy
from dataclasses import dataclass
from typing import Iterable

from dango_sim.models import BU_KING_ID, Dango, RaceConfig, RaceResult, RaceState


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
        self.participants = deepcopy(config.participants)
        self.dangos: dict[str, Dango] = {
            dango.id: dango for dango in self.participants
        }
        self.state = RaceState.initial(self.normal_ids())
        if self.config.include_bu_king:
            self.dangos[BU_KING_ID] = Dango(
                id=BU_KING_ID,
                name="Bu King",
                is_special=True,
            )
            self.state.place_group([BU_KING_ID], self.config.board.finish)

    def run(self) -> RaceResult:
        for round_number in range(1, self.config.max_rounds + 1):
            self.state.round_number = round_number
            order = self.normal_ids()
            if self.config.include_bu_king:
                order.append(BU_KING_ID)
            self.rng.shuffle(order)
            round_rolls = self.roll_round_values(
                dango_id for dango_id in order if dango_id != BU_KING_ID
            )

            for dango_id in order:
                if self.has_finished():
                    break
                if dango_id == BU_KING_ID:
                    self.take_bu_king_turn()
                else:
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

            if not self.has_finished():
                self.end_round()

        raise RuntimeError("race did not finish within max_rounds")

    def normal_ids(self) -> list[str]:
        return [
            dango.id for dango in self.participants if not dango.is_special
        ]

    def normalize_position(self, position: int) -> int:
        return position % self.config.board.finish

    def next_position(self, position: int, steps: int = 1) -> int:
        return (position + steps) % self.config.board.finish

    def previous_position(self, position: int, steps: int = 1) -> int:
        return (position - steps) % self.config.board.finish

    def forward_path(self, source: int, steps: int) -> list[int]:
        return [self.next_position(source, step) for step in range(1, steps + 1)]

    def backward_path(self, source: int, steps: int) -> list[int]:
        return [self.previous_position(source, step) for step in range(1, steps + 1)]

    def path_passes_start(self, path: list[int]) -> bool:
        return 0 in path

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
        if destination >= self.config.board.finish:
            self.state.place_group(group, destination)
            return
        self.move_group_to(group, destination)

        if dango.skill and hasattr(dango.skill, "after_move"):
            dango.skill.after_move(dango, self.state, context, self.rng, self)

    def move_group_to(self, group: list[str], destination: int) -> None:
        self.state.remove_ids(group)
        self.state.place_group(group, destination)
        self.resolve_tiles(group, destination)

    def take_bu_king_turn(self) -> None:
        if not self.config.include_bu_king or self.state.round_number < 3:
            return

        roll = int(self.rng.choice([1, 2, 3, 4, 5, 6]))
        source = self.state.position_of(BU_KING_ID)
        target = source - roll
        normal_ids = set(self.normal_ids())
        contacted_positions = sorted(
            [
                position
                for position, stack in self.state.positions.items()
                if target <= position < source
                and any(dango_id in normal_ids for dango_id in stack)
            ],
            reverse=True,
        )

        carried_group = self.state.lift_group_from(BU_KING_ID)
        for position in contacted_positions:
            carried_group.extend(
                dango_id
                for dango_id in self.state.stack_at(position)
                if dango_id in normal_ids
            )

        self.state.remove_ids(carried_group)
        self.state.place_group(carried_group, target)
        self.resolve_tiles(carried_group, target)

    def end_round(self) -> None:
        if not self.config.include_bu_king:
            return

        normal_positions = [
            self.state.position_of(dango_id) for dango_id in self.normal_ids()
        ]
        last_place = min(normal_positions)
        if self.state.position_of(BU_KING_ID) >= last_place:
            return

        self.state.remove_ids([BU_KING_ID])
        self.state.place_group([BU_KING_ID], self.config.board.finish)

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

        if self.config.board.tiles.get(current) is None:
            return
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
