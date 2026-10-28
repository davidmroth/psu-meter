"""Pure decoding of Corsair PSU HID reports into watts."""

from __future__ import annotations

from enum import Enum
from typing import Iterator, Sequence

from psu_meter.exceptions import InvalidConfigurationError

MIN_PLAUSIBLE_WATTS = 10
MAX_PLAUSIBLE_WATTS = 2000

SLAVE_ADDRESS = 0x02
WRITE_BIT = 0x00
READ_BIT = 0x01
CMD_PAGE = 0x00
CMD_READ_OUTPUT_POWER = 0xEE


class ByteOrder(Enum):
    BIG = "be"
    LITTLE = "le"


class ParseMode(Enum):
    """How the legacy HID fallback picks a watt value out of an unlabelled report."""

    BE_FIRST = "be-first"
    LE_FIRST = "le-first"
    MAX = "max"

    @classmethod
    def from_setting(cls, raw: str) -> "ParseMode":
        normalized = raw.strip().lower()
        for mode in cls:
            if mode.value == normalized:
                return mode
        allowed = ", ".join(mode.value for mode in cls)
        raise InvalidConfigurationError(f"PSU_PARSE_MODE must be one of {allowed} (got {raw!r})")


def is_plausible_watts(value: float) -> bool:
    return MIN_PLAUSIBLE_WATTS < value < MAX_PLAUSIBLE_WATTS


def linear11_to_float(data: Sequence[int]) -> float:
    """Decode a PMBus LINEAR11 value: 5-bit signed exponent, 11-bit signed mantissa."""
    raw = int.from_bytes(bytes(data[:2]), byteorder="little")
    exponent = raw >> 11
    mantissa = raw & 0x7FF
    if mantissa > 1023:
        mantissa -= 2048
    if exponent > 15:
        exponent -= 32
    return mantissa * (2**exponent)


def decode_output_power(report: Sequence[int]) -> int | None:
    """Watts from a READ_POUT response, or None if the report is not that response."""
    if len(report) < 4:
        return None
    if report[0] != (SLAVE_ADDRESS | READ_BIT) or report[1] != CMD_READ_OUTPUT_POWER:
        return None
    power = linear11_to_float(report[2:])
    if not 0 < power < MAX_PLAUSIBLE_WATTS:
        return None
    return int(round(power))


def _word_candidates(report: Sequence[int], order: ByteOrder) -> Iterator[int]:
    for index in range(len(report) - 1):
        high, low = (report[index], report[index + 1]) if order is ByteOrder.BIG else (report[index + 1], report[index])
        yield (high << 8) | low


def _first_plausible(report: Sequence[int], orders: Sequence[ByteOrder]) -> int | None:
    for order in orders:
        for value in _word_candidates(report, order):
            if is_plausible_watts(value):
                return value
    return None


def _largest_plausible(report: Sequence[int]) -> int | None:
    plausible = [
        value
        for order in (ByteOrder.BIG, ByteOrder.LITTLE)
        for value in _word_candidates(report, order)
        if is_plausible_watts(value)
    ]
    return max(plausible, default=None)


def _first_plausible_signed(report: Sequence[int]) -> int | None:
    for raw in _word_candidates(report, ByteOrder.LITTLE):
        signed = raw if raw < 0x8000 else raw - 0x10000
        if is_plausible_watts(abs(signed)):
            return abs(signed)
    return None


def find_power_in_report(report: Sequence[int], mode: ParseMode) -> int | None:
    """Best-guess watts from a raw report whose layout is not known."""
    if len(report) < 2:
        return None
    if mode is ParseMode.MAX:
        chosen = _largest_plausible(report)
    elif mode is ParseMode.LE_FIRST:
        chosen = _first_plausible(report, (ByteOrder.LITTLE, ByteOrder.BIG))
    else:
        chosen = _first_plausible(report, (ByteOrder.BIG, ByteOrder.LITTLE))
    if chosen is not None:
        return chosen
    return _first_plausible_signed(report)
