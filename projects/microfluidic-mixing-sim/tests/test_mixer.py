import numpy as np
import pytest
import ufl
from dolfinx import fem
from mixing.geometry import channel, floor
from mixing.solver import stokes, transport, sections, integral


@pytest.fixture(scope="module")
def solved():
    domain,tags = channel(.65,.25)
    velocity,pressure,flux = stokes(domain,tags,3)
    return domain,tags,velocity,pressure,flux


def test_real_three_dimensional_grooves(solved):
    domain,tags,u,p,flux = solved
    assert domain.geometry.x[:,2].min() < -.1
    assert domain.topology.dim == 3
    assert all(len(tags.find(i)) > 0 for i in [1,2,3,4])
    # Cross-stream motion must come from the solved geometry.
    assert integral(u[2]**2) > 1e-6
    assert flux["relative_imbalance"] < .01
    assert flux["1"]/flux["2"] == pytest.approx(1/3,rel=.01)


def test_transport_and_constant_preservation(solved):
    domain,tags,u,_,_ = solved
    # Low-Pe physical-range check; high-Pe SUPG overshoots are reported raw
    # in the sweep and are an explicit limitation, not hidden by clipping.
    c = transport(domain,tags,u,8)
    profile = sections(u,c,3,xs=[.5,8,15.5],n=20)
    assert c.x.array.min() >= -.015
    assert .99 <= c.x.array.max() <= 1.015
    assert all(-.05 < p["mixing_index"] <= 1 for p in profile)
    assert profile[-1]["mixing_index"] > profile[0]["mixing_index"]
    assert abs(profile[-1]["mean"]-.25) < .04
    uniform = transport(domain,tags,u,40,inlet_values=(.4,.4))
    assert np.max(np.abs(uniform.x.array-.4)) < 1e-9
    fine_samples = sections(u,c,3,xs=[15.5],n=48)
    assert abs(fine_samples[0]["mixing_index"]-profile[-1]["mixing_index"]) < .01


def test_floor_staggers():
    x = np.linspace(0,16,1000)
    assert floor(x,np.full_like(x,-.6),.25).min() < -.24
    assert not np.allclose(floor(x,np.full_like(x,-.6),.25),floor(x,np.full_like(x,.6),.25))
    assert np.all(floor(x,x*0,0) == 0)


def test_invalid_inputs(solved):
    domain,tags,u,_,_ = solved
    with pytest.raises(ValueError):
        stokes(domain,tags,0)
    with pytest.raises(ValueError):
        transport(domain,tags,u,0)
