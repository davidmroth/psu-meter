from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Callable, Protocol, Sequence

from psu_meter.domain import PowerReading
from psu_meter.exceptions import PsuReadError
from psu_meter.reader import Clock


class Reader(Protocol):
    def read(self) -> PowerReading:
        """Return one reading or raise PsuReadError."""


class Sleeper(Protocol):
    def __call__(self, seconds: float) -> None:
        """Block for the given number of seconds."""


@dataclass(frozen=True)
class Sample:
    """The outcome of one poll: a reading, or the reason there is none."""

    observed_at: float
    reading: PowerReading | None
    error: str | None
    raw_report: tuple[int, ...] | None = None

    @property
    def watts(self) -> int | None:
        return self.reading.watts if self.reading else None


class SampleListener(Protocol):
    def __call__(self, sample: Sample) -> None:
        """React to one poll result. Must not raise."""


class ReadingPoller:
    def __init__(
        self,
        reader: Reader,
        clock: Clock,
        history: deque[Sample],
        interval_sec: float,
        sleeper: Sleeper,
        listeners: Sequence[SampleListener] = (),
    ) -> None:
        self._reader = reader
        self._clock = clock
        self._history = history
        self._interval_sec = interval_sec
        self._sleeper = sleeper
        self._listeners = tuple(listeners)

    def tick(self) -> Sample:
        try:
            reading = self._reader.read()
            sample = Sample(reading.observed_at, reading, None, reading.raw_report)
        except PsuReadError as exc:
            sample = Sample(self._clock(), None, str(exc), exc.raw_report)
        self._history.append(sample)
        for listener in self._listeners:
            listener(sample)
        return sample

    def run_forever(self, should_continue: Callable[[], bool] | None = None) -> None:
        while should_continue() if should_continue else True:
            self.tick()
            self._sleeper(self._interval_sec)

    def latest(self) -> Sample | None:
        if not self._history:
            return None
        return self._history[-1]

    def samples(self) -> list[Sample]:
        return list(self._history)
