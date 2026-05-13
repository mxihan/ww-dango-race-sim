from __future__ import annotations

import random
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Callable, Iterable, Mapping

from dango_sim.engine import RaceEngine
from dango_sim.listener import RaceTrace, SimulationStats, StatsCollector, TraceRecorder
from dango_sim.models import RaceConfig


@dataclass(frozen=True)
class SimulationSummary:
    runs: int
    wins: Mapping[str, int]
    win_rates: Mapping[str, float]
    average_rank: Mapping[str, float]
    average_rounds: float
    top_n_rates: Mapping[int, Mapping[str, float]] = field(default_factory=dict)
    stats: SimulationStats | None = None
    traces: tuple[RaceTrace, ...] | None = None

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
    config, seed, engine_cls, collect_stats = args
    listeners: list[object] = []
    collector = StatsCollector() if collect_stats else None
    if collector is not None:
        listeners.append(collector)
    engine = engine_cls(config, random.Random(seed), listeners=listeners or None)
    result = engine.run()
    stats_data = None
    if collector is not None:
        stats_data = {
            "skill_triggers": collector.skill_triggers,
            "position_counts": collector.position_counts,
        }
    return result, stats_data


def run_simulations(
    *,
    config_factory: Callable[[], RaceConfig],
    runs: int,
    seed: int | None = None,
    engine_cls=RaceEngine,
    max_workers: int | None = None,
    top_n: Iterable[int] = (),
    stats: bool = True,
    trace: bool = False,
    trace_limit: int | None = None,
) -> SimulationSummary:
    """Run multiple independent race simulations and aggregate results.

    Args:
        max_workers: When set to an integer > 1, uses process-based
            parallelism via ProcessPoolExecutor. ``None`` (default) runs
            sequentially. Each ``config_factory()`` call must produce a
            fresh config with independent skill instances; skill objects
            must not be shared across calls when using parallel execution.
            ``engine_cls`` must be a picklable module-level class when
            ``max_workers > 1``.
    """
    if runs <= 0:
        raise ValueError("runs must be positive")

    master_rng = random.Random(seed)
    top_n_values = sorted({int(value) for value in top_n})
    if any(value <= 0 for value in top_n_values):
        raise ValueError("top_n values must be positive")

    configs = [config_factory() for _ in range(runs)]
    seeds = [master_rng.randrange(2**63) for _ in range(runs)]
    collect_stats_flag = stats

    if max_workers is not None and max_workers > 1:
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            raw_results = list(executor.map(
                _run_single,
                [(c, s, engine_cls, collect_stats_flag) for c, s in zip(configs, seeds)],
            ))
    else:
        raw_results = [
            _run_single((c, s, engine_cls, collect_stats_flag))
            for c, s in zip(configs, seeds)
        ]

    results = [r[0] for r in raw_results]
    stats_datas = [r[1] for r in raw_results if r[1] is not None]

    # Collect traces (sequential, limited)
    trace_results: list[RaceTrace] = []
    if trace:
        limit = trace_limit if trace_limit is not None else runs
        for i in range(min(limit, runs)):
            recorder = TraceRecorder()
            engine = engine_cls(configs[i], random.Random(seeds[i]), listeners=[recorder])
            engine.run()
            trace_results.append(recorder.as_trace())

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

    # Aggregate stats
    sim_stats = None
    if stats and stats_datas:
        agg_skill: dict[str, dict[str, int]] = {}
        agg_pos: dict[str, dict[int, int]] = {}
        for sd in stats_datas:
            for dango_id, hooks in sd["skill_triggers"].items():
                if dango_id not in agg_skill:
                    agg_skill[dango_id] = {}
                for hook_name, count in hooks.items():
                    agg_skill[dango_id][hook_name] = agg_skill[dango_id].get(hook_name, 0) + count
            for dango_id, positions in sd["position_counts"].items():
                if dango_id not in agg_pos:
                    agg_pos[dango_id] = {}
                for pos, count in positions.items():
                    agg_pos[dango_id][pos] = agg_pos[dango_id].get(pos, 0) + count

        total_rounds_count = int(total_rounds)
        heatmap = {
            dango_id: {pos: count / total_rounds_count for pos, count in positions.items()}
            for dango_id, positions in agg_pos.items()
        }
        sim_stats = SimulationStats(
            skill_triggers=agg_skill,
            position_heatmap=heatmap,
        )

    return SimulationSummary(
        runs=runs,
        wins=wins,
        win_rates=win_rates,
        average_rank=average_rank,
        average_rounds=total_rounds / runs,
        top_n_rates=top_n_rates,
        stats=sim_stats,
        traces=tuple(trace_results) if trace_results else None,
    )
