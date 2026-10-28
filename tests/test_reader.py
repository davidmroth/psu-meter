import pytest

from psu_meter.domain import SourceReading
from psu_meter.exceptions import AllSourcesFailedError, PsuReadError
from psu_meter.reader import PsuReader


class ScriptedSource:
    def __init__(self, name, outcome):
        self.name = name
        self._outcome = outcome
        self.calls = 0

    def read(self):
        self.calls += 1
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._outcome


def test_it_time_stamps_the_first_source_that_answers(clock):
    reading = PsuReader([ScriptedSource("a", SourceReading(250, "a"))], clock).read()

    assert (reading.observed_at, reading.watts, reading.source) == (clock.now, 250, "a")


def test_it_stops_at_the_first_answer(clock):
    later = ScriptedSource("b", SourceReading(1, "b"))

    PsuReader([ScriptedSource("a", SourceReading(250, "a")), later], clock).read()

    assert later.calls == 0


def test_it_falls_through_to_the_next_source_after_a_failure(clock):
    sources = [ScriptedSource("a", PsuReadError("a", "no reply")), ScriptedSource("b", SourceReading(260, "b"))]

    assert PsuReader(sources, clock).read().source == "b"


def test_it_reports_every_reason_and_the_last_raw_report_when_all_fail(clock):
    sources = [
        ScriptedSource("a", PsuReadError("a", "no reply", (1, 2))),
        ScriptedSource("b", PsuReadError("b", "bad bytes", (3, 4))),
    ]

    with pytest.raises(AllSourcesFailedError) as caught:
        PsuReader(sources, clock).read()

    assert str(caught.value) == "psu: a: no reply; b: bad bytes"
    assert caught.value.raw_report == (3, 4)


def test_it_turns_an_unexpected_library_error_into_a_read_failure(clock):
    sources = [ScriptedSource("a", OSError("open failed"))]

    with pytest.raises(AllSourcesFailedError, match="a: OSError: open failed"):
        PsuReader(sources, clock).read()
