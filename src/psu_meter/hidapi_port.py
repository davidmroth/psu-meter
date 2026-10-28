"""hidapi-backed port. Imported only by the runtime, so tests never need USB libraries."""

from __future__ import annotations

import hid

from psu_meter.hid_port import HidPort, PortOpener


def hidapi_opener(vendor_id: int, product_id: int) -> PortOpener:
    def open_port() -> HidPort:
        device = hid.device()
        device.open(vendor_id, product_id)
        return device

    return open_port
