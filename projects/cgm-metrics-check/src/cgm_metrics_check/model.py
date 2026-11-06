"""Validated original sensor quantities. No unit inference or clinical filtering."""
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import math

MG_PER_MMOL = 18.0182


def utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('timestamp must include a timezone offset')
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class Reading:
    timestamp: datetime
    value: float
    unit: str

    def __post_init__(self):
        utc(self.timestamp)
        offset = self.timestamp.utcoffset()
        if abs(offset) > timedelta(hours=14) or offset.total_seconds() % 60:
            raise ValueError('timestamp offset must use whole minutes within +/-14:00 for FHIR R4')
        if self.unit not in ('mg/dL', 'mmol/L'):
            raise ValueError('unit must be mg/dL or mmol/L; units are never guessed')
        if isinstance(self.value, bool) or not isinstance(self.value, (int, float)) or not math.isfinite(self.value) or self.value <= 0:
            raise ValueError('glucose must be a finite positive number')
        if not math.isfinite(self.mg_dl):
            raise ValueError('normalized glucose must be finite after unit conversion')

    @property
    def mg_dl(self) -> float:
        return self.value if self.unit == 'mg/dL' else self.value * MG_PER_MMOL
