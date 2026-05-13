from __future__ import annotations

import random
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Callable, Iterable, Mapping

from dango_sim.engine import RaceEngine
from dango_sim.models import RaceConfig


@dataclass(frozen=True)
class SimulationSummary:
    runs: int
    wins: Mapping[str, int]
    win_rates: Mapping[str, float]
    average_rank: Mapping[str, float]
    average_rounds: float
    top_n_rates: Mapping[int, Mapping[str, float]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "wins", MappingProxyType(dict(self.wins)))
        object.__setattr__(
            self,
            "win_rates",
            MappingProxyType(dict(self.win_rates)),
        )
        object.__setattr__(
            self,
            "average_rank",
            MappingProxyType(dict(self.average_rank)),
        )
        object.__setattr__(
            self,
            "top_n_rates",
            MappingProxyType(
                {
                    int(n): MappingProxyType(dict(rates))
                    for n, rates in self.top_n_rates.items()
                }
            ),
        )


def _run_single(args: tuple) -> object:
    config, seed, engine_cls = args
    return engine_cls(config, random.Random(seed)).run()


def run_simulations(
    *,
    config_factory: Callable[[], RaceConfig],
    runs: int,
    seed: int | None = None,
    engine_cls=RaceEngine,
    max_workers: int | None = None,
    top_n: Iterable[int] = (),
) -> SimulationSummary:
    if runs <= 0:
        raise ValueError("runs must be positive")

    master_rng = random.Random(seed)
    top_n_values = sorted({int(value) for value in top_n})
    if any(value <= 0 for value in top_n_values):
        raise ValueError("top_n values must be positive")

    configs = [config_factory() for _ in range(runs)]
    seeds = [master_rng.randrange(2**63) for _ in range(runs)]

    if max_workers is not None and max_workers > 1:
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(
                _run_single,
                [(c, s, engine_cls) for c, s in zip(configs, seeds)],
            ))
    else:
        results = [
            engine_cls(config, random.Random(seed)).run()
            for config, seed in zip(configs, seeds)
        ]

    wins: dict[str, int] = {}
    rank_totals: dict[str, int] = {}
    rank_counts: dict[str, int] = {}
    total_rounds = 0
    top_n_counts: dict[int, dict[str, int]] = {
        value: {} for value in top_n_values
    }

    for result in results:
        wins[result.winner_id] = wins.get(result.winner_id, 0) + 1
        total_rounds += result.rounds

        for rank, dango_id in enumerate(result.rankings, start=1):
            wins.setdefault(dango_id, 0)
            rank_totals[dango_id] = rank_totals.get(dango_id, 0) + rank
            rank_counts[dango_id] = rank_counts.get(dango_id, 0) + 1

        for n in top_n_values:
            for dango_id in result.rankings[:n]:
                top_n_counts[n][dango_id] = top_n_counts[n].get(dango_id, 0) + 1
            for dango_id in result.rankings:
                top_n_counts[n].setdefault(dango_id, 0)

    win_rates = {dango_id: count / runs for dango_id, count in wins.items()}
    average_rank = {
        dango_id: rank_totals[dango_id] / rank_counts[dango_id]
        for dango_id in rank_totals
    }
    top_n_rates = {
        n: {
            dango_id: count / runs
            for dango_id, count in counts.items()
        }
        for n, counts in top_n_counts.items()
    }

    return SimulationSummary(
        runs=runs,
        wins=wins,
        win_rates=win_rates,
        average_rank=average_rank,
        average_rounds=total_rounds / runs,
        top_n_rates=top_n_rates,
    )
