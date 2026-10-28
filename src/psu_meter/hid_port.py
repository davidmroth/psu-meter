from __future__ import annotations

from contextlib import contextmanager
from typing import Callable, Iterator, Protocol, Sequence

REPORT_LENGTH = 64


class HidPort(Protocol):
    """The small part of a HID device the meter uses."""

    def write(self, data: Sequence[int]) -> int:
        """Send one output report."""

    def read(self, length: int) -> Sequence[int]:
        """Read one input report of up to ``length`` bytes."""

    def close(self) -> None:
        """Release the device."""


PortOpener = Callable[[], HidPort]


@contextmanager
def opened_port(open_port: PortOpener) -> Iterator[HidPort]:
    port = open_port()
    try:
        yield port
    finally:
        port.close()


def padded_report(payload: Sequence[int]) -> list[int]:
    """Report id 0 followed by ``payload``, zero-padded to the device's report length."""
    return [0x00, *payload] + [0x00] * (REPORT_LENGTH - len(payload))
