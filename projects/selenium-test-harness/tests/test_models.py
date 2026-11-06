import math

import pytest

from instrument_harness import Limits, Reading, Settings, SupplyPage


@pytest.mark.parametrize("voltage", [-1, 13, math.nan, math.inf])
def test_rejects_unsafe_voltage(voltage):
    with pytest.raises(ValueError, match="voltage_v"):
        Settings(voltage)


@pytest.mark.parametrize("resistance", [0, 99, 10001, math.nan, math.inf])
def test_rejects_unsafe_resistance(resistance):
    with pytest.raises(ValueError, match="resistance_ohm"):
        Settings(1, resistance)


@pytest.mark.parametrize("values", [(2, 1, 0.01), (0, 1, -1), (0, math.inf, 0.01)])
def test_rejects_invalid_limits(values):
    with pytest.raises(ValueError):
        Limits(*values)


def test_voltage_and_current_limits_are_independent_and_inclusive():
    limits = Limits(4.9, 5.1, 0.1)
    assert limits.violations(Reading(5, 4.9, 1, 1), Settings(5)) == []
    assert limits.violations(Reading(5, 5.1, 1, 1), Settings(5)) == []
    assert limits.violations(Reading(6, 8, 1, 1), Settings(5)) == [
        "voltage outside tolerance",
        "current outside limits",
    ]


@pytest.mark.parametrize("timeout", [0, -1, math.nan, math.inf])
def test_wait_deadline_cannot_be_infinite(timeout):
    with pytest.raises(ValueError, match="finite and positive"):
        SupplyPage(None, "http://127.0.0.1/", timeout=timeout)
