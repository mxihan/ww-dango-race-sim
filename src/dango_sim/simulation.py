from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable

from dango_sim.engine import RaceEngine
from dango_sim.models import RaceConfig


@dataclass(frozen=True)
class SimulationSummary:
    runs: int
    wins: dict[str, int]
    win_rates: dict[str, float]
    average_rank: dict[str, float]
    average_rounds: float


def run_simulations(
    *,
    config_factory: Callable[[], RaceConfig],
    runs: int,
    seed: int | None = None,
    engine_cls=RaceEngine,
) -> SimulationSummary:
    if runs <= 0:
        raise ValueError("runs must be positive")

    master_rng = random.Random(seed)
    wins: dict[str, int] = {}
    rank_totals: dict[str, int] = {}
    rank_counts: dict[str, int] = {}
    total_rounds = 0

    for _ in range(runs):
        config = config_factory()
        engine = engine_cls(config, random.Random(master_rng.randrange(2**63)))
        result = engine.run()

        wins[result.winner_id] = wins.get(result.winner_id, 0) + 1
        total_rounds += result.rounds

        for rank, dango_id in enumerate(result.rankings, start=1):
            wins.setdefault(dango_id, 0)
            rank_totals[dango_id] = rank_totals.get(dango_id, 0) + rank
            rank_counts[dango_id] = rank_counts.get(dango_id, 0) + 1

    win_rates = {dango_id: count / runs for dango_id, count in wins.items()}
    average_rank = {
        dango_id: rank_totals[dango_id] / rank_counts[dango_id]
        for dango_id in rank_totals
    }

    return SimulationSummary(
        runs=runs,
        wins=wins,
        win_rates=win_rates,
        average_rank=average_rank,
        average_rounds=total_rounds / runs,
    )
