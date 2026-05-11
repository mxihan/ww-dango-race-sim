from dango_sim.models import Board


def test_board_accepts_finish_position():
    board = Board(finish=12)

    assert board.finish == 12
