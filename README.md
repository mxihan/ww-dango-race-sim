# ww-dango

Python simulator for configurable single-lane dango races.

## Run tests

```bash
uv run pytest
```

## Run sample simulations

```bash
uv run python main.py --runs 1000 --seed 42
```

The core API accepts a fresh `RaceConfig` per simulation, so callers can vary participants and boards between races.
