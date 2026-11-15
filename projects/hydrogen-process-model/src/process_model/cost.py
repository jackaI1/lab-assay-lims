"""Hydrogen cost per kg from energy prices and capital assumptions.

Capital is turned into an annual charge with a capital recovery factor (CRF), the share of
a loan's value paid each year at a given interest rate over the plant life. Fixed operating
cost is a fixed share of capital each year. Both are divided by the kg the plant makes per year.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, fields
from pathlib import Path

from process_model.constants import LHV_CH4_KJ_PER_MOL, M_CH4, MJ_PER_KWH
from process_model.electrolysis import kwh_per_kg
from process_model.smr import SmrPoint


@dataclass(frozen=True)
class Assumptions:
    """Every number the cost comparison depends on. Values come from a TOML file."""

    natural_gas_price_per_gj: float
    electricity_price_per_kwh: float
    discount_rate: float
    lifetime_years: int
    fixed_om_fraction: float
    availability: float
    plant_kg_per_day: float
    smr_capex_per_kg_per_day: float
    electrolyser_capex_per_kw: float
    furnace_efficiency: float
    electrolyser_efficiency_hhv: float
    smr_temperature_c: float
    smr_steam_to_carbon: float
    smr_pressure_bar: float

    @classmethod
    def from_toml(cls, path: str | Path) -> Assumptions:
        with Path(path).open("rb") as handle:
            data = tomllib.load(handle)
        names = [field.name for field in fields(cls)]
        missing = sorted(set(names) - data.keys())
        if missing:
            raise ValueError(f"assumptions file is missing: {', '.join(missing)}")
        assumptions = cls(**{name: data[name] for name in names})
        assumptions.validate()
        return assumptions

    def validate(self) -> None:
        if not 0.0 < self.availability <= 1.0:
            raise ValueError("availability must be above 0 and at most 1")
        if not 0.0 < self.furnace_efficiency <= 1.0:
            raise ValueError("furnace_efficiency must be above 0 and at most 1")
        if not 0.0 < self.electrolyser_efficiency_hhv <= 1.0:
            raise ValueError("electrolyser_efficiency_hhv must be above 0 and at most 1")
        if self.discount_rate < 0.0 or self.lifetime_years <= 0:
            raise ValueError("discount_rate must be zero or more and lifetime_years positive")
        if self.plant_kg_per_day <= 0.0:
            raise ValueError("plant_kg_per_day must be positive")


@dataclass(frozen=True)
class CostBreakdown:
    """Cost per kg of hydrogen, split into its parts."""

    route: str
    energy_kwh_per_kg: float
    energy_cost_per_kg: float
    capex_cost_per_kg: float
    fixed_om_cost_per_kg: float
    annual_kg: float

    @property
    def total_cost_per_kg(self) -> float:
        return self.energy_cost_per_kg + self.capex_cost_per_kg + self.fixed_om_cost_per_kg


def capital_recovery_factor(rate: float, years: int) -> float:
    """Share of a capital cost paid each year, at interest rate `rate` over `years`."""
    if rate == 0.0:
        return 1.0 / years
    growth = (1.0 + rate) ** years
    return rate * growth / (growth - 1.0)


def annual_output_kg(assumptions: Assumptions) -> float:
    return assumptions.plant_kg_per_day * 365.0 * assumptions.availability


def smr_cost(point: SmrPoint, assumptions: Assumptions) -> CostBreakdown:
    """Cost per kg for steam methane reforming at the operating point `point`.

    Energy is the methane fed as feedstock (LHV) plus the methane burned in the furnace to
    supply the reforming heat duty, divided by the furnace efficiency.
    """
    mol_ch4_per_kg_h2 = point.ch4_kg_per_kg_h2 * 1000.0 / M_CH4
    feed_mj = mol_ch4_per_kg_h2 * LHV_CH4_KJ_PER_MOL / 1000.0
    fuel_mj = point.duty_mj_per_kg_h2 / assumptions.furnace_efficiency
    energy_mj = feed_mj + fuel_mj
    energy_cost = (energy_mj / 1000.0) * assumptions.natural_gas_price_per_gj
    capex_total = assumptions.smr_capex_per_kg_per_day * assumptions.plant_kg_per_day
    return _breakdown("SMR", energy_mj / MJ_PER_KWH, energy_cost, capex_total, assumptions)


def electrolysis_cost(assumptions: Assumptions) -> CostBreakdown:
    """Cost per kg for water electrolysis at the stated efficiency and prices."""
    energy_kwh = kwh_per_kg(assumptions.electrolyser_efficiency_hhv)
    energy_cost = energy_kwh * assumptions.electricity_price_per_kwh
    stack_kw = assumptions.plant_kg_per_day * energy_kwh / (24.0 * assumptions.availability)
    capex_total = stack_kw * assumptions.electrolyser_capex_per_kw
    return _breakdown("Electrolysis", energy_kwh, energy_cost, capex_total, assumptions)


def _breakdown(
    route: str,
    energy_kwh: float,
    energy_cost: float,
    capex_total: float,
    assumptions: Assumptions,
) -> CostBreakdown:
    annual_kg = annual_output_kg(assumptions)
    annual_capex = capex_total * capital_recovery_factor(
        assumptions.discount_rate, assumptions.lifetime_years
    )
    annual_fixed_om = capex_total * assumptions.fixed_om_fraction
    return CostBreakdown(
        route=route,
        energy_kwh_per_kg=energy_kwh,
        energy_cost_per_kg=energy_cost,
        capex_cost_per_kg=annual_capex / annual_kg,
        fixed_om_cost_per_kg=annual_fixed_om / annual_kg,
        annual_kg=annual_kg,
    )
