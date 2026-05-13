from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from dango_sim.sample_config import build_sample_config
from dango_sim.simulation import run_simulations
from dango_sim.state_io import load_starting_state


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser(description="Run dango race simulations.")
    parser.add_argument(
        "--runs",
        type=positive_int,
        default=1000,
        help="number of simulations to run",
    )
    parser.add_argument("--seed", type=int, default=None, help="random seed")
    parser.add_argument(
        "--starting-state",
        type=Path,
        default=None,
        help="JSON starting state for second-half simulations",
    )
    parser.add_argument(
        "--top-n",
        type=positive_int,
        nargs="*",
        default=[],
        help="also report probability of each dango finishing in each top-N bucket",
    )
    parser.add_argument(
        "--workers",
        type=positive_int,
        default=None,
        help="number of parallel workers (default: sequential)",
    )
    parser.add_argument(
        "--no-stats",
        action="store_true",
        default=False,
        help="disable statistics collection for maximum throughput",
    )
    parser.add_argument(
        "--trace",
        type=positive_int,
        nargs="?",
        const=10,
        default=None,
        help="record race traces (optional: number of races to trace, default: 10)",
    )
    parser.add_argument(
        "--trace-output",
        type=Path,
        default=Path("traces.json"),
        help="file to write trace data to (default: traces.json)",
    )
    args = parser.parse_args()

    starting_state = (
        load_starting_state(args.starting_state)
        if args.starting_state is not None
        else None
    )
    summary = run_simulations(
        config_factory=lambda: build_sample_config(starting_state),
        runs=args.runs,
        seed=args.seed,
        top_n=args.top_n,
        max_workers=args.workers,
        stats=not args.no_stats,
        trace=args.trace is not None,
        trace_limit=args.trace,
    )
    print(f"Runs: {summary.runs}")
    print(f"Average rounds: {summary.average_rounds:.2f}")
    for dango_id, wins in sorted(
        summary.wins.items(),
        key=lambda item: (-item[1], item[0]),
    ):
        win_rate = summary.win_rates[dango_id] * 100
        avg_rank = summary.average_rank[dango_id]
        print(
            f"{dango_id}: wins={wins}, "
            f"win_rate={win_rate:.2f}%, average_rank={avg_rank:.2f}"
        )
    for n, rates in sorted(summary.top_n_rates.items()):
        print(f"Top {n} rates:")
        for dango_id, rate in sorted(rates.items(), key=lambda item: (-item[1], item[0])):
            print(f"  {dango_id}: {rate * 100:.2f}%")

    if summary.stats is not None:
        print("\nSkill triggers:")
        for dango_id in sorted(summary.stats.skill_triggers):
            hooks = summary.stats.skill_triggers[dango_id]
            parts = [f"{hook}={count}" for hook, count in sorted(hooks.items())]
            print(f"  {dango_id}: {', '.join(parts)}")

        print("\nPosition heatmap:")
        for dango_id in sorted(summary.stats.position_heatmap):
            heatmap = summary.stats.position_heatmap[dango_id]
            top_positions = sorted(heatmap.items(), key=lambda item: -item[1])[:5]
            parts = [f"pos {pos}: {freq * 100:.1f}%" for pos, freq in top_positions]
            print(f"  {dango_id}: {', '.join(parts)}")

    if summary.traces is not None:
        trace_data = [
            [
                {
                    "kind": ev.kind,
                    "round": ev.round_number,
                    "data": ev.data,
                    "state": ev.state_snapshot,
                }
                for ev in trace.events
            ]
            for trace in summary.traces
        ]
        args.trace_output.write_text(json.dumps(trace_data, indent=2), encoding="utf-8")
        print(f"\nTraces: {len(summary.traces)} races recorded -> {args.trace_output}")


if __name__ == "__main__":
    main()
