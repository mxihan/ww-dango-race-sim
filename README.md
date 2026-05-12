# ww-dango

Python simulator for configurable single-lane dango races.

The board is a loop. Position `0` is both start and finish, and `finish`
is the number of positions in one lap. Valid track positions are
`0..finish-1`; custom tiles live on `1..finish-1`.

Tile effects resolve once by default, matching the reference web simulator.
Set `RaceConfig(tile_resolution="chain")` to allow a tile to move a stack onto
another tile and keep resolving until no tile applies or `max_tile_depth` is
reached.

## Run tests

```bash
uv run pytest
```

## Run sample simulations

```bash
uv run python main.py --runs 1000 --seed 42
```

The core API accepts a fresh `RaceConfig` per simulation, so callers can vary participants and boards between races.

## Starting states

Second-half simulations can start from an editable JSON file:

```json
{
  "positions": {
    "0": ["carlotta"],
    "7": ["bu_king", "chisa"]
  },
  "laps_completed": {
    "carlotta": 1,
    "chisa": 0
  }
}
```

Stacks are listed from bottom to top. If Bu King is present in the file, its
position is preserved, but it still does not roll or act until round 3 of the
current half.

Run a second-half simulation with top-N probabilities:

```bash
uv run python main.py --runs 1000 --seed 42 --starting-state second-half.json --top-n 3 4
```
