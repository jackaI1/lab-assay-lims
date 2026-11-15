"""Steam methane reforming at chemical equilibrium, solved with Cantera.

The feed is 1 kmol CH4 plus `steam_to_carbon` kmol of H2O, as gas. The outlet is the
equilibrium mixture at the stated temperature and pressure, using the GRI-Mech 3.0
gas-phase mechanism that ships with Cantera. That mechanism has no solid carbon, so this
model cannot show carbon deposition, which is a real risk at low steam-to-carbon ratios.

Heat duty is the enthalpy the furnace must add: the outlet enthalpy at reformer conditions
minus the feed enthalpy at 25 degrees C. Enthalpy is taken per kg, and the feed mass is
the same before and after reaction, so the duty is a true energy balance.
"""

from __future__ import annotations

from dataclasses import dataclass

import cantera as ct

from process_model.constants import M_CH4, M_H2

MECHANISM = "gri30.yaml"
REFERENCE_TEMPERATURE_K = 298.15
KELVIN_OFFSET = 273.15
PA_PER_BAR = 1.0e5
MOL_PER_KMOL = 1000.0
KJ_PER_J = 1.0e-3


@dataclass(frozen=True)
class SmrPoint:
    """Equilibrium outlet and energy duty for one reformer condition.

    Amounts are per kmol of CH4 fed. The three closure errors compare the outlet with the
    feed for carbon, hydrogen and oxygen atoms; the mass closure error compares total mass.
    All of them should be at rounding level (about 1e-9).
    """

    temperature_c: float
    steam_to_carbon: float
    pressure_bar: float
    h2_per_ch4: float
    ch4_conversion: float
    h2_mole_fraction_dry: float
    duty_kj_per_mol_h2: float
    carbon_closure_error: float
    hydrogen_closure_error: float
    oxygen_closure_error: float
    mass_closure_error: float

    @property
    def ch4_kg_per_kg_h2(self) -> float:
        """Methane fed per kg of hydrogen produced. The ideal reaction needs about 2.0 kg."""
        mol_h2_per_kg = 1000.0 / M_H2
        return mol_h2_per_kg / self.h2_per_ch4 * M_CH4 / 1000.0

    @property
    def duty_mj_per_kg_h2(self) -> float:
        """Reformer heat duty per kg of hydrogen produced, in MJ."""
        mol_h2_per_kg = 1000.0 / M_H2
        return self.duty_kj_per_mol_h2 * mol_h2_per_kg / 1000.0


def _relative_error(actual: float, expected: float) -> float:
    return abs(actual - expected) / abs(expected)


def _atoms_per_mole(gas: ct.Solution) -> dict[str, float]:
    """Carbon, hydrogen and oxygen atoms in one mole of the gas at its current composition."""
    x = gas.X
    totals = {"C": 0.0, "H": 0.0, "O": 0.0}
    for index, name in enumerate(gas.species_names):
        for element in totals:
            totals[element] += x[index] * gas.n_atoms(name, element)
    return totals


def equilibrium(
    temperature_c: float, steam_to_carbon: float, pressure_bar: float = 25.0
) -> SmrPoint:
    """Solve the reformer outlet at one temperature, steam-to-carbon ratio and pressure."""
    if not 500.0 <= temperature_c <= 1200.0:
        raise ValueError("temperature_c must be between 500 and 1200 degrees C")
    if steam_to_carbon < 1.0:
        raise ValueError("steam_to_carbon must be at least 1.0 (the reaction needs one H2O per C)")
    if pressure_bar <= 0.0:
        raise ValueError("pressure_bar must be positive")

    gas = ct.Solution(MECHANISM)
    pressure_pa = pressure_bar * PA_PER_BAR
    feed = {"CH4": 1.0, "H2O": steam_to_carbon}

    # Feed per kmol CH4: 1 C, (4 + 2 S/C) H and S/C O atoms. Mass uses Cantera's own molar
    # masses so that the mass check compares like with like (numerically kg per kmol).
    feed_atoms = {"C": 1.0, "H": 4.0 + 2.0 * steam_to_carbon, "O": steam_to_carbon}
    molar_mass = dict(zip(gas.species_names, gas.molecular_weights, strict=True))
    feed_mass = molar_mass["CH4"] + steam_to_carbon * molar_mass["H2O"]

    gas.TPX = REFERENCE_TEMPERATURE_K, pressure_pa, feed
    feed_enthalpy = gas.enthalpy_mass

    gas.TPX = temperature_c + KELVIN_OFFSET, pressure_pa, feed
    gas.equilibrate("TP")

    atoms = _atoms_per_mole(gas)
    outlet_kmol = feed_atoms["C"] / atoms["C"]
    x = dict(zip(gas.species_names, gas.X, strict=True))
    h2_kmol = outlet_kmol * x["H2"]
    if h2_kmol <= 0.0:
        raise RuntimeError("equilibrium solver returned no hydrogen")
    ch4_kmol = outlet_kmol * x["CH4"]
    dry_kmol = outlet_kmol * (1.0 - x["H2O"])

    duty_joules = (gas.enthalpy_mass - feed_enthalpy) * feed_mass
    return SmrPoint(
        temperature_c=float(temperature_c),
        steam_to_carbon=float(steam_to_carbon),
        pressure_bar=float(pressure_bar),
        h2_per_ch4=float(h2_kmol),
        ch4_conversion=float(1.0 - ch4_kmol),
        h2_mole_fraction_dry=float(h2_kmol / dry_kmol),
        duty_kj_per_mol_h2=float(duty_joules * KJ_PER_J / (h2_kmol * MOL_PER_KMOL)),
        carbon_closure_error=_relative_error(atoms["C"] * outlet_kmol, feed_atoms["C"]),
        hydrogen_closure_error=_relative_error(atoms["H"] * outlet_kmol, feed_atoms["H"]),
        oxygen_closure_error=_relative_error(atoms["O"] * outlet_kmol, feed_atoms["O"]),
        mass_closure_error=_relative_error(outlet_kmol * gas.mean_molecular_weight, feed_mass),
    )


def sweep(
    temperatures_c: list[float], steam_to_carbon_ratios: list[float], pressure_bar: float = 25.0
) -> list[SmrPoint]:
    """Equilibrium points for every combination of temperature and steam-to-carbon ratio."""
    return [
        equilibrium(temperature, ratio, pressure_bar)
        for ratio in steam_to_carbon_ratios
        for temperature in temperatures_c
    ]
