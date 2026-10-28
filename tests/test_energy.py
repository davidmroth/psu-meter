from collections import deque

import pytest

from energy_cost.domain import WattReading
from energy_cost.timeutil import UtcRange
from psu_meter.domain import PowerReading, PsuEfficiency
from psu_meter.energy import GpuWattConverter, build_energy_service, energy_listener
from psu_meter.exceptions import InvalidEfficiencyError, PsuReadError
from psu_meter.poller import ReadingPoller, Sample
from test_poller import StubReader

# 2026-10-13T00:00:00Z
HOUR_START = 1_791_849_600.0
IN_MEMORY_ENERGY_ENV = {"ENERGY_DB_PATH": ":memory:", "ENERGY_RATE_PER_KWH": "0.15"}


def reading_sample(watts: int, observed_at: float = HOUR_START) -> Sample:
    return Sample(observed_at, PowerReading(observed_at, watts, "hid-pmbus"), None)


def test_it_records_output_watts_unchanged_at_full_efficiency():
    assert GpuWattConverter(PsuEfficiency())(reading_sample(300)) == WattReading(HOUR_START, 300.0, estimated=False)


def test_it_scales_output_watts_up_to_wall_watts_by_efficiency():
    assert GpuWattConverter(PsuEfficiency(0.9))(reading_sample(450)).watts == pytest.approx(500.0)


def test_it_skips_failed_polls():
    failed = Sample(HOUR_START, None, "psu: unplugged")

    assert GpuWattConverter(PsuEfficiency())(failed) is None


@pytest.mark.parametrize("ratio", [0.0, -0.5, 1.01, float("inf")])
def test_efficiency_rejects_ratios_outside_zero_to_one(ratio):
    with pytest.raises(InvalidEfficiencyError, match="more than 0 and at most 1"):
        PsuEfficiency(ratio)


def test_polled_gpu_readings_land_in_energy_history_as_wall_watts():
    energy = build_energy_service(IN_MEMORY_ENERGY_ENV, lambda: HOUR_START + 60)
    outcomes = [
        PowerReading(HOUR_START, 180, "hid-pmbus"),
        PsuReadError("psu", "unplugged"),
        PowerReading(HOUR_START + 10, 180, "hid-pmbus"),
    ]
    poller = ReadingPoller(
        StubReader(outcomes),
        lambda: HOUR_START + 5,
        deque(maxlen=4),
        5.0,
        lambda _: None,
        [energy_listener(energy, PsuEfficiency(0.9))],
    )

    for _ in outcomes:
        poller.tick()

    history = energy.history.query(UtcRange(HOUR_START, HOUR_START + 60))
    assert history.stats.current == pytest.approx(200.0)
    assert history.totals.covered_seconds == 10.0
    assert history.totals.kwh == pytest.approx(200.0 * 10 / 3_600_000)
    assert history.totals.estimated_kwh == 0
