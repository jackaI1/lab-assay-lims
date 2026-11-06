"""Date-only calibration policy and exact drawing-limit comparisons."""

from datetime import date
from decimal import Decimal, InvalidOperation

USABLE = frozenset({"CURRENT", "DUE_SOON", "DUE_TODAY"})


def parse_date(value):
    """Accept ISO calendar dates or date objects, never timestamps."""
    if type(value) is date:
        return value
    if not isinstance(value, str) or len(value) != 10:
        raise ValueError("Use a date in YYYY-MM-DD format")
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("Use a date in YYYY-MM-DD format")
    return parsed


def dimension(value):
    """Limit input to finite, Excel-safe dimensions with six decimal places."""
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("Dimension must be a finite decimal number") from exc
    if not number.is_finite() or number.copy_abs() >= Decimal("1000000000"):
        raise ValueError("Dimension must be finite and smaller than 1 billion in magnitude")
    if number.as_tuple().exponent < -6:
        raise ValueError("Dimension supports at most six decimal places")
    return number


def check_tolerance(measured, lower, upper):
    """Return LOW, PASS or HIGH. Both drawing limits are included."""
    measured, lower, upper = map(dimension, (measured, lower, upper))
    if lower > upper:
        raise ValueError("Lower drawing limit must not exceed upper limit")
    return "LOW" if measured < lower else "HIGH" if measured > upper else "PASS"


def calibration_status(calibrated, due, out_of_tolerance, as_of, warning_days=30):
    """A calibration stays valid through its due date, unless it failed."""
    as_of = parse_date(as_of)
    if type(warning_days) is not int or warning_days < 0:
        raise ValueError("Warning days must be a nonnegative integer")
    if calibrated is None or due is None:
        return "UNCALIBRATED"
    calibrated, due = parse_date(calibrated), parse_date(due)
    if due < calibrated:
        raise ValueError("Due date must be on or after calibration date")
    if calibrated > as_of:
        return "UNCALIBRATED"
    if out_of_tolerance:
        return "OUT_OF_TOLERANCE"
    remaining = (due - as_of).days
    if remaining < 0:
        return "OVERDUE"
    if remaining == 0:
        return "DUE_TODAY"
    return "DUE_SOON" if remaining <= warning_days else "CURRENT"
