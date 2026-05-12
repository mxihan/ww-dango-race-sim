from __future__ import annotations

import random
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Iterable

from dango_sim.models import BU_KING_ID, Dango, RaceConfig, RaceResult, RaceState


@dataclass
class TurnContext:
    round_rolls: dict[str, int]
    base_roll: int
    movement: int
    path: list[int] = field(default_factory=list)
    group: list[str] = field(default_factory=list)
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
            self.state.place_group([BU_KING_ID], 0, bottom=True)

    def run(self) -> RaceResult:
        for round_number in range(1, self.config.max_rounds + 1):
            self.state.round_number = round_number
            order = self.build_round_order(round_number)
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

    def build_round_order(self, round_number: int) -> list[str]:
        order = self.normal_ids()
        if self.config.include_bu_king and round_number >= 3:
            order.append(BU_KING_ID)
        self.rng.shuffle(order)
        return order

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
        path = self.forward_path(source, context.movement)
        context.group = list(group)
        context.path = list(path)
        if self.path_passes_start(path):
            self.state.finished_group = list(reversed(group))
            self.state.finished_position = 0
            self.state.place_group(group, 0)
            self.after_any_move(group, path, dango_id)
            return
        self.move_group_to(group, path[-1], actor_id=dango_id, path=path)

        if dango.skill and hasattr(dango.skill, "after_move"):
            dango.skill.after_move(dango, self.state, context, self.rng, self)

    def move_group_to(
        self,
        group: list[str],
        destination: int,
        *,
        actor_id: str | None = None,
        path: list[int] | None = None,
        bottom: bool = False,
    ) -> None:
        destination = self.normalize_position(destination)
        self.state.remove_ids(group)
        self.state.place_group(group, destination, bottom=bottom)
        self.resolve_tiles(group, destination)
        self.after_any_move(group, path or [destination], actor_id)

    def after_any_move(
        self,
        group: list[str],
        path: list[int],
        actor_id: str | None,
    ) -> None:
        return None

    def bu_king_group(self) -> list[str]:
        position = self.state.position_of(BU_KING_ID)
        stack = self.state.stack_at(position)
        return stack[stack.index(BU_KING_ID):]

    def take_bu_king_turn(self, base_roll: int | None = None) -> None:
        if not self.config.include_bu_king or self.state.round_number < 3:
            return

        roll = (
            int(base_roll)
            if base_roll is not None
            else int(self.rng.choice([1, 2, 3, 4, 5, 6]))
        )
        path: list[int] = []
        for _ in range(roll):
            source = self.state.position_of(BU_KING_ID)
            destination = self.previous_position(source)
            carried_group = self.bu_king_group()
            carried_above_bu_king = carried_group[1:]
            destination_stack = self.state.stack_at(destination)

            self.state.remove_ids(carried_group)
            self.state.positions[destination] = [
                BU_KING_ID,
                *destination_stack,
                *carried_above_bu_king,
            ]
            path.append(destination)

        final_position = self.state.position_of(BU_KING_ID)
        final_group = self.bu_king_group()
        self.resolve_tiles(final_group, final_position)
        self.after_any_move(final_group, path, BU_KING_ID)

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
        if self.config.tile_resolution == "single":
            self.resolve_single_tile(group, position)
            return

        self.resolve_chained_tiles(group, position)

    def resolve_single_tile(self, group: list[str], position: int) -> None:
        current = self.normalize_position(position)
        tile = self.config.board.tiles.get(current)
        if tile is None:
            return

        next_position = tile.on_landed(group, current, self.state, self.rng)
        self.apply_tile_movement(group, current, next_position)

    def resolve_chained_tiles(self, group: list[str], position: int) -> None:
        current = position
        for _ in range(self.config.max_tile_depth):
            current = self.normalize_position(current)
            tile = self.config.board.tiles.get(current)
            if tile is None:
                return

            next_position = tile.on_landed(group, current, self.state, self.rng)
            moved_position = self.apply_tile_movement(group, current, next_position)
            if moved_position == current or self.has_finished():
                return

            current = moved_position

        if self.config.board.tiles.get(current) is None:
            return
        raise RuntimeError("tile resolution exceeded maximum depth")

    def apply_tile_movement(
        self,
        group: list[str],
        current: int,
        next_position: int,
    ) -> int:
        if next_position == current:
            return current

        steps = next_position - current
        path = self.forward_path(current, steps) if steps > 0 else []
        if self.path_passes_start(path):
            self.state.remove_ids(group)
            self.state.finished_group = list(reversed(group))
            self.state.finished_position = 0
            self.state.place_group(group, 0)
            return 0

        normalized_position = self.normalize_position(next_position)
        self.state.remove_ids(group)
        self.state.place_group(group, normalized_position)
        return normalized_position

    def has_finished(self) -> bool:
        return self.state.finished_group is not None

    def rankings(self) -> list[str]:
        normal_ids = set(self.normal_ids())
        ordered: list[str] = []

        if self.state.finished_group is not None:
            ordered.extend(
                dango_id
                for dango_id in self.state.finished_group
                if dango_id in normal_ids
            )

        remaining_positions = sorted(
            [
                position
                for position in self.state.positions
            ],
            key=lambda position: self.forward_distance_to_start(position),
        )
        for position in remaining_positions:
            ordered.extend(
                dango_id
                for dango_id in reversed(self.state.stack_at(position))
                if dango_id in normal_ids and dango_id not in ordered
            )

        return ordered

    def forward_distance_to_start(self, position: int) -> int:
        return (self.config.board.finish - position) % self.config.board.finish
