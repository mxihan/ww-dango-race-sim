from __future__ import annotations

import argparse
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


if __name__ == "__main__":
    main()
