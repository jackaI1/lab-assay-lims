import numpy as np
import pytest

from drug_release.analysis import analyze, information_criteria
from drug_release.models import MODELS, fit, predict


@pytest.mark.parametrize(
    "name,params,formula",
    [
        ("zero_order", [0.04], lambda t: 0.04 * t),
        ("first_order", [0.2], lambda t: 1 - np.exp(-0.2 * t)),
        ("higuchi", [0.15], lambda t: 0.15 * np.sqrt(t)),
        ("korsmeyer_peppas", [0.12, 0.65], lambda t: 0.12 * t**0.65),
        ("weibull", [7.0, 1.4], lambda t: 1 - np.exp(-((t / 7) ** 1.4))),
    ],
)
def test_known_parameters_and_noisy_recovery(name, params, formula):
    t = np.linspace(0.1, 8, 35)
    y = formula(t)
    np.testing.assert_allclose(predict(name, t, params), y, atol=1e-12)
    np.testing.assert_allclose(fit(name, t, y), params, rtol=1e-4)
    noisy = y + np.random.default_rng(4).normal(0, 0.002, len(t))
    np.testing.assert_allclose(fit(name, t, noisy), params, rtol=0.04)


def test_aicc_counts_variance_and_handles_sparse_data():
    aic, aicc = information_criteria(0.04, 10, 2)
    expected = 10 * np.log(0.04 / 10) + 2 * 3
    assert aic == pytest.approx(expected)
    assert aicc == pytest.approx(expected + 2 * 3 * 4 / (10 - 3 - 1))
    assert information_criteria(0.04, 4, 2)[1] is None


def test_scopes_holdout_and_bootstrap():
    t = np.linspace(0.2, 10, 24)
    y = 1 - np.exp(-0.2 * t)
    report = analyze(t, y, bootstrap=30, seed=7, error=0.00005)
    early, full = report["scopes"]
    assert set(early["models"]) == set(MODELS)
    assert "korsmeyer_peppas" not in full["models"]
    assert max(y[early["indices"]]) <= 0.6
    assert len(early["indices"]) < len(t)
    for scope in report["scopes"]:
        train, test = scope["train_indices"], scope["test_indices"]
        assert set(train).isdisjoint(test)
        assert sorted(train + test) == scope["indices"]
        for name, result in scope["models"].items():
            pars = fit(name, t[train], y[train])
            expected = np.sqrt(np.mean((predict(name, t[test], pars) - y[test]) ** 2)) * 100
            assert result["heldout_rmse_pp"] == pytest.approx(expected)
            assert result["bootstrap_success"] == 30
            assert len(result["ci95"]) == len(result["parameters"])
    assert report == analyze(t, y, bootstrap=30, seed=7, error=0.00005)
    assert any("60%" in w for w in report["warnings"])


def test_ambiguity_when_first_order_and_weibull_indistinguishable():
    t = np.linspace(0.1, 8, 24)
    y = 1 - np.exp(-t / 5)
    r = analyze(t, y, bootstrap=20)
    assert any("cannot separate" in w.lower() for w in r["scopes"][1]["warnings"])


@pytest.mark.parametrize(
    "t,y",
    [
        ([1, 1, 2], [0.1, 0.2, 0.3]),
        ([1, 2, 3], [0.1, float("nan"), 0.3]),
        ([-1, 2, 3], [0.1, 0.2, 0.3]),
        ([1, 2, 3], [10, 20, 30]),
        ([0, 1, 2], [0.1, 0.2, 0.3]),
        ([1, 2], [0.1]),
    ],
)
def test_invalid_inputs(t, y):
    with pytest.raises(ValueError):
        analyze(t, y, bootstrap=20)


def test_sparse_early_scope_is_reported_without_fabricated_fit():
    r = analyze(np.arange(1, 10), np.linspace(0.5, 0.95, 9), bootstrap=20)
    assert not r["scopes"][0]["models"]
    assert any("Insufficient" in w for w in r["scopes"][0]["warnings"])


def test_zero_baseline_omitted_from_scores_and_decrease_flagged():
    t = np.arange(10.0)
    y = np.array([0, 0.1, 0.2, 0.19, 0.35, 0.4, 0.45, 0.5, 0.55, 0.59])
    r = analyze(t, y, bootstrap=20)
    assert 0 not in r["scopes"][0]["indices"]
    assert any("decrease" in w for w in r["warnings"])


def test_late_dip_does_not_reenter_early_scope():
    t = np.arange(1.0, 12)
    y = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.61, 0.59, 0.7, 0.8, 0.9])
    r = analyze(t, y, bootstrap=20)
    assert r["scopes"][0]["indices"] == list(range(6))


def test_bootstrap_interval_contains_known_noisy_parameter():
    t = np.linspace(0.2, 9, 30)
    y = 1 - np.exp(-0.2 * t) + np.random.default_rng(42).normal(0, 0.005, len(t))
    r = analyze(t, y, bootstrap=100, seed=3, error=0.00005)
    lo, hi = r["scopes"][1]["models"]["first_order"]["ci95"][0]
    assert lo < 0.2 < hi


def test_beyond_complete_release_warns_without_clipping():
    t = np.arange(1.0, 13)
    y = np.minimum(0.09 * t, 1)
    r = analyze(t, y, bootstrap=20)
    assert any("exceeds 100%" in w for w in r["scopes"][1]["models"]["zero_order"]["warnings"])


def test_saved_residual_sign_matches_observed_minus_fitted():
    t = np.arange(1.0, 10)
    y = np.array([0.1, 0.11, 0.2, 0.3, 0.35, 0.5, 0.6, 0.7, 0.9])
    report = analyze(t, y, bootstrap=20)
    scope = report["scopes"][1]
    result = scope["models"]["zero_order"]
    fitted = predict("zero_order", t, list(result["parameters"].values()))
    np.testing.assert_allclose(result["residuals_pp"], (y - fitted) * 100)


@pytest.mark.parametrize("constant", [0.0, 0.5, 1.0])
def test_flat_curve_withholds_unidentifiable_parameters(constant):
    report = analyze(np.arange(1.0, 9), np.full(8, constant), bootstrap=20)
    for scope in report["scopes"]:
        assert not scope["models"]
        assert any("Insufficient" in w for w in scope["warnings"])


def test_response_below_stated_rounding_precision_withholds_fit():
    report = analyze(np.arange(1.0, 9), np.linspace(0.2, 0.20008, 8), bootstrap=20, error=0.00005)
    assert not report["scopes"][1]["models"]


@pytest.mark.parametrize(
    "name,parameters",
    [
        ("zero_order", [1e-8]),
        ("first_order", [1e-8]),
        ("higuchi", [1e-8]),
        ("korsmeyer_peppas", [1e-8, 0.65]),
        ("weibull", [1e6, 1.4]),
    ],
)
def test_tiny_response_does_not_cause_false_optimizer_convergence(name, parameters):
    t = np.arange(1.0, 9)
    y = predict(name, t, parameters)
    np.testing.assert_allclose(fit(name, t, y), parameters, rtol=0.001)
