import numpy as np
import pytest
from mineral_assay.titration import Curve, equivalence, gran, concentration, replicate_summary
from mineral_assay.xrf import fit_spectrum, calibrate
from mineral_assay.flotation import reconcile, grade_prediction_flags

def test_replicates_known_acid():
    curves = [Curve.csv(f'examples/acid_replicate_{i}.csv') for i in range(1,4)]
    for curve in curves:
        for method in ('first','second'):
            endpoint = equivalence(curve, method, search=(8,12))
            assert concentration(endpoint, .1, 20) == pytest.approx(.05, abs=.001)
        assert gran(curve, 20, (4,8)) == pytest.approx(10, abs=.3)
    assert replicate_summary([concentration(equivalence(c, search=(8,12)), .1, 20) for c in curves])['n'] == 3

def test_weak_acid_gran_and_potential():
    v = np.linspace(1, 9, 81)
    # Henderson-Hasselbalch buffer region, endpoint 10 mL.
    curve = Curve(v, 4.76 + np.log10(v/(10-v)))
    assert gran(curve, 20, (3,8), 'weak_acid') == pytest.approx(10)
    v = np.linspace(0,20,201)
    potential = Curve(v, 200*np.tanh((v-10)/.4), 'potential')
    assert equivalence(potential, 'second', search=(8,12)) == pytest.approx(10, abs=.3)

def test_back_titration_and_uncertainty():
    assert concentration(10, .1, 20, initial_reagent_mol=.003) == pytest.approx(.1)
    assert concentration(10, .1, 20, analyte_per_titrant=.5) == pytest.approx(.025)
    assert replicate_summary([.04,.05,.06])['sd'] == pytest.approx(.01)
    with pytest.raises(ValueError): concentration(10,.1,20,initial_reagent_mol=.0005)

def test_xrf_calibration():
    data = np.genfromtxt('examples/xrf_sample.csv', delimiter=',', names=True)
    fit = fit_spectrum(data['energy_kev'],data['counts'],['Fe','Cu'])
    assert fit['areas']['Fe'] == pytest.approx(30, rel=.001)
    assert fit['areas']['Cu'] == pytest.approx(18, rel=.001)
    assert calibrate(fit['areas']['Fe'], [10,30,50],[.02,.06,.10]) == pytest.approx(.06, rel=.001)

def test_flows_and_physical_flags():
    r = reconcile(.02,.12,.008,.1,[.002,.006,.001],.01)
    assert r['feed'] == pytest.approx(r['mass_pull']*r['concentrate']+(1-r['mass_pull'])*r['tailings'])
    assert 0 <= r['recovery'] <= 1
    assert grade_prediction_flags(.02,.1,.25)
    assert not grade_prediction_flags(.02,.1,.15)
