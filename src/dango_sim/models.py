from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class Board:
    finish: int
    tiles: Mapping[int, object] = field(default_factory=dict)
