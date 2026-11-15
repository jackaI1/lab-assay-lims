"""Water electrolysis: electricity, water and oxygen per kg of hydrogen.

Efficiency is stated on the higher heating value (HHV) of hydrogen, which is how most
electrolyser makers quote it. An efficiency of 0.70 means 70% of the electricity ends up
as hydrogen's HHV energy; the rest is lost as heat in the stack and the power supply.
"""

from __future__ import annotations

from process_model.constants import (
    HHV_H2_MJ_PER_KG,
    LHV_H2_MJ_PER_KG,
    M_H2,
    M_H2O,
    M_O2,
    MJ_PER_KWH,
)


def kwh_per_kg(efficiency_hhv: float, basis: str = "HHV") -> float:
    """Electricity needed for 1 kg of hydrogen at a stated efficiency (kWh per kg)."""
    if not 0.0 < efficiency_hhv <= 1.0:
        raise ValueError("efficiency must be above 0 and at most 1")
    if basis == "HHV":
        energy_mj = HHV_H2_MJ_PER_KG
    elif basis == "LHV":
        energy_mj = LHV_H2_MJ_PER_KG
    else:
        raise ValueError("basis must be 'HHV' or 'LHV'")
    return energy_mj / MJ_PER_KWH / efficiency_hhv


def water_kg_per_kg_h2() -> float:
    """Water consumed per kg of hydrogen, from 2 H2O -> 2 H2 + O2."""
    return 2.0 * M_H2O / (2.0 * M_H2)


def oxygen_kg_per_kg_h2() -> float:
    """Oxygen co-produced per kg of hydrogen."""
    return M_O2 / (2.0 * M_H2)


def water_mass_balance_error() -> float:
    """Water in minus hydrogen and oxygen out, per kg of hydrogen (should be about 0)."""
    return water_kg_per_kg_h2() - (1.0 + oxygen_kg_per_kg_h2())
