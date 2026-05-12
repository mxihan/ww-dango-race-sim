from dango_sim.engine import RaceEngine
from dango_sim.models import BU_KING_ID, Board, Dango, RaceConfig, RaceState
from dango_sim.tiles import Booster, Inhibitor


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
    engine = RaceEngine(config, rng=FixedRng([3, 1]))

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
    engine = RaceEngine(config, rng=FixedRng([1, 2, 3]))

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


def test_bu_king_is_added_at_finish_and_excluded_from_ranking():
    config = RaceConfig(board=Board(finish=10), participants=[Dango(id="a", name="A")])
    engine = RaceEngine(config, rng=FixedRng([]))

    assert engine.state.stack_at(10) == [BU_KING_ID]
    assert BU_KING_ID not in engine.rankings()


def test_bu_king_starts_acting_on_round_three():
    config = RaceConfig(board=Board(finish=10), participants=[Dango(id="a", name="A")])
    engine = RaceEngine(config, rng=FixedRng([1]))

    engine.state.round_number = 2
    engine.take_bu_king_turn()
    assert engine.state.stack_at(10) == [BU_KING_ID]

    engine.state.round_number = 3
    engine.take_bu_king_turn()
    assert engine.state.stack_at(9) == [BU_KING_ID]


def test_bu_king_contacts_stack_and_carries_it_backward_from_bottom():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
    )
    engine = RaceEngine(config, rng=FixedRng([3]))
    engine.state = RaceState(positions={10: [BU_KING_ID], 7: ["a", "b"]}, round_number=3)

    engine.take_bu_king_turn()

    assert engine.state.stack_at(7) == [BU_KING_ID, "a", "b"]


def test_bu_king_collects_every_stack_crossed_in_encounter_order():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[
            Dango(id="a", name="A"),
            Dango(id="b", name="B"),
            Dango(id="c", name="C"),
        ],
    )
    engine = RaceEngine(config, rng=FixedRng([6]))
    engine.state = RaceState(
        positions={10: [BU_KING_ID], 8: ["a"], 5: ["b", "c"]},
        round_number=3,
    )

    engine.take_bu_king_turn()

    assert engine.state.stack_at(8) == []
    assert engine.state.stack_at(5) == []
    assert engine.state.stack_at(4) == [BU_KING_ID, "a", "b", "c"]


def test_bu_king_resolves_tiles_after_collecting_crossed_stacks():
    config = RaceConfig(
        board=Board(finish=10, tiles={7: Booster()}),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
    )
    engine = RaceEngine(config, rng=FixedRng([3]))
    engine.state = RaceState(positions={10: [BU_KING_ID], 7: ["a", "b"]}, round_number=3)

    engine.take_bu_king_turn()

    assert engine.state.stack_at(7) == []
    assert engine.state.stack_at(8) == [BU_KING_ID, "a", "b"]


def test_bu_king_teleports_to_finish_when_separated_from_last_place():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
    )
    engine = RaceEngine(config, rng=FixedRng([]))
    engine.state = RaceState(
        positions={10: [BU_KING_ID], 2: ["a"], 6: ["b"]},
        round_number=3,
    )

    engine.end_round()

    assert engine.state.stack_at(10) == [BU_KING_ID]


def test_bu_king_stays_when_it_can_still_reach_last_place():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
    )
    engine = RaceEngine(config, rng=FixedRng([]))
    engine.state = RaceState(
        positions={5: [BU_KING_ID], 2: ["a"], 6: ["b"]},
        round_number=3,
    )

    engine.end_round()

    assert engine.state.stack_at(5) == [BU_KING_ID]


def test_bu_king_teleports_after_passing_last_place_toward_start():
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

    assert engine.state.stack_at(10) == [BU_KING_ID]


def test_bu_king_stays_when_on_last_place_stack():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
    )
    engine = RaceEngine(config, rng=FixedRng([]))
    engine.state = RaceState(positions={2: [BU_KING_ID, "a"], 6: ["b"]}, round_number=3)

    engine.end_round()

    assert engine.state.stack_at(2) == [BU_KING_ID, "a"]


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


def test_bu_king_included_in_shuffled_turn_order():
    """Bu King participates in the random turn order each round."""
    config = RaceConfig(
        board=Board(finish=3),
        participants=[Dango(id="a", name="A")],
    )
    rng = OrderRecordingRng([3])
    engine = RaceEngine(config, rng=rng)

    engine.run()

    assert len(rng.shuffled_orders) >= 1
    for order in rng.shuffled_orders:
        assert "a" in order
        assert BU_KING_ID in order


def test_bu_king_absent_from_turn_order_when_excluded():
    """Bu King is not in the turn order when include_bu_king=False."""
    config = RaceConfig(
        board=Board(finish=3),
        participants=[Dango(id="a", name="A")],
        include_bu_king=False,
    )
    rng = OrderRecordingRng([3])
    engine = RaceEngine(config, rng=rng)

    engine.run()

    for order in rng.shuffled_orders:
        assert "a" in order
        assert BU_KING_ID not in order


def test_race_completes_with_bu_king_in_shuffled_order():
    """Full race with Bu King in shuffled order produces valid results."""
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
    )
    rolls = [3, 1, 3, 3, 1, 3, 3, 1, 3, 3, 1, 3]
    rng = OrderRecordingRng(rolls)
    engine = RaceEngine(config, rng=rng)

    result = engine.run()

    assert result.winner_id in ("a", "b")
    assert len(result.rankings) == 2
    assert BU_KING_ID not in result.rankings
