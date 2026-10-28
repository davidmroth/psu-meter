import pytest

from psu_meter.config import PsuMeterConfig
from psu_meter.domain import PsuEfficiency
from psu_meter.exceptions import InvalidConfigurationError
from psu_meter.pmbus import ParseMode


def test_defaults_match_the_hx1200i_and_five_second_polling():
    config = PsuMeterConfig.from_env({})

    assert (config.vendor_id, config.product_id) == (0x1B1C, 0x1C27)
    assert (config.parse_mode, config.interval_sec, config.history_size, config.port) == (ParseMode.BE_FIRST, 5.0, 60, 5000)


def test_efficiency_defaults_to_recording_output_watts_unchanged():
    assert PsuMeterConfig.from_env({}).efficiency == PsuEfficiency(1.0)


def test_efficiency_reads_psu_efficiency():
    assert PsuMeterConfig.from_env({"PSU_EFFICIENCY": "0.9"}).efficiency == PsuEfficiency(0.9)


def test_usb_ids_accept_hex():
    config = PsuMeterConfig.from_env({"PSU_VENDOR_ID": "0x1b1c", "PSU_PRODUCT_ID": "0x1C28"})

    assert config.product_id == 0x1C28


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("PSU_METER_INTERVAL_SEC", "0", "PSU_METER_INTERVAL_SEC must be more than zero"),
        ("PSU_METER_INTERVAL_SEC", "soon", "PSU_METER_INTERVAL_SEC must be a number of seconds"),
        ("PSU_METER_HISTORY", "0", "PSU_METER_HISTORY must be at least 1"),
        ("PSU_METER_PORT", "web", "PSU_METER_PORT must be a whole number"),
        ("PSU_EFFICIENCY", "ninety", "PSU_EFFICIENCY must be a number such as 0.90"),
        ("PSU_EFFICIENCY", "0", "PSU_EFFICIENCY: PSU efficiency must be more than 0 and at most 1"),
        ("PSU_EFFICIENCY", "1.2", "PSU_EFFICIENCY: PSU efficiency must be more than 0 and at most 1"),
        ("PSU_EFFICIENCY", "nan", "PSU_EFFICIENCY: PSU efficiency must be more than 0 and at most 1"),
    ],
)
def test_it_rejects_bad_settings_with_the_setting_name(name, value, message):
    with pytest.raises(InvalidConfigurationError, match=message):
        PsuMeterConfig.from_env({name: value})
