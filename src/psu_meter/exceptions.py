from __future__ import annotations


class PsuError(Exception):
    """Base class for every psu-meter error."""


class InvalidConfigurationError(PsuError):
    """An environment setting has a value the meter cannot use."""


class InvalidEfficiencyError(InvalidConfigurationError):
    """A PSU efficiency outside the range 0 (exclusive) to 1 (inclusive)."""


class PsuReadError(PsuError):
    """One way of reading the PSU did not produce a power value."""

    def __init__(self, source: str, reason: str, raw_report: tuple[int, ...] | None = None) -> None:
        super().__init__(f"{source}: {reason}")
        self.source = source
        self.reason = reason
        self.raw_report = raw_report


class AllSourcesFailedError(PsuReadError):
    """Every configured way of reading the PSU failed in the same poll."""

    def __init__(self, failures: list[PsuReadError]) -> None:
        reasons = "; ".join(str(failure) for failure in failures) or "no power sources are configured"
        raw_report = next((f.raw_report for f in reversed(failures) if f.raw_report is not None), None)
        super().__init__("psu", reasons, raw_report)
        self.failures = tuple(failures)
