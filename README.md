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
