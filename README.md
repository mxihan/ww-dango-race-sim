# ww-dango

Python simulator for configurable single-lane dango races.

The board is a loop: position `0` is both start and finish, and `finish`
means the number of steps needed to complete one lap. Custom tiles live on
track positions `1..finish-1`.

## Run tests

```bash
uv run pytest
```

## Run sample simulations

```bash
uv run python main.py --runs 1000 --seed 42
```

The core API accepts a fresh `RaceConfig` per simulation, so callers can vary participants and boards between races.
