from __future__ import annotations

import argparse
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from dango_sim.models import Board, Dango, RaceConfig
from dango_sim.simulation import run_simulations
from dango_sim.skills import (
    AemeathSkill,
    CarlottaSkill,
    LynaeSkill,
    MornyeSkill,
    ChisaSkill,
    ShorekeeperSkill,
)
from dango_sim.state_io import load_starting_state
from dango_sim.tiles import Booster, Inhibitor, SpaceTimeRift


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def build_sample_config(starting_state=None) -> RaceConfig:
    # Board layout (32 tiles, start/finish share position 0):
    #   0 = start = finish
    #   1..31 = track tiles (1 = first tile ahead of start)
    #   finish = 32 means dangos travel 32 tiles to complete a lap
    return RaceConfig(
        board=Board(
            finish=32,
            tiles={
                3: Booster(),
                6: SpaceTimeRift(),
                10: Inhibitor(),
                11: Booster(),
                16: Booster(),
                20: SpaceTimeRift(),
                23: Booster(),
                28: Inhibitor(),
            },
        ),
        participants=[
            Dango(id="carlotta", name="珂莱塔团子", skill=CarlottaSkill()),
            Dango(id="chisa", name="千咲团子", skill=ChisaSkill()),
            Dango(id="lynae", name="琳奈团子", skill=LynaeSkill()),
            Dango(id="mornye", name="莫宁团子", skill=MornyeSkill()),
            Dango(id="aemeath", name="爱弥斯团子", skill=AemeathSkill()),
            Dango(id="shorekeeper", name="守岸人团子", skill=ShorekeeperSkill()),
        ],
        starting_state=starting_state,
    )


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
