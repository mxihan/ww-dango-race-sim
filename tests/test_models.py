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


def test_config_validation_rejects_tile_outside_board():
    config = RaceConfig(
        board=Board(finish=10, tiles={11: object()}),
        participants=[Dango(id="a", name="A")],
    )

    with pytest.raises(ValueError, match="within"):
        config.validate()


def test_race_result_stores_rankings_as_immutable_tuple():
    rankings = ["a", "b"]
    result = RaceResult(winner_id="a", rankings=rankings, rounds=3)

    rankings.append("c")

    assert result.rankings == ("a", "b")
    with pytest.raises(AttributeError):
        result.rankings.append("c")
