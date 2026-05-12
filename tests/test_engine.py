import random

from dango_sim.engine import RaceEngine
from dango_sim.models import (
    BU_KING_ID,
    Board,
    Dango,
    RaceConfig,
    RaceStartingState,
    RaceState,
)
from dango_sim.tiles import Booster, Inhibitor, SpaceTimeRift


class FixedRng:
    def __init__(self, choices):
        self.choices = list(choices)

    def shuffle(self, values):
        return None

    def choice(self, values):
        return self.choices.pop(0)

    def random(self):
        return 0.99


class RecordingRollsSkill:
    def __init__(self):
        self.observed_rolls = []

    def modify_roll(self, dango, movement, state, context, rng):
        self.observed_rolls.append(sorted(context.round_rolls.values()))
        return movement


def test_normal_dango_reaching_finish_ends_race_immediately():
    config = RaceConfig(
        board=Board(finish=3),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng([1, 3, 1, 3]))

    result = engine.run()

    assert result.winner_id == "b"
    assert tuple(result.rankings) == ("b", "a")
    assert result.rounds == 1


def test_normal_dango_finishes_when_forward_path_passes_start():
    config = RaceConfig(
        board=Board(finish=5),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
        include_bu_king=False,
    )
    engine = RaceEngine(config)
    engine.state.positions = {3: ["a"], 1: ["b"]}

    engine.take_turn("a", base_roll=2, round_rolls={"a": 2, "b": 1})

    assert engine.has_finished()
    assert engine.state.finished_group == ["a"]
    assert engine.rankings() == ["a", "b"]


def test_normal_dango_wraps_without_finishing_when_start_not_passed():
    config = RaceConfig(
        board=Board(finish=5),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
        include_bu_king=False,
    )
    engine = RaceEngine(config)
    engine.state.positions = {1: ["a"], 3: ["b"]}

    engine.take_turn("a", base_roll=2, round_rolls={"a": 2, "b": 1})

    assert not engine.has_finished()
    assert engine.state.positions == {3: ["b", "a"]}
    assert engine.rankings() == ["a", "b"]


