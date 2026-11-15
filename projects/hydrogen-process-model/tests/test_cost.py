from dataclasses import replace

import pytest

from process_model.constants import LHV_CH4_KJ_PER_MOL, M_CH4
from process_model.cost import (
    Assumptions,
    annual_output_kg,
    capital_recovery_factor,
    electrolysis_cost,
    smr_cost,
)
from process_model.smr import equilibrium

HOURS_PER_DAY = 24.0


def test_capital_recovery_factor_matches_the_standard_formula():
    # 8% over 20 years, the textbook value
    assert capital_recovery_factor(0.08, 20) == pytest.approx(0.1018522, rel=1e-6)


def test_capital_recovery_factor_without_interest_is_straight_line():
    assert capital_recovery_factor(0.0, 10) == pytest.approx(0.1)


def test_electrolysis_cost_matches_a_hand_calculation(assumptions):
    cost = electrolysis_cost(assumptions)

    kwh = 141.8 / 3.6 / assumptions.electrolyser_efficiency_hhv
    kw = assumptions.plant_kg_per_day * kwh / (HOURS_PER_DAY * assumptions.availability)
    capex = kw * assumptions.electrolyser_capex_per_kw
    annual_kg = assumptions.plant_kg_per_day * 365 * assumptions.availability
    crf = capital_recovery_factor(assumptions.discount_rate, assumptions.lifetime_years)

    assert cost.energy_kwh_per_kg == pytest.approx(kwh)
    assert cost.energy_cost_per_kg == pytest.approx(kwh * assumptions.electricity_price_per_kwh)
    assert cost.capex_cost_per_kg == pytest.approx(capex * crf / annual_kg)
    assert cost.fixed_om_cost_per_kg == pytest.approx(
        capex * assumptions.fixed_om_fraction / annual_kg
    )
    assert cost.total_cost_per_kg == pytest.approx(
        cost.energy_cost_per_kg + cost.capex_cost_per_kg + cost.fixed_om_cost_per_kg
    )


def test_smr_energy_is_feed_plus_furnace_fuel(assumptions):
    point = equilibrium(assumptions.smr_temperature_c, assumptions.smr_steam_to_carbon)
    cost = smr_cost(point, assumptions)

    feed_mj = point.ch4_kg_per_kg_h2 * 1000 / M_CH4 * LHV_CH4_KJ_PER_MOL / 1000
    fuel_mj = point.duty_mj_per_kg_h2 / assumptions.furnace_efficiency
    assert cost.energy_kwh_per_kg == pytest.approx((feed_mj + fuel_mj) / 3.6)
    assert cost.energy_cost_per_kg == pytest.approx(
        (feed_mj + fuel_mj) / 1000 * assumptions.natural_gas_price_per_gj
    )


def test_smr_feed_energy_is_near_the_ideal_value(assumptions):
    # About 2 kg of methane per kg of hydrogen at full conversion, so about 100 MJ of feed.
    point = equilibrium(assumptions.smr_temperature_c, assumptions.smr_steam_to_carbon)
    feed_mj = point.ch4_kg_per_kg_h2 * 1000 / M_CH4 * LHV_CH4_KJ_PER_MOL / 1000

    assert 95.0 < feed_mj < 160.0


def test_lower_availability_spreads_the_same_capital_over_less_hydrogen(assumptions):
    point = equilibrium(assumptions.smr_temperature_c, assumptions.smr_steam_to_carbon)
    full = smr_cost(point, assumptions)
    half = smr_cost(point, replace(assumptions, availability=assumptions.availability / 2))

    assert half.capex_cost_per_kg == pytest.approx(full.capex_cost_per_kg * 2)
    assert annual_output_kg(replace(assumptions, availability=0.45)) == pytest.approx(
        annual_output_kg(assumptions) / 2
    )


def test_assumptions_load_from_the_shipped_file(assumptions):
    assert assumptions.plant_kg_per_day == 1000.0
    assert assumptions.electrolyser_efficiency_hhv == 0.70


def test_missing_assumption_is_reported(tmp_path):
    path = tmp_path / "partial.toml"
    path.write_text("natural_gas_price_per_gj = 4.0\n")

    with pytest.raises(ValueError, match="missing"):
        Assumptions.from_toml(path)


def test_invalid_availability_is_rejected(tmp_path, assumptions):
    with pytest.raises(ValueError, match="availability"):
        replace(assumptions, availability=1.5).validate()
