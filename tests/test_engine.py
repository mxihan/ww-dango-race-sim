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


def test_ranking_uses_nearest_to_finish_then_top_to_bottom():
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


def test_ranking_uses_top_to_bottom_for_finished_stacks():
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
    engine.state = RaceState(positions={10: ["b", "c"], 4: ["a"]})

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


def test_engine_resolves_tile_chaining():
    config = RaceConfig(
        board=Board(finish=10, tiles={2: Booster(), 3: Booster()}),
        participants=[Dango(id="a", name="A")],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng([2]))

    engine.take_turn("a")

    assert engine.state.stack_at(4) == ["a"]


def test_engine_allows_tile_chain_to_end_at_max_depth():
    config = RaceConfig(
        board=Board(finish=10, tiles={2: Booster(), 3: Booster()}),
        participants=[Dango(id="a", name="A")],
        include_bu_king=False,
        max_tile_depth=2,
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

    assert engine.state.stack_at(7) == []
    assert engine.state.stack_at(4) == [BU_KING_ID, "a", "b"]


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


def test_bu_king_stays_when_on_last_place_stack():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
    )
    engine = RaceEngine(config, rng=FixedRng([]))
    engine.state = RaceState(positions={2: [BU_KING_ID, "a"], 6: ["b"]}, round_number=3)

    engine.end_round()

    assert engine.state.stack_at(2) == [BU_KING_ID, "a"]
