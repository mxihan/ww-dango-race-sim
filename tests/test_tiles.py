from dango_sim.models import BU_KING_ID, RaceState
from dango_sim.tiles import Booster, Inhibitor, SpaceTimeRift


class FixedRng:
    def shuffle(self, values):
        values.reverse()


class RecordingShuffleRng:
    def __init__(self):
        self.seen_values = None

    def shuffle(self, values):
        self.seen_values = list(values)
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


def test_rift_keeps_bu_king_at_bottom_when_present():
    state = RaceState(positions={2: [BU_KING_ID, "a", "b"]})
    rng = RecordingShuffleRng()

    SpaceTimeRift().on_landed(["a", "b"], 2, state, rng)

    assert rng.seen_values == ["a", "b"]
    assert state.positions[2][0] == BU_KING_ID
    assert state.positions[2][1:] == ["b", "a"]
