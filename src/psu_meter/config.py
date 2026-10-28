from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from psu_meter.domain import PsuEfficiency
from psu_meter.exceptions import InvalidConfigurationError
from psu_meter.pmbus import ParseMode

CORSAIR_VENDOR_ID = 0x1B1C
HX1200I_PRODUCT_ID = 0x1C27


def _text(environ: Mapping[str, str], name: str, default: str) -> str:
    raw = environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip()


def _integer(environ: Mapping[str, str], name: str, default: int, minimum: int) -> int:
    raw = _text(environ, name, str(default))
    try:
        value = int(raw, 0)
    except ValueError as exc:
        raise InvalidConfigurationError(f"{name} must be a whole number (got {raw!r})") from exc
    if value < minimum:
        raise InvalidConfigurationError(f"{name} must be at least {minimum} (got {value})")
    return value


def _seconds(environ: Mapping[str, str], name: str, default: float) -> float:
    raw = _text(environ, name, str(default))
    try:
        value = float(raw)
    except ValueError as exc:
        raise InvalidConfigurationError(f"{name} must be a number of seconds (got {raw!r})") from exc
    if not value > 0:
        raise InvalidConfigurationError(f"{name} must be more than zero (got {raw!r})")
    return value


def _efficiency(environ: Mapping[str, str], name: str) -> PsuEfficiency:
    raw = _text(environ, name, "1.0")
    try:
        ratio = float(raw)
    except ValueError as exc:
        raise InvalidConfigurationError(f"{name} must be a number such as 0.90 (got {raw!r})") from exc
    try:
        return PsuEfficiency(ratio)
    except InvalidConfigurationError as exc:
        raise InvalidConfigurationError(f"{name}: {exc}") from exc


@dataclass(frozen=True)
class PsuMeterConfig:
    vendor_id: int
    product_id: int
    parse_mode: ParseMode
    interval_sec: float
    history_size: int
    port: int
    log_level: str
    log_dir: str
    efficiency: PsuEfficiency

    @classmethod
    def from_env(cls, environ: Mapping[str, str]) -> "PsuMeterConfig":
        return cls(
            vendor_id=_integer(environ, "PSU_VENDOR_ID", CORSAIR_VENDOR_ID, 0),
            product_id=_integer(environ, "PSU_PRODUCT_ID", HX1200I_PRODUCT_ID, 0),
            parse_mode=ParseMode.from_setting(_text(environ, "PSU_PARSE_MODE", ParseMode.BE_FIRST.value)),
            interval_sec=_seconds(environ, "PSU_METER_INTERVAL_SEC", 5.0),
            history_size=_integer(environ, "PSU_METER_HISTORY", 60, 1),
            port=_integer(environ, "PSU_METER_PORT", 5000, 1),
            log_level=_text(environ, "LOG_LEVEL", "INFO").upper(),
            log_dir=_text(environ, "PSU_METER_LOG_DIR", "/app/logs"),
            efficiency=_efficiency(environ, "PSU_EFFICIENCY"),
        )
