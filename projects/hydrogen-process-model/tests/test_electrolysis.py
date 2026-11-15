import pytest

from process_model.electrolysis import (
    kwh_per_kg,
    oxygen_kg_per_kg_h2,
    water_kg_per_kg_h2,
    water_mass_balance_error,
)


def test_hhv_energy_at_perfect_efficiency_is_the_heating_value_in_kwh():
    assert kwh_per_kg(1.0, "HHV") == pytest.approx(141.8 / 3.6)


def test_lower_heating_value_basis_gives_less_energy():
    assert kwh_per_kg(1.0, "LHV") == pytest.approx(120.0 / 3.6)
    assert kwh_per_kg(0.7, "LHV") < kwh_per_kg(0.7, "HHV")


def test_energy_scales_with_one_over_efficiency():
    assert kwh_per_kg(0.7) == pytest.approx(kwh_per_kg(1.0) / 0.7)


def test_water_and_oxygen_per_kg_hydrogen_match_the_reaction():
    assert water_kg_per_kg_h2() == pytest.approx(8.94, abs=0.01)
    assert oxygen_kg_per_kg_h2() == pytest.approx(7.94, abs=0.01)


def test_water_mass_balances_hydrogen_plus_oxygen():
    assert abs(water_mass_balance_error()) < 1e-3


@pytest.mark.parametrize("efficiency", [0.0, -0.1, 1.2])
def test_efficiency_outside_zero_to_one_is_rejected(efficiency):
    with pytest.raises(ValueError):
        kwh_per_kg(efficiency)


def test_unknown_basis_is_rejected():
    with pytest.raises(ValueError):
        kwh_per_kg(0.7, "GCV")
