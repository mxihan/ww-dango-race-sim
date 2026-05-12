import pytest

from dango_sim.models import (
    BU_KING_ID,
    Board,
    Dango,
    RaceConfig,
    RaceResult,
    RaceStartingState,
    RaceState,
)


def test_board_accepts_finish_position():
    board = Board(finish=12)

    assert board.finish == 12


def test_board_copies_tiles_on_construction():
    tiles = {3: object()}
    board = Board(finish=12, tiles=tiles)

    tiles[4] = object()

    assert list(board.tiles) == [3]


def test_board_tiles_cannot_be_item_assigned():
    board = Board(finish=12, tiles={3: object()})

    with pytest.raises(TypeError):
        board.tiles[4] = object()


def test_race_state_tracks_bottom_to_top_stacks():
    state = RaceState.initial(["a", "b", "c"], start_position=0)

    assert state.stack_at(0) == ["a", "b", "c"]
    assert state.position_of("b") == 0
    assert state.stack_index("b") == 1


def test_stack_at_returns_copy():
    state = RaceState.initial(["a", "b"], start_position=0)
    stack = state.stack_at(0)

    stack.append("c")

    assert state.stack_at(0) == ["a", "b"]


def test_remove_moving_group_keeps_lower_dango_at_source():
    state = RaceState.initial(["a", "b", "c"], start_position=0)

    group = state.lift_group_from("b")

    assert group == ["b", "c"]
    assert state.stack_at(0) == ["a"]


def test_place_group_on_top_of_destination_stack():
    state = RaceState.initial(["a", "b"], start_position=0)
    state.place_group(["c", "d"], 0)

    assert state.stack_at(0) == ["a", "b", "c", "d"]
    assert state.position_of("d") == 0


def test_config_validation_rejects_duplicate_normal_dango_ids():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[
            Dango(id="same", name="A"),
            Dango(id="same", name="B"),
        ],
    )

    with pytest.raises(ValueError, match="unique"):
        config.validate()


def test_config_validation_rejects_tile_at_or_past_finish():
    config = RaceConfig(
        board=Board(finish=10, tiles={10: object()}),
        participants=[Dango(id="a", name="A")],
    )

    with pytest.raises(ValueError, match="1"):
        config.validate()


def test_config_validation_rejects_tile_at_start():
    config = RaceConfig(
        board=Board(finish=10, tiles={0: object()}),
        participants=[Dango(id="a", name="A")],
    )

    with pytest.raises(ValueError, match="1"):
        config.validate()


def test_config_defaults_to_single_tile_resolution():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="a", name="A")],
    )

    assert config.tile_resolution == "single"
    config.validate()


def test_config_accepts_chain_tile_resolution():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="a", name="A")],
        tile_resolution="chain",
    )

    config.validate()


def test_config_rejects_unknown_tile_resolution():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="a", name="A")],
        tile_resolution="forever",
    )

    with pytest.raises(ValueError, match="tile_resolution"):
        config.validate()


def test_race_state_records_finishing_group():
    state = RaceState.initial(["a", "b"])

    state.finished_group = ["b", "a"]

    assert state.finished_group == ["b", "a"]


def test_race_result_stores_rankings_as_immutable_tuple():
    rankings = ["a", "b"]
    result = RaceResult(winner_id="a", rankings=rankings, rounds=3)

    rankings.append("c")

    assert result.rankings == ("a", "b")
    with pytest.raises(AttributeError):
        result.rankings.append("c")


def test_config_defaults_turn_order_and_no_starting_state():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="a", name="A")],
    )

    assert config.order_direction == "high_first"
    assert config.bu_king_order_faces == "d3"
    assert config.starting_state is None
    config.validate()


def test_config_accepts_low_first_and_d6_bu_king_order_faces():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="a", name="A")],
        order_direction="low_first",
        bu_king_order_faces="d6",
    )

    config.validate()


def test_config_rejects_unknown_order_direction():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="a", name="A")],
        order_direction="sideways",
    )

    with pytest.raises(ValueError, match="order_direction"):
        config.validate()


def test_config_rejects_unknown_bu_king_order_faces():
    config = RaceConfig(
        board=Board(finish=10),
        participants=[Dango(id="a", name="A")],
        bu_king_order_faces="d20",
    )

    with pytest.raises(ValueError, match="bu_king_order_faces"):
        config.validate()


def test_starting_state_copies_positions_and_laps():
    starting_state = RaceStartingState(
        positions={0: ["a"], 4: ["bu_king", "b"]},
        laps_completed={"a": 1, "b": 0},
    )

    assert starting_state.positions[4] == ("bu_king", "b")
    assert starting_state.laps_completed["a"] == 1

    with pytest.raises(TypeError):
        starting_state.positions[0] = ("b",)
