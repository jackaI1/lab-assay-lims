import json
from dataclasses import replace

import numpy as np
import pytest

from lab_assay import microsim as m

N = 4000


@pytest.fixture(scope="module")
def cfg():
    return m.load_config()


@pytest.fixture(scope="module")
def base(cfg):
    return m.base_params(cfg)


def test_life_table_matches_published_life_expectancy(base):
    # The Gompertz intercept is solved so that life expectancy at 65 matches the StatCan-based target.
    assert m.life_expectancy(base.a0, base.slope, base.start_age, base.end_age) == pytest.approx(
        21.0, abs=1e-6
    )


def test_same_seed_gives_identical_population(base):
    first = m.simulate(base, N, seed=2026)
    second = m.simulate(base, N, seed=2026)
    other = m.simulate(base, N, seed=2027)
    np.testing.assert_array_equal(first, second)
    assert not np.array_equal(first, other)


def test_transition_rows_sum_to_one_and_are_nonnegative(base, cfg):
    # Stress the rates well above their usual values to check that the row rescaling holds.
    stressed = replace(base, mult_h_to_mci=20.0, mult_dementia_onset=20.0, mult_d_to_ltc=20.0)
    for params in (base, stressed):
        for age in range(cfg["start_age"], cfg["end_age"]):
            P = m.transition_matrix(params, age)
            assert np.all(P >= 0.0)
            np.testing.assert_allclose(P.sum(axis=1), 1.0, atol=1e-12)
            assert P[m.X, m.X] == 1.0


def test_population_is_conserved_and_death_is_absorbing(base):
    counts = m.simulate(base, N, seed=7)
    np.testing.assert_array_equal(counts.sum(axis=1), np.full(len(counts), N))
    dead = counts[:, m.X]
    assert np.all(np.diff(dead) >= 0)


def test_calibration_recovers_known_multipliers(cfg, base):
    # Build targets from a model with known multipliers, then check that least squares finds them.
    truth = replace(base, mult_h_to_mci=1.5, mult_dementia_onset=0.8)
    counts = m.simulate(truth, 20000, 2026)
    fake_cfg = json.loads(json.dumps(cfg))
    for t in fake_cfg["targets"]:
        if t["role"] == "calibration":
            t["value"] = m.band_prevalence(counts, base.start_age, *t["band"])
    fit = m.calibrate(fake_cfg, base, 20000, 2026)
    assert fit["params"].mult_h_to_mci == pytest.approx(1.5, rel=0.05)
    assert fit["params"].mult_dementia_onset == pytest.approx(0.8, rel=0.05)


def test_validation_band_is_not_used_for_fitting(cfg):
    roles = {tuple(t["band"]): t["role"] for t in cfg["targets"]}
    assert roles[(75, 84)] == "validation"
    fit_targets = [t for t in cfg["targets"] if t["role"] == "calibration"]
    assert all(tuple(t["band"]) != (75, 84) for t in fit_targets)


def test_run_writes_report_and_plots(tmp_path, cfg):
    report = m.run(cfg, population=N, seed=2026, psa_draws=3, psa_population=500, output=tmp_path)
    assert (tmp_path / "report.json").exists()
    for name in ("prevalence-by-age.png", "tornado.png", "psa-intervals.png"):
        assert (tmp_path / name).stat().st_size > 0
    assert len(report["one_way"]) == len(cfg["sensitivity"])
    assert all(row["swing"] >= 0 for row in report["one_way"])
    assert report["probabilistic"]["draws"] == 3
    saved = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert saved["seed"] == 2026


def test_cli_runs_with_small_population(tmp_path):
    assert (
        m.main(
            ["--output", str(tmp_path), "--population", "500", "--psa-draws", "2", "--psa-population", "300"]
        )
        == 0
    )
    assert (tmp_path / "report.json").exists()


def test_cli_rejects_tiny_population(tmp_path):
    with pytest.raises(SystemExit):
        m.main(["--output", str(tmp_path), "--population", "10"])
