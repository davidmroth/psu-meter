from __future__ import annotations

import logging
from typing import Callable, Sequence

from psu_meter.domain import PowerReading
from psu_meter.exceptions import AllSourcesFailedError, PsuReadError
from psu_meter.sources import PowerSource

logger = logging.getLogger(__name__)

Clock = Callable[[], float]


class PsuReader:
    """Tries each power source in order and time-stamps the first one that answers."""

    def __init__(self, sources: Sequence[PowerSource], clock: Clock) -> None:
        self._sources = tuple(sources)
        self._clock = clock

    def read(self) -> PowerReading:
        failures: list[PsuReadError] = []
        for source in self._sources:
            try:
                found = source.read()
            except PsuReadError as exc:
                logger.debug("Power source failed: %s", exc)
                failures.append(exc)
                continue
            # USB libraries raise OS, value and driver-specific errors; one failing source must not end the poll.
            except Exception as exc:
                logger.exception("Unexpected error from power source %s", source.name)
                failures.append(PsuReadError(source.name, f"{type(exc).__name__}: {exc}"))
                continue
            logger.info("Power: %s W (via %s)", found.watts, found.source)
            return PowerReading(self._clock(), found.watts, found.source, found.raw_report)
        raise AllSourcesFailedError(failures)
