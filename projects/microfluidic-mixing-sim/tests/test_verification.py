import pytest
from mixing.verification import poiseuille, momentum, diffusion
from mixing.study import physical


def test_coupled_stokes_poiseuille():
    result = poiseuille(8)
    assert result["velocity_L2"] < 1e-9
    assert result["pressure_L2"] < 1e-8


@pytest.mark.parametrize("solve",[momentum,diffusion])
def test_analytic_mesh_convergence(solve):
    errors = [solve(n)["L2"] for n in [8,16,32]]
    assert errors[-1] < .002
    assert errors[0]/errors[1] > 3.5
    assert errors[1]/errors[2] > 3.5


def test_physical_units():
    p = physical(1)
    assert p["U_m_s"] == pytest.approx(8.333333333e-4)
    assert p["Pe_H"] == pytest.approx(83.33333333)
    assert p["Re_H"] == pytest.approx(.08333333333)
    assert p["diffusion_time_s"] == pytest.approx(40)
