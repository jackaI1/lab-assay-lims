"""Values in explicit engineering units and errors callers can handle."""

from dataclasses import dataclass
from math import isfinite


class InstrumentError(RuntimeError):
    """The instrument could not complete a requested operation."""


class OperationTimeout(InstrumentError):
    """No fresh response arrived before the configured deadline."""


class BadReading(InstrumentError):
    """A readout was malformed, non-finite, or in unexpected units."""


@dataclass(frozen=True)
class Settings:
    voltage_v: float
    resistance_ohm: float = 1000.0

    def __post_init__(self) -> None:
        if not isfinite(self.voltage_v) or not 0 <= self.voltage_v <= 12:
            raise ValueError("voltage_v must be finite and between 0 and 12 V")
        if not isfinite(self.resistance_ohm) or not 100 <= self.resistance_ohm <= 10000:
            raise ValueError("resistance_ohm must be finite and between 100 and 10000 ohm")


@dataclass(frozen=True)
class Reading:
    voltage_v: float
    current_ma: float
    sequence: int
    revision: int


@dataclass(frozen=True)
class Limits:
    current_min_ma: float
    current_max_ma: float
    voltage_tolerance_v: float = 0.01

    def __post_init__(self) -> None:
        values = (self.current_min_ma, self.current_max_ma, self.voltage_tolerance_v)
        if not all(isfinite(value) for value in values):
            raise ValueError("limits must be finite")
        if self.current_min_ma > self.current_max_ma or self.voltage_tolerance_v < 0:
            raise ValueError("limits must be ordered and tolerance non-negative")

    def violations(self, reading: Reading, settings: Settings) -> list[str]:
        failures = []
        if abs(reading.voltage_v - settings.voltage_v) > self.voltage_tolerance_v:
            failures.append("voltage outside tolerance")
        if not self.current_min_ma <= reading.current_ma <= self.current_max_ma:
            failures.append("current outside limits")
        return failures
