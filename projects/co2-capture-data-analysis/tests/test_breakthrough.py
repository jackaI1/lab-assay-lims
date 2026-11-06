import numpy as np
import pytest

from co2_analysis import analyze_breakthrough
from co2_analysis.breakthrough import R_L_KPA_MOL_K

HEADER = ["time_s", "outlet_ppm", "flow_ml_min"]
OPTIONS = {"inlet_ppm": 10000, "mass_g": 2, "median_window": 1, "sustain_points": 1}


def test_linear_curve_analytic_capacity_thresholds_and_mtz(csv_file):
    time = np.linspace(0, 100, 101)
    path = csv_file(HEADER, zip(time, time * 100, np.full(len(time), 120), strict=True))
    result, _ = analyze_breakthrough(path, bed_length_cm=20, **OPTIONS)
    expected = (120 / 1000 / 60) * 0.01 * 101.325 / (R_L_KPA_MOL_K * 298.15) * 50 * 1000
    assert result["captured_mmol"] == pytest.approx(expected)
    assert result["capacity_mmol_g"] == pytest.approx(expected / 2)
    assert [result[k] for k in ["t05_s", "t50_s", "t95_s"]] == pytest.approx([5, 50, 95])
    assert result["mtz_width_s"] == pytest.approx(90)
    assert result["mtz_length_proxy_cm"] == pytest.approx(20 * 90 / 95)
    assert result["mass_balance_residual_mmol"] == pytest.approx(0, abs=1e-14)


def test_irregular_grid_varying_flow_and_outlet_balance(csv_file):
    time = np.array([0, 1, 3, 7, 10])
    inlet_flow = 60 + 2 * time
    outlet_flow = 30 + time
    path = csv_file(
        HEADER + ["outlet_flow_ml_min"],
        zip(time, [5000] * len(time), inlet_flow, outlet_flow, strict=True),
    )
    result, _ = analyze_breakthrough(path, separate_outlet_flow=True, **OPTIONS)
    factor = 101.325 / (R_L_KPA_MOL_K * 298.15) / 60 / 1e6
    assert result["inlet_mmol"] == pytest.approx(700 * 10000 * factor)
    assert result["outlet_mmol"] == pytest.approx(350 * 5000 * factor)
    assert result["captured_mmol"] == pytest.approx((7000000 - 1750000) * factor)
    assert abs(result["mass_balance_residual_mmol"]) < 1e-14


@pytest.mark.parametrize("outlet,expected", [(0, 1), (10000, 0), (20000, -1)])
def test_full_zero_and_negative_capture(csv_file, outlet, expected):
    path = csv_file(HEADER, [(0, outlet, 60), (10, outlet, 60), (30, outlet, 60)])
    result, _ = analyze_breakthrough(path, **OPTIONS)
    incoming = 0.01 * 101.325 / (R_L_KPA_MOL_K * 298.15) * 0.03 * 1000
    assert result["captured_mmol"] == pytest.approx(expected * incoming)


def test_noise_not_clipped_and_missing_saturation_not_invented(csv_file):
    path = csv_file(HEADER, [(0, -100, 60), (10, 100, 60), (20, 200, 60)])
    result, _ = analyze_breakthrough(path, **OPTIONS)
    assert "negative_outlet_noise" in result["flags"]
    assert "saturation_unobserved" in result["flags"]
    assert result["t95_s"] is None
    assert result["mtz_width_s"] is None
    assert result["outlet_mmol"] > 0


def test_persistent_crossing_ignores_single_spike(csv_file):
    path = csv_file(
        HEADER, zip(range(8), [0, 9000, 0, 0, 6000, 7000, 8000, 9000], [60] * 8, strict=True)
    )
    options = {**OPTIONS, "sustain_points": 3}
    result, _ = analyze_breakthrough(path, **options)
    assert result["t50_s"] == pytest.approx(3 + 5 / 6)


def test_median_filter_is_only_for_thresholds(csv_file):
    path = csv_file(
        HEADER, zip(range(9), [0, 9000, 0, 0, 6000, 7000, 8000, 9000, 10000], [60] * 9, strict=True)
    )
    raw, _ = analyze_breakthrough(path, **OPTIONS)
    filtered, _ = analyze_breakthrough(path, **{**OPTIONS, "median_window": 3})
    assert raw["captured_mmol"] == filtered["captured_mmol"]
    assert raw["t50_s"] < filtered["t50_s"]


def test_sampling_gap_and_left_censoring(csv_file):
    path = csv_file(HEADER, [(100, 6000, 60), (101, 9000, 60), (200, 10000, 60)])
    result, _ = analyze_breakthrough(path, max_gap_s=10, **OPTIONS)
    assert result["t05_s"] is None
    assert "starts_above_t05" in result["flags"]
    assert "sampling_gap" in result["flags"]


@pytest.mark.parametrize(
    "key,value",
    [
        ("mass_g", 0),
        ("temperature_k", -1),
        ("pressure_kpa", float("nan")),
        ("inlet_ppm", 1e7),
        ("median_window", 2),
        ("median_window", 999),
        ("sustain_points", 0),
        ("bed_length_cm", -1),
    ],
)
def test_invalid_options(csv_file, key, value):
    path = csv_file(HEADER, [(0, 0, 60), (1, 5000, 60), (2, 10000, 60)])
    with pytest.raises(ValueError):
        analyze_breakthrough(path, **{**OPTIONS, key: value})


@pytest.mark.parametrize(
    "rows",
    [
        [(0, 0, 60), (0, 5000, 60), (2, 10000, 60)],
        [(0, 0, 60), (2, 5000, 60), (1, 10000, 60)],
        [(0, 0, 60), (1, 5000, -1), (2, 10000, 60)],
        [(0, 0, 60), (1, "nan", 60), (2, 10000, 60)],
        [(0, 0, 60), (1, "", 60), (2, 10000, 60)],
        [(0, 0, 60), (1, 5000, 60)],
    ],
)
def test_invalid_measurements(csv_file, rows):
    with pytest.raises(ValueError):
        analyze_breakthrough(csv_file(HEADER, rows), **OPTIONS)


def test_missing_header(csv_file):
    with pytest.raises(ValueError, match="missing columns"):
        analyze_breakthrough(csv_file(["time", "ppm", "flow"], [(0, 0, 60)] * 3), **OPTIONS)
