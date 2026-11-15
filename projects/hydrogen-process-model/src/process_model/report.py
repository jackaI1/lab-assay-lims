"""Builds the comparison: the SMR sweep, the electrolyser cases and the cost of each route."""

from __future__ import annotations

from dataclasses import dataclass, replace

from process_model.cost import Assumptions, CostBreakdown, electrolysis_cost, smr_cost
from process_model.electrolysis import (
    kwh_per_kg,
    oxygen_kg_per_kg_h2,
    water_kg_per_kg_h2,
    water_mass_balance_error,
)
from process_model.smr import SmrPoint, equilibrium, sweep

SWEEP_TEMPERATURES_C = [750.0, 800.0, 850.0, 900.0, 950.0]
SWEEP_STEAM_TO_CARBON = [2.5, 3.0, 3.5]
ELECTROLYSER_EFFICIENCIES = [0.60, 0.70, 0.80]


@dataclass(frozen=True)
class ElectrolyserCase:
    efficiency_hhv: float
    kwh_per_kg: float
    water_kg_per_kg: float
    oxygen_kg_per_kg: float
    cost: CostBreakdown


@dataclass(frozen=True)
class Report:
    assumptions: Assumptions
    operating_point: SmrPoint
    smr: CostBreakdown
    electrolysis: CostBreakdown
    sweep: list[SmrPoint]
    sweep_costs: list[CostBreakdown]
    electrolyser_cases: list[ElectrolyserCase]
    water_balance_error: float

    @property
    def max_closure_error(self) -> float:
        """Largest closure error across every SMR sweep point and the water balance."""
        errors = [self.water_balance_error]
        for point in self.sweep:
            errors.extend(
                [
                    point.carbon_closure_error,
                    point.hydrogen_closure_error,
                    point.oxygen_closure_error,
                    point.mass_closure_error,
                ]
            )
        return max(abs(value) for value in errors)


def build_report(assumptions: Assumptions) -> Report:
    operating_point = equilibrium(
        assumptions.smr_temperature_c,
        assumptions.smr_steam_to_carbon,
        assumptions.smr_pressure_bar,
    )
    points = sweep(SWEEP_TEMPERATURES_C, SWEEP_STEAM_TO_CARBON, assumptions.smr_pressure_bar)
    cases = []
    for efficiency in ELECTROLYSER_EFFICIENCIES:
        case_assumptions = replace(assumptions, electrolyser_efficiency_hhv=efficiency)
        cases.append(
            ElectrolyserCase(
                efficiency_hhv=efficiency,
                kwh_per_kg=kwh_per_kg(efficiency),
                water_kg_per_kg=water_kg_per_kg_h2(),
                oxygen_kg_per_kg=oxygen_kg_per_kg_h2(),
                cost=electrolysis_cost(case_assumptions),
            )
        )
    return Report(
        assumptions=assumptions,
        operating_point=operating_point,
        smr=smr_cost(operating_point, assumptions),
        electrolysis=electrolysis_cost(assumptions),
        sweep=points,
        sweep_costs=[smr_cost(point, assumptions) for point in points],
        electrolyser_cases=cases,
        water_balance_error=water_mass_balance_error(),
    )
