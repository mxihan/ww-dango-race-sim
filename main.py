from __future__ import annotations

import argparse
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from dango_sim.models import Board, Dango, RaceConfig
from dango_sim.simulation import run_simulations
from dango_sim.skills import (
    AimisSkill,
    CorletaSkill,
    LinnaeSkill,
    MorningSkill,
    ChisaSkill,
    ShorekeeperSkill,
)
from dango_sim.tiles import Booster, Inhibitor, SpaceTimeRift


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def build_sample_config() -> RaceConfig:
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
            Dango(id="corleta", name="珂莱塔团子", skill=CorletaSkill()),
            Dango(id="chisa", name="千咲团子", skill=ChisaSkill()),
            Dango(id="linnae", name="琳奈团子", skill=LinnaeSkill()),
            Dango(id="morning", name="莫宁团子", skill=MorningSkill()),
            Dango(id="aimis", name="爱弥斯团子", skill=AimisSkill()),
            Dango(id="shorekeeper", name="守岸人团子", skill=ShorekeeperSkill()),
        ],
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
    args = parser.parse_args()

    summary = run_simulations(
        config_factory=build_sample_config,
        runs=args.runs,
        seed=args.seed,
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


if __name__ == "__main__":
    main()
