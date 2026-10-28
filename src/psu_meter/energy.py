"""Builds this meter's energy history, cost and stats service."""

from __future__ import annotations

from typing import Callable, Mapping

from energy_cost.domain import WattReading
from energy_cost.live import RecordingListener
from energy_cost.service import EnergyService
from energy_cost.settings import EnergySettings, MeterIdentity
from psu_meter.domain import PsuEfficiency
from psu_meter.poller import Sample

PSU_IDENTITY = MeterIdentity(meter="psu", measures="gpu")


def build_energy_service(environ: Mapping[str, str], clock: Callable[[], float]) -> EnergyService:
    return EnergyService.build(EnergySettings.from_env(environ), PSU_IDENTITY, clock)


class GpuWattConverter:
    """Turns one PSU poll into the GPU's wall-outlet watts for energy history."""

    def __init__(self, efficiency: PsuEfficiency) -> None:
        self._efficiency = efficiency

    def __call__(self, sample: Sample) -> WattReading | None:
        reading = sample.reading
        if reading is None:
            return None
        return WattReading(
            observed_at=reading.observed_at,
            watts=self._efficiency.wall_watts(reading.watts),
            estimated=False,
        )


def energy_listener(energy: EnergyService, efficiency: PsuEfficiency) -> RecordingListener[Sample]:
    return RecordingListener(energy.recorder, GpuWattConverter(efficiency))
