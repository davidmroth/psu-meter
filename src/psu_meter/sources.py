"""The ways psu-meter can ask the PSU for its output power."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Callable, Iterable, Iterator, Protocol

from psu_meter.domain import SourceReading
from psu_meter.exceptions import PsuReadError
from psu_meter.hid_port import REPORT_LENGTH, HidPort, PortOpener, opened_port, padded_report
from psu_meter.pmbus import (
    CMD_PAGE,
    CMD_READ_OUTPUT_POWER,
    READ_BIT,
    SLAVE_ADDRESS,
    WRITE_BIT,
    ParseMode,
    decode_output_power,
    find_power_in_report,
)

logger = logging.getLogger(__name__)

HANDSHAKE = (0xFE, 0x03)
LEGACY_REQUEST = [0x00, 0x02, 0x00] + [0x00] * 17
LEGACY_SETTLE_SECONDS = 0.15
LIQUIDCTL_POWER_PROPERTY = "Total power output"


class PowerSource(Protocol):
    name: str

    def read(self) -> SourceReading:
        """Return watts or raise PsuReadError."""


class HidPmbusSource:
    """Reads READ_POUT over the Corsair HID-to-PMBus bridge."""

    name = "hid-pmbus"

    def __init__(self, open_port: PortOpener) -> None:
        self._open_port = open_port

    def read(self) -> SourceReading:
        with _hid_session(self.name, self._open_port) as port:
            port.write(padded_report(HANDSHAKE))
            port.read(REPORT_LENGTH)
            self._exchange(port, WRITE_BIT, CMD_PAGE, [0])
            report = tuple(self._exchange(port, READ_BIT, CMD_READ_OUTPUT_POWER))
        watts = decode_output_power(report)
        if watts is None:
            raise PsuReadError(self.name, "response was not a usable READ_POUT reply", report)
        return SourceReading(watts, self.name, report)

    @staticmethod
    def _exchange(port: HidPort, read_bit: int, command: int, data: list[int] | None = None) -> list[int]:
        port.write(padded_report([SLAVE_ADDRESS | read_bit, command, *(data or [])]))
        return list(port.read(REPORT_LENGTH))


class LiquidctlSource:
    """Asks liquidctl for the PSU's total output power."""

    name = "liquidctl"

    def __init__(
        self,
        discover: Callable[[], Iterable[Any]] | None,
        vendor_id: int,
        product_id: int,
    ) -> None:
        self._discover = discover
        self._vendor_id = vendor_id
        self._product_id = product_id

    def read(self) -> SourceReading:
        if self._discover is None:
            raise PsuReadError(self.name, "liquidctl is not installed")
        for device in self._matching_devices():
            watts = self._total_output_watts(device)
            if watts is not None:
                return SourceReading(watts, f"{self.name}:{_description(device)}")
        raise PsuReadError(self.name, f"no matching device reported {LIQUIDCTL_POWER_PROPERTY!r}")

    def _matching_devices(self) -> list[Any]:
        devices = list(self._discover())
        logger.debug("liquidctl discovered %s supported device(s)", len(devices))
        return [device for device in devices if self._is_target(device)]

    def _is_target(self, device: Any) -> bool:
        vendor_id, product_id = _device_ids(device)
        if vendor_id is None or product_id is None:
            return True
        return (vendor_id, product_id) == (self._vendor_id, self._product_id)

    def _total_output_watts(self, device: Any) -> int | None:
        # liquidctl drivers raise many unrelated exception types; one bad device must not stop the others.
        try:
            with device.connect():
                _call_with_direct_access(device.initialize)
                status = _call_with_direct_access(device.get_status)
        except Exception:
            logger.exception("liquidctl read failed for %s", _description(device))
            return None
        for prop, value, _unit in status:
            if prop == LIQUIDCTL_POWER_PROPERTY:
                return int(round(float(value)))
        return None


class HidLegacySource:
    """Older raw HID request whose reply layout is guessed with ``ParseMode``."""

    name = "hid-fallback"

    def __init__(self, open_port: PortOpener, parse_mode: ParseMode, settle: Callable[[float], None]) -> None:
        self._open_port = open_port
        self._parse_mode = parse_mode
        self._settle = settle

    def read(self) -> SourceReading:
        with _hid_session(self.name, self._open_port) as port:
            port.write(LEGACY_REQUEST)
            self._settle(LEGACY_SETTLE_SECONDS)
            report = tuple(port.read(REPORT_LENGTH))
        watts = find_power_in_report(report, self._parse_mode)
        if watts is None:
            raise PsuReadError(self.name, f"no plausible watt value in report ({self._parse_mode.value})", report)
        return SourceReading(watts, self.name, report)


@contextmanager
def _hid_session(source: str, open_port: PortOpener) -> Iterator[HidPort]:
    """An open port whose OS-level failures (unplugged, no permission) surface as PsuReadError."""
    try:
        with opened_port(open_port) as port:
            yield port
    except (OSError, ValueError) as exc:
        raise PsuReadError(source, f"HID device error: {exc}") from exc


def _call_with_direct_access(method: Callable[..., Any]) -> Any:
    # Older liquidctl drivers do not accept the direct_access keyword.
    try:
        return method(direct_access=True)
    except TypeError:
        return method()


def _device_ids(device: Any) -> tuple[int | None, int | None]:
    holders = (device, getattr(device, "device", None))
    return _first_attribute(holders, "vendor_id"), _first_attribute(holders, "product_id")


def _first_attribute(holders: tuple[Any, ...], name: str) -> Any:
    for holder in holders:
        value = getattr(holder, name, None)
        if value is not None:
            return value
    return None


def _description(device: Any) -> str:
    return getattr(device, "description", type(device).__name__)
