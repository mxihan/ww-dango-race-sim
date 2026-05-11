import pytest

from dango_sim.models import Board, Dango, RaceConfig, RaceResult
from dango_sim.simulation import SimulationSummary, run_simulations


class StubEngine:
    results = [
        RaceResult(winner_id="a", rankings=["a", "b"], rounds=1),
        RaceResult(winner_id="b", rankings=["b", "a"], rounds=2),
        RaceResult(winner_id="a", rankings=["a", "b"], rounds=3),
    ]

    def __init__(self, config, rng):
        self.config = config
        self.rng = rng

    def run(self):
        return self.results.pop(0)


def test_run_simulations_counts_wins_and_win_rates():
    StubEngine.results = [
        RaceResult(winner_id="a", rankings=["a", "b"], rounds=1),
        RaceResult(winner_id="b", rankings=["b", "a"], rounds=2),
        RaceResult(winner_id="a", rankings=["a", "b"], rounds=3),
    ]

    summary = run_simulations(
        config_factory=lambda: RaceConfig(
            board=Board(finish=10),
            participants=[Dango(id="a", name="A"), Dango(id="b", name="B")],
            include_bu_king=False,
        ),
        runs=3,
        seed=7,
        engine_cls=StubEngine,
    )

    assert summary == SimulationSummary(
        runs=3,
        wins={"a": 2, "b": 1},
        win_rates={"a": 2 / 3, "b": 1 / 3},
        average_rank={"a": 4 / 3, "b": 5 / 3},
        average_rounds=2.0,
    )


def test_run_simulations_calls_config_factory_once_per_run():
    class RecordingEngine:
        configs = []

        def __init__(self, config, rng):
            self.config = config
            self.rng = rng
            self.configs.append(config)

        def run(self):
            return RaceResult(
                winner_id=self.config.participants[0].id,
                rankings=[dango.id for dango in self.config.participants],
                rounds=self.config.board.finish,
            )

    configs = [
        RaceConfig(
            board=Board(finish=4),
            participants=[Dango(id="a", name="A")],
            include_bu_king=False,
        ),
        RaceConfig(
            board=Board(finish=6),
            participants=[Dango(id="b", name="B"), Dango(id="c", name="C")],
            include_bu_king=False,
        ),
    ]
    RecordingEngine.configs = []

    summary = run_simulations(
        config_factory=lambda: configs.pop(0),
        runs=2,
        engine_cls=RecordingEngine,
    )

    assert [config.board.finish for config in RecordingEngine.configs] == [4, 6]
    assert [
        [dango.id for dango in config.participants]
        for config in RecordingEngine.configs
    ] == [["a"], ["b", "c"]]
    assert summary.runs == 2


def test_run_simulations_rejects_non_positive_runs():
    with pytest.raises(ValueError, match="positive"):
        run_simulations(config_factory=lambda: RaceConfig(Board(1), []), runs=0)
