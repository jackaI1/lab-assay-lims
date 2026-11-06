"""Typed bench supply API; callers do not need Selenium selectors."""

from math import isfinite

from .models import BadReading, InstrumentError, Reading, Settings
from .page import SupplyPage


class BenchSupply:
    def __init__(self, page: SupplyPage) -> None:
        self.page = page
        self._revision: int | None = None

    def connect(self) -> None:
        self._revision = None
        self.page.open()

    def configure(self, settings: Settings) -> None:
        self._revision = None
        self._revision = self.page.configure(settings)

    def measure(self) -> Reading:
        if self._revision is None:
            raise InstrumentError("Configure the supply before measuring")
        raw = self.page.acquire()
        try:
            voltage = float(raw["voltage"])
            current = float(raw["current"])
            sequence = int(raw["sequence"])
            revision = int(raw["revision"])
        except (ValueError, KeyError) as exc:
            raise BadReading(f"Malformed readout: {raw}") from exc
        if not isfinite(voltage) or not isfinite(current):
            raise BadReading("Readout must contain finite numbers")
        if raw["voltage_unit"] != "V" or raw["current_unit"] != "mA":
            raise BadReading("Expected readout units V and mA")
        if revision != self._revision:
            raise BadReading("Reading belongs to a different settings revision")
        return Reading(voltage, current, sequence, revision)

    def output_off(self) -> None:
        self._revision = None
        self.page.output_off()
