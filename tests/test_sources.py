from contextlib import nullcontext

import pytest

from conftest import POWER_REPLY_312, FakePort
from psu_meter.exceptions import PsuReadError
from psu_meter.hid_port import REPORT_LENGTH
from psu_meter.pmbus import ParseMode
from psu_meter.sources import HidLegacySource, HidPmbusSource, LiquidctlSource

VENDOR, PRODUCT = 0x1B1C, 0x1C27


def pmbus_port(power_reply):
    return FakePort(replies=[[0xFE], [0x02, 0x00], power_reply])


def test_pmbus_source_reads_watts_and_keeps_the_raw_reply():
    port = pmbus_port(POWER_REPLY_312)

    found = HidPmbusSource(lambda: port).read()

    assert (found.watts, found.source, found.raw_report) == (312, "hid-pmbus", tuple(POWER_REPLY_312))


def test_pmbus_source_sends_handshake_page_select_then_read_pout():
    port = pmbus_port(POWER_REPLY_312)

    HidPmbusSource(lambda: port).read()

    assert [write[:4] for write in port.writes] == [[0, 0xFE, 0x03, 0], [0, 0x02, 0x00, 0], [0, 0x03, 0xEE, 0]]
    assert all(len(write) == REPORT_LENGTH + 1 for write in port.writes)


def test_pmbus_source_rejects_an_unusable_reply_and_still_closes_the_port():
    port = pmbus_port([0x03, 0x8B, 0x00, 0x00])

    with pytest.raises(PsuReadError) as caught:
        HidPmbusSource(lambda: port).read()

    assert caught.value.source == "hid-pmbus"
    assert caught.value.raw_report == (0x03, 0x8B, 0x00, 0x00)
    assert port.closed


def test_pmbus_source_reports_an_unplugged_device_as_a_read_failure():
    def unplugged():
        raise OSError("open failed")

    with pytest.raises(PsuReadError, match="hid-pmbus: HID device error: open failed"):
        HidPmbusSource(unplugged).read()


def test_legacy_source_waits_for_the_device_then_parses_the_reply():
    port = FakePort(replies=[[0x00, 0x2C, 0x01, 0x90]])
    waits = []

    found = HidLegacySource(lambda: port, ParseMode.MAX, waits.append).read()

    assert (found.watts, found.source) == (400, "hid-fallback")
    assert waits == [0.15]
    assert port.closed


def test_legacy_source_reports_the_parse_mode_when_nothing_is_plausible():
    port = FakePort(replies=[[0x00, 0x00, 0x00]])

    with pytest.raises(PsuReadError, match=r"no plausible watt value in report \(le-first\)"):
        HidLegacySource(lambda: port, ParseMode.LE_FIRST, lambda _s: None).read()


class FakeLiquidDevice:
    def __init__(self, status, vendor_id=VENDOR, product_id=PRODUCT, description="Corsair HX1200i", fails=False):
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.description = description
        self._status = status
        self._fails = fails

    def connect(self):
        if self._fails:
            raise OSError("device busy")
        return nullcontext()

    def initialize(self, direct_access=False):
        return []

    def get_status(self, direct_access=False):
        return self._status


class OldDriverDevice(FakeLiquidDevice):
    def initialize(self):
        return []

    def get_status(self):
        return self._status


POWER_STATUS = [("Total power output", 287.6, "W")]


def liquidctl(*devices):
    return LiquidctlSource(lambda: list(devices), VENDOR, PRODUCT)


def test_liquidctl_source_reads_total_power_output_from_the_matching_device():
    found = liquidctl(FakeLiquidDevice(POWER_STATUS)).read()

    assert (found.watts, found.source) == (288, "liquidctl:Corsair HX1200i")


def test_liquidctl_source_ignores_devices_with_other_usb_ids():
    other = FakeLiquidDevice([("Total power output", 999, "W")], vendor_id=0x1234)

    found = liquidctl(other, FakeLiquidDevice(POWER_STATUS)).read()

    assert found.watts == 288


def test_liquidctl_source_moves_on_when_one_device_fails():
    found = liquidctl(FakeLiquidDevice(POWER_STATUS, fails=True, description="busy"), FakeLiquidDevice(POWER_STATUS)).read()

    assert found.source == "liquidctl:Corsair HX1200i"


def test_liquidctl_source_supports_drivers_without_direct_access():
    assert liquidctl(OldDriverDevice(POWER_STATUS)).read().watts == 288


def test_liquidctl_source_fails_when_no_device_reports_power():
    with pytest.raises(PsuReadError, match="no matching device reported 'Total power output'"):
        liquidctl(FakeLiquidDevice([("Fan speed", 900, "rpm")])).read()


def test_liquidctl_source_fails_clearly_when_liquidctl_is_not_installed():
    with pytest.raises(PsuReadError, match="liquidctl is not installed"):
        LiquidctlSource(None, VENDOR, PRODUCT).read()
