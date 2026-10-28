from __future__ import annotations

import math
from dataclasses import dataclass

from psu_meter.exceptions import InvalidEfficiencyError


@dataclass(frozen=True)
class SourceReading:
    """Watts as returned by one way of reading the PSU, before it is time-stamped."""

    watts: int
    source: str
    raw_report: tuple[int, ...] | None = None


@dataclass(frozen=True)
class PowerReading:
    """One successful PSU power reading."""

    observed_at: float
    watts: int
    source: str
    raw_report: tuple[int, ...] | None = None


@dataclass(frozen=True)
class PsuEfficiency:
    """Share of wall power the PSU delivers to the GPU; the rest is lost as heat but still billed.

    1.0 means "record the PSU's output watts as-is".
    """

    ratio: float = 1.0

    def __post_init__(self) -> None:
        if not math.isfinite(self.ratio) or not 0 < self.ratio <= 1:
            raise InvalidEfficiencyError(f"PSU efficiency must be more than 0 and at most 1 (got {self.ratio!r})")

    def wall_watts(self, output_watts: float) -> float:
        return output_watts / self.ratio
