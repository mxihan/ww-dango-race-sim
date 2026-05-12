import json

from dango_sim.models import RaceStartingState
from dango_sim.state_io import dump_starting_state, load_starting_state


def test_load_starting_state_converts_positions_to_ints_and_stacks_to_tuples(tmp_path):
    path = tmp_path / "state.json"
    path.write_text(
        json.dumps(
            {
                "positions": {"0": ["a"], "7": ["bu_king", "b"]},
                "laps_completed": {"a": 1, "b": 0},
            }
        ),
        encoding="utf-8",
    )

    state = load_starting_state(path)

    assert state == RaceStartingState(
        positions={0: ("a",), 7: ("bu_king", "b")},
        laps_completed={"a": 1, "b": 0},
    )


def test_dump_starting_state_writes_editable_json(tmp_path):
    path = tmp_path / "state.json"
    state = RaceStartingState(
        positions={3: ["a", "b"]},
        laps_completed={"a": 1, "b": 0},
    )

    dump_starting_state(state, path)

    assert json.loads(path.read_text(encoding="utf-8")) == {
        "positions": {"3": ["a", "b"]},
        "laps_completed": {"a": 1, "b": 0},
    }
