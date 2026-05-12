from __future__ import annotations

import json
from pathlib import Path

from dango_sim.models import RaceStartingState


def load_starting_state(path: str | Path) -> RaceStartingState:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return RaceStartingState(
        positions={
            int(position): list(stack)
            for position, stack in payload["positions"].items()
        },
        laps_completed={
            str(dango_id): int(laps)
            for dango_id, laps in payload["laps_completed"].items()
        },
    )


def dump_starting_state(starting_state: RaceStartingState, path: str | Path) -> None:
    payload = {
        "positions": {
            str(position): list(stack)
            for position, stack in starting_state.positions.items()
        },
        "laps_completed": dict(starting_state.laps_completed),
    }
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
