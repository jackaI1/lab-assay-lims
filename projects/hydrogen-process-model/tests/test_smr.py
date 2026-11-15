import pytest

from process_model.smr import equilibrium, sweep

CLOSURE_TOLERANCE = 1e-9


@pytest.mark.parametrize(
    ("temperature_c", "steam_to_carbon", "pressure_bar"),
    [(700, 2.5, 25), (800, 3.0, 25), (900, 3.5, 30), (950, 2.5, 1)],
)
def test_outlet_conserves_carbon_hydrogen_oxygen_and_mass(
    temperature_c, steam_to_carbon, pressure_bar
):
    point = equilibrium(temperature_c, steam_to_carbon, pressure_bar)

    assert point.carbon_closure_error < CLOSURE_TOLERANCE
    assert point.hydrogen_closure_error < CLOSURE_TOLERANCE
    assert point.oxygen_closure_error < CLOSURE_TOLERANCE
    assert point.mass_closure_error < CLOSURE_TOLERANCE


def test_hotter_reformer_converts_more_methane_and_makes_more_hydrogen():
    cooler = equilibrium(750, 3.0)
    hotter = equilibrium(900, 3.0)

    assert hotter.ch4_conversion > cooler.ch4_conversion
    assert hotter.h2_per_ch4 > cooler.h2_per_ch4


def test_more_steam_makes_more_hydrogen_per_methane():
    drier = equilibrium(850, 2.5)
    wetter = equilibrium(850, 3.5)

    assert wetter.h2_per_ch4 > drier.h2_per_ch4


def test_lower_pressure_favours_conversion():
    high_pressure = equilibrium(850, 3.0, pressure_bar=25)
    low_pressure = equilibrium(850, 3.0, pressure_bar=1)

    assert low_pressure.ch4_conversion > high_pressure.ch4_conversion


def test_heat_duty_is_at_least_the_reforming_reaction_enthalpy():
    # CH4 + H2O -> CO + 3 H2 needs about 206 kJ per mol CH4 at 25 C, which is about 69 kJ per
    # mol H2. Heating the products to 900 C adds sensible heat on top of that.
    point = equilibrium(900, 3.0)

    assert point.duty_kj_per_mol_h2 > 68.0
    assert point.duty_mj_per_kg_h2 == pytest.approx(
        point.duty_kj_per_mol_h2 * 1000 / 2.01588 / 1000
    )


def test_methane_per_kg_hydrogen_is_near_the_ideal_two_kilograms():
    point = equilibrium(900, 3.0)

    assert point.ch4_kg_per_kg_h2 > 1.98


def test_dry_hydrogen_fraction_is_a_mole_fraction():
    point = equilibrium(850, 3.0)

    assert 0.0 < point.h2_mole_fraction_dry < 1.0


def test_sweep_covers_every_combination():
    points = sweep([800.0, 900.0], [2.5, 3.0, 3.5])

    assert len(points) == 6
    assert {(p.temperature_c, p.steam_to_carbon) for p in points} == {
        (800.0, 2.5),
        (800.0, 3.0),
        (800.0, 3.5),
        (900.0, 2.5),
        (900.0, 3.0),
        (900.0, 3.5),
    }


@pytest.mark.parametrize(
    ("temperature_c", "steam_to_carbon", "pressure_bar", "message"),
    [
        (400, 3.0, 25, "temperature_c"),
        (900, 0.5, 25, "steam_to_carbon"),
        (900, 3.0, 0, "pressure_bar"),
    ],
)
def test_out_of_range_inputs_are_rejected(temperature_c, steam_to_carbon, pressure_bar, message):
    with pytest.raises(ValueError, match=message):
        equilibrium(temperature_c, steam_to_carbon, pressure_bar)
