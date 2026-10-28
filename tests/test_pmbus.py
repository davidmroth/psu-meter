import pytest

from conftest import LINEAR11_312_WATTS, POWER_REPLY_312
from psu_meter.exceptions import InvalidConfigurationError
from psu_meter.pmbus import ParseMode, decode_output_power, find_power_in_report, linear11_to_float


def test_linear11_decodes_zero_exponent():
    assert linear11_to_float([0x38, 0x01]) == 312


def test_linear11_decodes_negative_exponent():
    assert linear11_to_float(LINEAR11_312_WATTS) == 312.0


def test_linear11_decodes_negative_mantissa():
    assert linear11_to_float([0xFF, 0x07]) == -1


def test_it_decodes_a_read_pout_reply():
    assert decode_output_power(POWER_REPLY_312) == 312


@pytest.mark.parametrize(
    "report",
    [
        [0x02, 0xEE, *LINEAR11_312_WATTS],
        [0x03, 0x8B, *LINEAR11_312_WATTS],
        [0x03, 0xEE, 0x70],
        [0x03, 0xEE, 0x00, 0x00],
    ],
    ids=["wrong-address", "wrong-command", "too-short", "zero-watts"],
)
def test_it_rejects_reports_that_are_not_a_usable_read_pout_reply(report):
    assert decode_output_power(report) is None


AMBIGUOUS_REPORT = [0x00, 0x2C, 0x01, 0x90]


def test_be_first_takes_the_first_plausible_big_endian_word():
    assert find_power_in_report(AMBIGUOUS_REPORT, ParseMode.BE_FIRST) == 44


def test_le_first_takes_the_first_plausible_little_endian_word():
    assert find_power_in_report(AMBIGUOUS_REPORT, ParseMode.LE_FIRST) == 300


def test_max_takes_the_largest_plausible_word_in_either_order():
    assert find_power_in_report(AMBIGUOUS_REPORT, ParseMode.MAX) == 400


def test_it_falls_back_to_a_signed_little_endian_word():
    assert find_power_in_report([0xD4, 0xFE], ParseMode.BE_FIRST) == 300


def test_it_returns_none_when_no_word_is_plausible():
    assert find_power_in_report([0x00, 0x00, 0x00], ParseMode.BE_FIRST) is None


def test_parse_mode_accepts_any_case_and_spacing():
    assert ParseMode.from_setting(" MAX ") is ParseMode.MAX


def test_it_rejects_an_unknown_parse_mode_naming_the_setting():
    with pytest.raises(InvalidConfigurationError, match="PSU_PARSE_MODE must be one of be-first, le-first, max"):
        ParseMode.from_setting("middle")
