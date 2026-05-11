from dango_sim.models import RaceState
from dango_sim.tiles import Booster, Inhibitor, SpaceTimeRift


class FixedRng:
    def shuffle(self, values):
        values.reverse()


def test_booster_moves_group_forward_one():
    state = RaceState(positions={2: ["a"]})

    assert Booster().on_landed(["a"], 2, state, FixedRng()) == 3


def test_inhibitor_moves_group_backward_one():
    state = RaceState(positions={2: ["a"]})

    assert Inhibitor().on_landed(["a"], 2, state, FixedRng()) == 1


def test_space_time_rift_reorders_stack_at_position():
    state = RaceState(positions={2: ["a", "b", "c"]})

    destination = SpaceTimeRift().on_landed(["b", "c"], 2, state, FixedRng())

    assert destination == 2
    assert state.stack_at(2) == ["c", "b", "a"]
