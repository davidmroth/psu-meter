from collections import deque

from psu_meter.domain import PowerReading
from psu_meter.exceptions import PsuReadError
from psu_meter.poller import ReadingPoller


class StubReader:
    def __init__(self, outcomes):
        self._outcomes = list(outcomes)

    def read(self):
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def poller(outcomes, clock, size=60, sleeps=None, listeners=()):
    return ReadingPoller(
        StubReader(outcomes),
        clock,
        deque(maxlen=size),
        5.0,
        (sleeps if sleeps is not None else []).append,
        listeners,
    )


def test_tick_keeps_a_successful_reading(clock):
    reading = PowerReading(clock.now - 1, 300, "hid-pmbus", (1, 2))

    sample = poller([reading], clock).tick()

    assert (sample.observed_at, sample.watts, sample.error, sample.raw_report) == (clock.now - 1, 300, None, (1, 2))


def test_tick_records_a_failed_read_with_no_watts(clock):
    sample = poller([PsuReadError("psu", "unplugged", (9,))], clock).tick()

    assert (sample.observed_at, sample.watts, sample.error, sample.raw_report) == (clock.now, None, "psu: unplugged", (9,))


def test_history_keeps_only_the_newest_samples(clock):
    readings = [PowerReading(clock.now + i, 100 + i, "x") for i in range(3)]
    meter = poller(readings, clock, size=2)

    for _ in readings:
        meter.tick()

    assert [s.watts for s in meter.samples()] == [101, 102]
    assert meter.latest().watts == 102


def test_tick_hands_every_sample_to_each_listener_in_order(clock):
    first, second = [], []
    meter = poller(
        [PowerReading(clock.now, 200, "x"), PsuReadError("psu", "unplugged")],
        clock,
        listeners=[first.append, second.append],
    )

    meter.tick()
    meter.tick()

    assert [s.watts for s in first] == [200, None]
    assert first == second


def test_latest_is_none_before_the_first_poll(clock):
    assert poller([], clock).latest() is None


def test_run_forever_polls_then_waits_the_interval(clock):
    sleeps = []
    meter = poller([PowerReading(clock.now, 100, "x")] * 2, clock, sleeps=sleeps)
    remaining = iter([True, True, False])

    meter.run_forever(lambda: next(remaining))

    assert len(meter.samples()) == 2
    assert sleeps == [5.0, 5.0]