def test_lower_dango_carries_dango_above_it():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[
            Dango(id="a", name="A"),
            Dango(id="b", name="B"),
            Dango(id="c", name="C"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng([2]))
    engine.state = RaceState.initial(["a", "b", "c"])

    engine.take_turn("b")

    assert engine.state.stack_at(0) == ["a"]
    assert engine.state.stack_at(2) == ["b", "c"]


def test_moving_group_lands_on_top_of_destination_stack():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[
            Dango(id="a", name="A"),
            Dango(id="b", name="B"),
            Dango(id="c", name="C"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng([2]))
    engine.state = RaceState(positions={0: ["a", "b"], 2: ["c"]})

    engine.take_turn("a")

    assert engine.state.stack_at(2) == ["c", "a", "b"]


def test_ranking_uses_forward_distance_to_start_and_top_to_bottom():
    config = RaceConfig(
        board=Board(finish=8),
        participants=[
            Dango(id="a", name="A"),
            Dango(id="b", name="B"),
            Dango(id="c", name="C"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config)
    engine.state.positions = {6: ["a"], 7: ["b", "c"], 2: []}

    assert engine.rankings() == ["c", "b", "a"]


def test_ranking_uses_actual_stack_order_for_same_position():
    config = RaceConfig(
        board=Board(finish=5),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
        include_bu_king=False,
    )
    engine = RaceEngine(config)
    engine.state.positions = {1: ["a"], 3: ["b"]}

    engine.take_turn("a", base_roll=2, round_rolls={"a": 2, "b": 1})

    assert engine.state.positions == {3: ["b", "a"]}
    assert engine.rankings() == ["a", "b"]


def test_ranking_treats_start_as_zero_forward_distance():
    config = RaceConfig(
        board=Board(finish=8),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
        include_bu_king=False,
    )
    engine = RaceEngine(config)
    engine.state.positions = {0: ["a"], 7: ["b"]}

    assert engine.rankings() == ["a", "b"]


def test_ranking_uses_nearest_to_start_then_top_to_bottom():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[
            Dango(id="a", name="A"),
            Dango(id="b", name="B"),
            Dango(id="c", name="C"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng([]))
    engine.state = RaceState(positions={4: ["a"], 7: ["b", "c"]})

    assert engine.rankings() == ["c", "b", "a"]


def test_ranking_uses_recorded_finished_group_before_remaining_dangos():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[
            Dango(id="a", name="A"),
            Dango(id="b", name="B"),
            Dango(id="c", name="C"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng([]))
    engine.state = RaceState(positions={0: ["b", "c"], 4: ["a"]})
    engine.state.finished_group = ["c", "b"]
    engine.state.finished_position = 0

    assert engine.rankings() == ["c", "b", "a"]


def test_round_rolls_are_materialized_before_first_turn():
    skill = RecordingRollsSkill()
    config = RaceConfig(
        board=Board(finish=1),
        participants=[
            Dango(id="a", name="A", skill=skill),
            Dango(id="b", name="B"),
            Dango(id="c", name="C"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng([1, 1, 1, 1, 2, 3]))

    engine.run()

    assert engine.dangos["a"].skill.observed_rolls == [[1, 2, 3]]
    assert skill.observed_rolls == []


def test_engine_forward_path_wraps_around_finish():
    config = RaceConfig(
        board=Board(finish=5),
        participants=[Dango(id="a", name="A")],
        include_bu_king=False,
    )
    engine = RaceEngine(config)

    assert engine.forward_path(3, 4) == [4, 0, 1, 2]
    assert engine.path_passes_start(engine.forward_path(3, 4))


def test_engine_backward_path_wraps_around_start():
    config = RaceConfig(
        board=Board(finish=5),
        participants=[Dango(id="a", name="A")],
        include_bu_king=False,
    )
    engine = RaceEngine(config)

    assert engine.backward_path(1, 3) == [0, 4, 3]


def test_engine_resolves_tile_chaining():
    config = RaceConfig(
        board=Board(finish=10, tiles={2: Booster(), 3: Booster()}),
        participants=[Dango(id="a", name="A")],
        include_bu_king=False,
        tile_resolution="chain",
    )
    engine = RaceEngine(config, rng=FixedRng([2]))

    engine.take_turn("a")

    assert engine.state.stack_at(4) == ["a"]


def test_single_tile_resolution_does_not_chain_by_default():
    config = RaceConfig(
        board=Board(finish=8, tiles={2: Booster(), 3: Booster()}),
        participants=[Dango(id="a", name="A")],
        include_bu_king=False,
    )
    engine = RaceEngine(config)
    engine.state.positions = {1: ["a"]}

    engine.take_turn("a", base_roll=1, round_rolls={"a": 1})

    assert engine.state.position_of("a") == 3


def test_chain_tile_resolution_remains_opt_in():
    config = RaceConfig(
        board=Board(finish=8, tiles={2: Booster(), 3: Booster()}),
        participants=[Dango(id="a", name="A")],
        include_bu_king=False,
        tile_resolution="chain",
    )
    engine = RaceEngine(config)
    engine.state.positions = {1: ["a"]}

    engine.take_turn("a", base_roll=1, round_rolls={"a": 1})

    assert engine.state.position_of("a") == 4


def test_chain_tile_resolution_wraps_tile_movement():
    config = RaceConfig(
        board=Board(finish=5, tiles={4: Booster()}),
        participants=[Dango(id="a", name="A")],
        include_bu_king=False,
    )
    engine = RaceEngine(config)
    engine.state.positions = {3: ["a"]}

    engine.take_turn("a", base_roll=1, round_rolls={"a": 1})

    assert engine.has_finished()


def test_booster_tile_finishes_when_forward_path_passes_start():
    config = RaceConfig(
        board=Board(finish=5, tiles={4: Booster()}),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
        include_bu_king=False,
    )
    engine = RaceEngine(config)
    engine.state.positions = {3: ["a"], 1: ["b"]}

    engine.take_turn("a", base_roll=1, round_rolls={"a": 1, "b": 1})

    assert engine.has_finished()
    assert engine.state.finished_group == ["a"]
    assert engine.state.finished_position == 0
    assert engine.state.positions == {1: ["b"], 0: ["a"]}
    assert 5 not in engine.state.positions


def test_inhibitor_tile_wraps_backward_without_finishing():
    config = RaceConfig(
        board=Board(finish=5, tiles={1: Inhibitor(steps=2)}),
        participants=[Dango(id="a", name="A")],
        include_bu_king=False,
    )
    engine = RaceEngine(config)

    engine.take_turn("a", base_roll=1, round_rolls={"a": 1})

    assert not engine.has_finished()
    assert engine.state.positions == {4: ["a"]}
    assert -1 not in engine.state.positions


def test_engine_allows_tile_chain_to_end_at_max_depth():
    config = RaceConfig(
        board=Board(finish=10, tiles={2: Booster(), 3: Booster()}),
        participants=[Dango(id="a", name="A")],
        include_bu_king=False,
        max_tile_depth=2,
        tile_resolution="chain",
    )
    engine = RaceEngine(config, rng=FixedRng([2]))

    engine.take_turn("a")

    assert engine.state.stack_at(4) == ["a"]


def test_engine_stops_infinite_tile_loop():
    config = RaceConfig(
        board=Board(finish=10, tiles={2: Booster(), 3: Inhibitor()}),
        participants=[Dango(id="a", name="A")],
        include_bu_king=False,
        max_tile_depth=3,
        tile_resolution="chain",
    )
    engine = RaceEngine(config, rng=FixedRng([2]))

    try:
        engine.take_turn("a")
    except RuntimeError as exc:
        assert "tile resolution" in str(exc)
    else:
        raise AssertionError("expected tile loop guard")


def test_bu_king_starts_at_zero_and_is_excluded_from_ranking():
    config = RaceConfig(board=Board(finish=10), participants=[Dango(id="a", name="A")])
    engine = RaceEngine(config)

    assert engine.state.position_of(BU_KING_ID) == 0
    assert BU_KING_ID not in engine.rankings()


def test_round_order_excludes_bu_king_before_round_three():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
    )
    engine = RaceEngine(config, random.Random(1))

    assert BU_KING_ID not in engine.build_round_order(1)
    assert BU_KING_ID not in engine.build_round_order(2)
    assert BU_KING_ID in engine.build_round_order(3)


def test_bu_king_turn_is_noop_before_round_three():
    config = RaceConfig(
        board=Board(finish=8),
        participants=[Dango(id="a", name="A")],
    )
    engine = RaceEngine(config)
    engine.state.round_number = 2
    engine.state.positions = {0: [BU_KING_ID], 7: ["a"]}

    engine.take_bu_king_turn(base_roll=1)

    assert engine.state.positions == {0: [BU_KING_ID], 7: ["a"]}


def test_bu_king_starts_moving_on_round_three():
    config = RaceConfig(
        board=Board(finish=8),
        participants=[Dango(id="a", name="A")],
    )
    engine = RaceEngine(config)
    engine.state.round_number = 3
    engine.state.positions = {0: [BU_KING_ID], 7: ["a"]}

    engine.take_bu_king_turn(base_roll=1)

    assert engine.state.positions == {7: [BU_KING_ID, "a"]}


def test_bu_king_moves_backward_stepwise_and_carries_contacted_dango():
    config = RaceConfig(
        board=Board(finish=8),
        participants=[
            Dango(id="a", name="A"),
            Dango(id="b", name="B"),
            Dango(id="c", name="C"),
        ],
    )
    engine = RaceEngine(config)
    engine.state.round_number = 3
    engine.state.positions = {0: [BU_KING_ID], 7: ["a"], 6: ["b", "c"]}

    engine.take_bu_king_turn(base_roll=2)

    assert engine.state.positions == {6: [BU_KING_ID, "b", "c", "a"]}


def test_bu_king_resolves_movement_tile_after_collecting_stack():
    config = RaceConfig(
        board=Board(finish=8, tiles={6: Booster()}),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
    )
    engine = RaceEngine(config)
    engine.state.round_number = 3
    engine.state.positions = {0: [BU_KING_ID], 7: ["a"], 6: ["b"]}

    engine.take_bu_king_turn(base_roll=2)

    assert engine.state.positions == {7: [BU_KING_ID, "b", "a"]}
    assert all(0 <= position < config.board.finish for position in engine.state.positions)


def test_bu_king_tile_effect_keeps_bu_king_at_bottom():
    config = RaceConfig(
        board=Board(finish=8, tiles={6: SpaceTimeRift()}),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
    )
    engine = RaceEngine(config, random.Random(1))
    engine.state.round_number = 3
    engine.state.positions = {0: [BU_KING_ID], 7: ["a"], 6: ["b"]}

    engine.take_bu_king_turn(base_roll=2)

    assert engine.state.positions[6][0] == BU_KING_ID
    assert sorted(engine.state.positions[6][1:]) == ["a", "b"]


def test_bu_king_wrapping_move_keeps_positions_normalized():
    config = RaceConfig(
        board=Board(finish=8),
        participants=[Dango(id="a", name="A")],
    )
    engine = RaceEngine(config)
    engine.state.round_number = 3
    engine.state.positions = {1: [BU_KING_ID], 7: ["a"]}

    engine.take_bu_king_turn(base_roll=3)

    assert all(0 <= position < config.board.finish for position in engine.state.positions)
    assert engine.state.position_of(BU_KING_ID) == 6
    assert engine.state.positions == {6: [BU_KING_ID, "a"]}


def test_bu_king_returns_to_zero_when_no_dango_ahead_before_start():
    config = RaceConfig(
        board=Board(finish=8),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
    )
    engine = RaceEngine(config)
    engine.state.round_number = 3
    engine.state.positions = {5: [BU_KING_ID], 6: ["a"], 7: ["b"]}

    engine.end_round()

    assert engine.state.position_of(BU_KING_ID) == 0


def test_bu_king_stays_when_dango_ahead_before_start():
    config = RaceConfig(
        board=Board(finish=8),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
    )
    engine = RaceEngine(config)
    engine.state.round_number = 3
    engine.state.positions = {5: [BU_KING_ID], 4: ["a"], 7: ["b"]}

    engine.end_round()

    assert engine.state.position_of(BU_KING_ID) == 5


def test_bu_king_returns_to_zero_after_passing_dangos_toward_start():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
    )
    engine = RaceEngine(config, rng=FixedRng([]))
    engine.state = RaceState(
        positions={1: [BU_KING_ID], 2: ["a"], 6: ["b"]},
        round_number=3,
    )

    engine.end_round()

    assert engine.state.stack_at(0) == [BU_KING_ID]


def test_bu_king_stays_when_carrying_dango_above_it():
    config = RaceConfig(
        board=Board(finish=8),
        participants=[Dango(id="a", name="A")],
    )
    engine = RaceEngine(config)
    engine.state.round_number = 3
    engine.state.positions = {5: [BU_KING_ID, "a"]}

    engine.end_round()

    assert engine.state.position_of(BU_KING_ID) == 5


class OrderRecordingRng:
    """RNG that records what lists were passed to shuffle."""

    def __init__(self, choices):
        self.choices = list(choices)
        self.shuffled_orders: list[list[str]] = []

    def shuffle(self, values):
        self.shuffled_orders.append(list(values))

    def choice(self, values):
        return self.choices.pop(0)

    def random(self):
        return 0.5


class QueueRng:
    def __init__(self, choices, shuffles=None):
        self.choices = list(choices)
        self.shuffles = list(shuffles or [])

    def choice(self, values):
        value = self.choices.pop(0)
        assert value in values
        return value

    def shuffle(self, values):
        if self.shuffles:
            ordered = self.shuffles.pop(0)
            values[:] = ordered

    def random(self):
        return 0.99


def test_round_order_uses_high_first_order_rolls_and_shuffles_ties():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[
            Dango(id="a", name="A"),
            Dango(id="b", name="B"),
            Dango(id="c", name="C"),
        ],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=QueueRng([3, 1, 3], shuffles=[["c", "a"]]))

    order_rolls = engine.roll_order_values(["a", "b", "c"], round_number=1)
    order = engine.order_actors(order_rolls)

    assert order_rolls == {"a": 3, "b": 1, "c": 3}
    assert order == ["c", "a", "b"]


def test_round_order_can_use_low_first_order_rolls():
    config = RaceConfig(
        board=Board(finish=20),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
        include_bu_king=False,
        order_direction="low_first",
    )
    engine = RaceEngine(config, rng=QueueRng([3, 1]))

    order = engine.order_actors(engine.roll_order_values(["a", "b"], round_number=1))

    assert order == ["b", "a"]


def test_bu_king_absent_from_turn_order_when_excluded():
    """Bu King is not in the turn order when include_bu_king=False."""
    config = RaceConfig(
        board=Board(finish=3),
        participants=[Dango(id="a", name="A")],
        include_bu_king=False,
    )
    rng = OrderRecordingRng([3, 3])
    engine = RaceEngine(config, rng=rng)

    engine.run()

    for order in rng.shuffled_orders:
        assert "a" in order
        assert BU_KING_ID not in order


class RoundOrderRecordingEngine(RaceEngine):
    def __init__(self, config, rng):
        super().__init__(config, rng)
        self.round_orders: list[tuple[int, list[str]]] = []

    def build_round_order(self, round_number):
        order = super().build_round_order(round_number)
        self.round_orders.append((round_number, list(order)))
        return order


def test_run_excludes_bu_king_until_round_three_turn_order():
    config = RaceConfig(
        board=Board(finish=50),
        participants=[Dango(id="a", name="A")],
        max_rounds=3,
    )
    engine = RoundOrderRecordingEngine(config, FixedRng([1, 1, 1, 1, 1, 1, 1, 1]))

    try:
        engine.run()
    except RuntimeError as exc:
        assert "race did not finish" in str(exc)
    else:
        raise AssertionError("expected race to reach max_rounds")

    assert engine.round_orders == [
        (1, ["a"]),
        (2, ["a"]),
        (3, ["a", BU_KING_ID]),
    ]


def test_race_completes_with_bu_king_in_shuffled_order():
    """Full race with Bu King in shuffled order produces valid results."""
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
    )
    engine = RaceEngine(config, rng=random.Random(42))

    result = engine.run()

    assert result.winner_id in ("a", "b")
    assert len(result.rankings) == 2
    assert BU_KING_ID not in result.rankings


def test_full_loop_race_returns_valid_result():
    config = RaceConfig(
        board=Board(finish=10, tiles={3: Booster(), 6: Inhibitor()}),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
    )

    result = RaceEngine(config, random.Random(7)).run()

    assert result.winner_id in {"a", "b"}
    assert set(result.rankings) == {"a", "b"}
    assert result.rounds >= 1


def test_without_starting_state_dangos_are_not_on_board_until_first_action():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
        include_bu_king=False,
    )
    engine = RaceEngine(config)

    assert engine.state.positions == {}
    assert not engine.state.is_entered("a")

    engine.take_turn("a", base_roll=2, round_rolls={"a": 2, "b": 1})

    assert engine.state.positions == {2: ["a"]}
    assert not engine.state.is_entered("b")


def test_with_starting_state_preserves_initial_stacks_and_laps():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
        include_bu_king=False,
        starting_state=RaceStartingState(
            positions={4: ["a", "b"]},
            laps_completed={"a": 1, "b": 0},
        ),
    )
    engine = RaceEngine(config)

    assert engine.state.positions == {4: ["a", "b"]}
    assert engine.state.laps_completed == {"a": 1, "b": 0}


def test_first_half_finish_increments_lap_and_places_group_at_zero():
    config = RaceConfig(
        board=Board(finish=5),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
        include_bu_king=False,
    )
    engine = RaceEngine(config)
    engine.state = RaceState(
        positions={4: ["a"], 2: ["b"]},
        laps_completed={"a": 0, "b": 0},
    )

    engine.take_turn("a", base_roll=1, round_rolls={"a": 1, "b": 1})

    assert engine.has_finished()
    assert engine.state.positions[0] == ["a"]
    assert engine.state.laps_completed["a"] == 1


def test_second_half_dango_with_one_lap_needs_one_more_finish():
    config = RaceConfig(
        board=Board(finish=5),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
        include_bu_king=False,
        starting_state=RaceStartingState(
            positions={4: ["a"], 2: ["b"]},
            laps_completed={"a": 1, "b": 0},
        ),
    )
    engine = RaceEngine(config)

    engine.take_turn("a", base_roll=1, round_rolls={"a": 1, "b": 1})

    assert engine.has_finished()
    assert engine.state.laps_completed["a"] == 2


def test_second_half_dango_with_zero_laps_needs_two_finishes():
    config = RaceConfig(
        board=Board(finish=5),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
        include_bu_king=False,
        starting_state=RaceStartingState(
            positions={4: ["a"], 2: ["b"]},
            laps_completed={"a": 0, "b": 1},
        ),
    )
    engine = RaceEngine(config)

    engine.take_turn("a", base_roll=1, round_rolls={"a": 1, "b": 1})

    assert not engine.has_finished()
    assert engine.state.laps_completed["a"] == 1
    assert engine.state.positions[0] == ["a"]


def test_bu_king_in_starting_state_does_not_roll_before_round_three():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="a", name="A")],
        starting_state=RaceStartingState(
            positions={5: [BU_KING_ID], 2: ["a"]},
            laps_completed={"a": 1},
        ),
    )
    engine = RaceEngine(config, rng=QueueRng([3, 2]))

    actors = engine.actors_for_round(1)
    order_rolls = engine.roll_order_values(actors, round_number=1)
    move_rolls = engine.roll_round_values(actors)

    assert actors == ["a"]
    assert order_rolls == {"a": 3}
    assert move_rolls == {"a": 2}
    assert engine.state.position_of(BU_KING_ID) == 5


def test_bu_king_uses_configurable_order_faces_and_fixed_movement_faces_from_round_three():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="a", name="A")],
        bu_king_order_faces="d6",
    )
    engine = RaceEngine(config, rng=QueueRng([2, 6, 1, 5]))

    actors = engine.actors_for_round(3)
    order_rolls = engine.roll_order_values(actors, round_number=3)
    move_rolls = engine.roll_round_values(actors)

    assert actors == ["a", BU_KING_ID]
    assert order_rolls[BU_KING_ID] == 6
    assert move_rolls[BU_KING_ID] == 5
