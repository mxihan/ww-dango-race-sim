import pytest

from dango_sim.models import Board, Dango, RaceConfig, RaceResult, RaceState


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
