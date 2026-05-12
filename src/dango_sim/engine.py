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
    engine: object | None = None


class RaceEngine:
    def __init__(self, config: RaceConfig, rng: random.Random | None = None):
        config.validate()
        self.config = config
        self.rng = rng or random.Random()
        self.participants = deepcopy(config.participants)
        self.dangos: dict[str, Dango] = {
            dango.id: dango for dango in self.participants
        }
        self.skip_turns_this_round: set[str] = set()
        self.force_last_next_round_ids: set[str] = set()
        self.force_last_this_round_ids: set[str] = set()
        if self.config.starting_state is None:
            self.state = RaceState.empty(self.normal_ids())
        else:
            self.state = RaceState.from_starting_state(self.config.starting_state)
        if self.config.include_bu_king:
            self.dangos[BU_KING_ID] = Dango(
                id=BU_KING_ID,
                name="Bu King",
                is_special=True,
            )
            if not self.state.is_entered(BU_KING_ID):
                self.state.place_group([BU_KING_ID], 0, bottom=True)

    def run(self) -> RaceResult:
        for round_number in range(1, self.config.max_rounds + 1):
            self.state.round_number = round_number
            self.start_round(round_number)
            actors = [
                actor_id
                for actor_id in self.actors_for_round(round_number)
                if actor_id not in self.skip_turns_this_round
            ]
            self._round_order_actors = actors
            try:
                order = self.build_round_order(round_number)
            finally:
                del self._round_order_actors
            round_rolls = self.roll_round_values(actors)

            for dango_id in order:
                if self.has_finished():
                    break
                if dango_id in self.skip_turns_this_round:
                    continue
                if dango_id == BU_KING_ID:
                    self.take_bu_king_turn(base_roll=round_rolls[dango_id])
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

    def start_round(self, round_number: int) -> None:
        self.force_last_this_round_ids = set(self.force_last_next_round_ids)
        self.force_last_next_round_ids.clear()
        self.skip_turns_this_round.clear()
        for dango in self.participants:
            if dango.skill and hasattr(dango.skill, "on_round_start"):
                dango.skill.on_round_start(dango, self.state, self, self.rng)

    def force_last_next_round(self, dango_id: str) -> None:
        if dango_id in self.normal_ids():
            self.force_last_next_round_ids.add(dango_id)

    def skip_turn_this_round(self, dango_id: str) -> None:
        if dango_id in self.normal_ids():
            self.skip_turns_this_round.add(dango_id)

    def apply_forced_last(self, order: list[str]) -> list[str]:
        forced = [
            dango_id
            for dango_id in order
            if dango_id in self.force_last_this_round_ids
        ]
        normal = [
            dango_id
            for dango_id in order
            if dango_id not in self.force_last_this_round_ids
        ]
        return normal + forced

    def actors_for_round(self, round_number: int) -> list[str]:
        actors = self.normal_ids()
        if self.config.include_bu_king and round_number >= 3:
            actors.append(BU_KING_ID)
        return actors

    def build_round_order(
        self,
        round_number: int,
        actors: Iterable[str] | None = None,
    ) -> list[str]:
        if actors is None:
            actors = getattr(
                self,
                "_round_order_actors",
                self.actors_for_round(round_number),
            )
        return self.apply_forced_last(
            self.order_actors(
                self.roll_order_values(
                    actors,
                    round_number=round_number,
                )
            )
        )

    def roll_order_values(
        self,
        actors: Iterable[str],
        *,
        round_number: int,
    ) -> dict[str, int]:
        return {
            actor_id: self.roll_bu_king_order()
            if actor_id == BU_KING_ID
            else self.roll_for_order(actor_id)
            for actor_id in actors
        }

    def order_actors(self, order_rolls: dict[str, int]) -> list[str]:
        reverse = self.config.order_direction == "high_first"
        ordered: list[str] = []
        for roll in sorted(set(order_rolls.values()), reverse=reverse):
            group = [
                actor_id
                for actor_id, value in order_rolls.items()
                if value == roll
            ]
            self.rng.shuffle(group)
            ordered.extend(group)
        return ordered

    def roll_bu_king_order(self) -> int:
        faces = [1, 2, 3] if self.config.bu_king_order_faces == "d3" else [1, 2, 3, 4, 5, 6]
        return int(self.rng.choice(faces))

    def roll_for_order(self, dango_id: str) -> int:
        return self.roll_with_dice_skill(dango_id)

    def roll_for_movement(self, dango_id: str) -> int:
        return self.roll_with_dice_skill(dango_id)

    def roll_with_dice_skill(self, dango_id: str) -> int:
        dango = self.dangos[dango_id]
        faces = [1, 2, 3]
        if dango.skill and hasattr(dango.skill, "roll_faces"):
            faces = list(dango.skill.roll_faces(dango, self.state))
        if dango.skill and hasattr(dango.skill, "roll"):
            return int(dango.skill.roll(dango, self.state, self.rng))
        return int(self.rng.choice(faces))

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

    def roll_round_values(self, actors: Iterable[str]) -> dict[str, int]:
        rolls: dict[str, int] = {}
        for actor_id in actors:
            if actor_id == BU_KING_ID:
                rolls[actor_id] = int(self.rng.choice([1, 2, 3, 4, 5, 6]))
            else:
                rolls[actor_id] = self.roll_for_movement(actor_id)
        return rolls

    def roll_for(self, dango_id: str) -> int:
        return self.roll_for_movement(dango_id)

    def take_turn(
        self,
        dango_id: str,
        *,
        base_roll: int | None = None,
        round_rolls: dict[str, int] | None = None,
    ) -> None:
        if dango_id in self.skip_turns_this_round:
            return
        if base_roll is None:
            base_roll = self.roll_for(dango_id)

        context = TurnContext(
            round_rolls=round_rolls or {dango_id: base_roll},
            base_roll=base_roll,
            movement=base_roll,
            engine=self,
        )
        dango = self.dangos[dango_id]
        if dango.skill and hasattr(dango.skill, "on_turn_start"):
            dango.skill.on_turn_start(dango, self.state, context, self.rng, self)
            if dango_id in self.skip_turns_this_round:
                return
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

        if not self.state.is_entered(dango_id):
            self.state.enter_at_start(dango_id)

        source = self.state.position_of(dango_id)
        group = self.state.lift_group_from(dango_id)
        path = self.forward_path(source, context.movement)
        context.group = list(group)
        context.path = list(path)
        if self.path_passes_start(path):
            self.finish_group_at_start(group)
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
        context = TurnContext(
            round_rolls={},
            base_roll=0,
            movement=0,
            path=list(path),
            group=list(group),
        )
        for dango in self.participants:
            if dango.skill and hasattr(dango.skill, "after_any_move"):
                dango.skill.after_any_move(dango, self.state, context, self.rng, self)

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
        if not self.config.include_bu_king or self.state.round_number < 3:
            return
        if self.bu_king_has_dango_above():
            return
        if not self.has_normal_dango_ahead_of_bu_king():
            self.state.remove_ids([BU_KING_ID])
            self.state.place_group([BU_KING_ID], 0, bottom=True)

    def bu_king_has_dango_above(self) -> bool:
        position = self.state.position_of(BU_KING_ID)
        stack = self.state.stack_at(position)
        index = stack.index(BU_KING_ID)
        return any(
            dango_id in self.normal_ids()
            for dango_id in stack[index + 1:]
        )

    def has_normal_dango_ahead_of_bu_king(self) -> bool:
        normal_ids = set(self.normal_ids())
        position = self.state.position_of(BU_KING_ID)
        current = position
        while current != 0:
            current = self.previous_position(current)
            if any(
                dango_id in normal_ids
                for dango_id in self.state.stack_at(current)
            ):
                return True
        return False

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
            self.finish_group_at_start(group)
            return 0

        normalized_position = self.normalize_position(next_position)
        self.state.remove_ids(group)
        self.state.place_group(group, normalized_position)
        return normalized_position

    def has_finished(self) -> bool:
        return self.state.finished_group is not None

    def rankings(self) -> list[str]:
        return self._rankings(include_specials=False)

    def rankings_with_specials(self) -> list[str]:
        return self._rankings(include_specials=True)

    def _rankings(self, *, include_specials: bool) -> list[str]:
        normal_ids = set(self.normal_ids())
        ranked_ids = set(normal_ids)
        if (
            include_specials
            and self.config.include_bu_king
            and self.state.is_entered(BU_KING_ID)
        ):
            ranked_ids.add(BU_KING_ID)
        ordered: list[str] = []

        if self.state.finished_group is not None:
            ordered.extend(
                dango_id
                for dango_id in self.state.finished_group
                if dango_id in ranked_ids
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
                if dango_id in ranked_ids and dango_id not in ordered
            )

        unentered = [
            dango_id for dango_id in normal_ids
            if dango_id not in ordered
        ]
        if unentered:
            ordered.extend(unentered)

        return ordered

    def win_lap_threshold(self) -> int:
        return 2 if self.config.starting_state is not None else 1

    def finish_group_at_start(self, group: list[str]) -> None:
        normal_ids = set(self.normal_ids())
        self.state.remove_ids(group)
        self.state.place_group(group, 0)
        for dango_id in group:
            if dango_id in normal_ids:
                self.state.laps_completed[dango_id] = (
                    self.state.laps_completed.get(dango_id, 0) + 1
                )

        threshold = self.win_lap_threshold()
        if any(
            dango_id in normal_ids
            and self.state.laps_completed.get(dango_id, 0) >= threshold
            for dango_id in group
        ):
            self.state.finished_group = [
                dango_id for dango_id in reversed(group) if dango_id in normal_ids
            ]
            self.state.finished_position = 0

    def forward_distance_to_start(self, position: int) -> int:
        return (self.config.board.finish - position) % self.config.board.finish

    def nearest_normal_dango_ahead(
        self,
        position: int,
        *,
        exclude_id: str | None = None,
    ) -> tuple[int, str] | None:
        normal_ids = set(self.normal_ids())
        if exclude_id is not None:
            normal_ids.discard(exclude_id)

        current = self.normalize_position(position)
        while True:
            current = self.next_position(current)
            if current == 0:
                return None
            for dango_id in reversed(self.state.stack_at(current)):
                if dango_id in normal_ids:
                    return current, dango_id
