from __future__ import annotations

import time
from collections import deque

import pytest

from energy_cost_browser_testing import MeterUnderTest
from psu_meter.energy import build_energy_service
from psu_meter.pmbus import ParseMode
from psu_meter.poller import ReadingPoller
from psu_meter.web import create_app

pytest_plugins = ["energy_cost_browser_testing.plugin"]

POLL_INTERVAL_SECONDS = 5.0


class NoHardwareReader:
    def read(self):
        raise AssertionError("browser tests feed readings directly and must not poll the PSU")


def _build_app(energy):
    poller = ReadingPoller(NoHardwareReader(), time.time, deque(maxlen=60), POLL_INTERVAL_SECONDS, lambda _s: None)
    return create_app(poller, ParseMode.BE_FIRST, energy)


@pytest.fixture
def meter_under_test() -> MeterUnderTest:
    return MeterUnderTest(
        name="psu",
        build_energy=lambda environ: build_energy_service(environ, time.time),
        build_app=_build_app,
    )
