from datetime import date

import pytest

from calibration_inspection_log.rules import calibration_status, check_tolerance


@pytest.mark.parametrize(
    ("measured", "expected"),
    [
        ("9.949999", "LOW"),
        ("9.95", "PASS"),
        ("10.00", "PASS"),
        ("10.05", "PASS"),
        ("10.050001", "HIGH"),
    ],
)
def test_drawing_limits_are_inclusive_without_rounding(measured, expected):
    assert check_tolerance(measured, "9.95", "10.05") == expected


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", "", "abc", "1e10000"])
def test_invalid_measurements_are_rejected(value):
    with pytest.raises(ValueError):
        check_tolerance(value, "0", "1")


def test_reversed_limits_are_rejected():
    with pytest.raises(ValueError):
        check_tolerance("1", "2", "0")


def test_equal_limits_and_negative_deviation_work():
    assert check_tolerance("-0.01", "-0.01", "-0.01") == "PASS"


@pytest.mark.parametrize(
    ("as_of", "expected"),
    [
        ("2026-01-01", "CURRENT"),
        ("2026-01-30", "DUE_SOON"),
        ("2026-02-28", "DUE_TODAY"),
        ("2026-03-01", "OVERDUE"),
    ],
)
def test_due_date_boundaries(as_of, expected):
    assert calibration_status("2026-01-01", "2026-02-28", False, as_of, 30) == expected


def test_failed_calibration_takes_priority_over_due_date():
    assert calibration_status("2026-01-01", "2027-01-01", True, "2026-02-01") == "OUT_OF_TOLERANCE"


def test_missing_or_future_calibration_is_not_valid():
    assert calibration_status(None, None, False, "2026-01-01") == "UNCALIBRATED"
    assert calibration_status("2026-02-01", "2027-02-01", False, "2026-01-01") == "UNCALIBRATED"


def test_leap_day_and_date_objects():
    assert calibration_status("2024-02-29", "2024-03-01", False, date(2024, 2, 29)) == "DUE_SOON"


@pytest.mark.parametrize(
    ("calibrated", "due", "window"),
    [
        ("2026-02-30", "2027-01-01", 30),
        ("2026-02-01", "2026-01-01", 30),
        ("2026-01-01", "2027-01-01", -1),
    ],
)
def test_bad_dates_and_warning_window_are_rejected(calibrated, due, window):
    with pytest.raises(ValueError):
        calibration_status(calibrated, due, False, "2026-02-01", window)


def test_huge_exponent_is_rejected_as_validation_error():
    with pytest.raises(ValueError):
        check_tolerance("1e1000000", "0", "1")


def test_week_dates_are_not_accepted_as_calendar_date_strings():
    with pytest.raises(ValueError):
        calibration_status("2026-W01-1", "2027-01-01", False, "2026-01-01")
