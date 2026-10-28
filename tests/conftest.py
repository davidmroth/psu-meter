from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import pytest

# PMBus LINEAR11 bytes (little-endian) for 312 W with exponent -1 and mantissa 624.
LINEAR11_312_WATTS = [0x70, 0xFA]
POWER_REPLY_312 = [0x03, 0xEE, *LINEAR11_312_WATTS]


@dataclass
class FakePort:
    replies: list[Sequence[int]]
    writes: list[list[int]] = field(default_factory=list)
    closed: bool = False

    def write(self, data: Sequence[int]) -> int:
        self.writes.append(list(data))
        return len(data)

    def read(self, length: int) -> Sequence[int]:
        return self.replies.pop(0)

    def close(self) -> None:
        self.closed = True


@dataclass
class FakeClock:
    now: float = 1_791_849_600.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()
