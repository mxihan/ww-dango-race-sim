from dango_sim.engine import RaceEngine
from dango_sim.models import Board, Dango, RaceConfig, RaceState


class FixedRng:
    def __init__(self, choices):
        self.choices = list(choices)

    def shuffle(self, values):
        return None

    def choice(self, values):
        return self.choices.pop(0)

    def random(self):
        return 0.99


def test_normal_dango_reaching_finish_ends_race_immediately():
    config = RaceConfig(
        board=Board(finish=3),
        participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
        include_bu_king=False,
    )
    engine = RaceEngine(config, rng=FixedRng([3]))

    result = engine.run()

    assert result.winner_id == "a"
    assert tuple(result.rankings) == ("a", "b")
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
