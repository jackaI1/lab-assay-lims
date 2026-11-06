import pytest

from co2_analysis import analyze_cycles
from co2_analysis.io import signed_charge

CC_HEADER = ["cycle", "time_s", "current_a", "voltage_v", "phase"]
CV_HEADER = CC_HEADER[:-1]
OPTIONS = {"voltage_min_v": 0, "voltage_max_v": 1}


def test_analytic_charge_retention_efficiency_drift_and_truncation(csv_file, cc_rows):
    path = csv_file(CC_HEADER, cc_rows() + cc_rows(2, 0.8) + cc_rows(3, 0.8, True))
    rows, _ = analyze_cycles(path, kind="cycling", mass_g=0.5, **OPTIONS)
    assert rows[0]["charge_mah"] == pytest.approx(1000)
    assert rows[0]["discharge_mah"] == pytest.approx(900)
    assert rows[0]["discharge_mah_g"] == pytest.approx(1800)
    assert rows[0]["coulombic_efficiency_pct"] == pytest.approx(90)
    assert rows[1]["retention_pct"] == pytest.approx(80)
    assert rows[1]["flags"] == "capacity_drift"
    assert not rows[2]["complete"]
    assert rows[2]["coulombic_efficiency_pct"] is None
    assert rows[2]["retention_pct"] is None


def test_first_incomplete_cycle_is_not_retention_baseline(csv_file, cc_rows):
    path = csv_file(CC_HEADER, cc_rows(1, truncated=True) + cc_rows(2, 0.8))
    rows, _ = analyze_cycles(path, kind="cycling", **OPTIONS)
    assert rows[0]["retention_pct"] is None
    assert rows[1]["retention_pct"] == 100


def test_gap_does_not_produce_quality_ratios(csv_file, cc_rows):
    path = csv_file(CC_HEADER, cc_rows() + cc_rows(3))
    rows, _ = analyze_cycles(path, kind="cycling", **OPTIONS)
    assert rows[1]["retention_pct"] is None
    assert "cycle_number_gap" in rows[1]["flags"]


def test_sampling_gap(csv_file, cc_rows):
    rows, _ = analyze_cycles(
        csv_file(CC_HEADER, cc_rows()), kind="cycling", max_gap_s=1000, **OPTIONS
    )
    assert "sampling_gap" in rows[0]["flags"]
    assert rows[0]["coulombic_efficiency_pct"] is None


def test_rest_intervals_are_not_capacity(csv_file, cc_rows):
    data = cc_rows()
    data.insert(3, [1, 3600, 0.5, 1, "rest"])
    rows, _ = analyze_cycles(csv_file(CC_HEADER, data), kind="cycling", **OPTIONS)
    assert rows[0]["complete"]
    assert rows[0]["charge_mah"] == pytest.approx(1000)


def test_internal_voltage_excursion_flags_cycle(csv_file, cc_rows):
    data = cc_rows()
    data[1][3] = 1.5
    rows, _ = analyze_cycles(csv_file(CC_HEADER, data), kind="cycling", **OPTIONS)
    assert not rows[0]["complete"]
    assert "voltage_out_of_range" in rows[0]["flags"]
    assert rows[0]["coulombic_efficiency_pct"] is None


@pytest.mark.parametrize("remove", [slice(0, 3), slice(3, 6), slice(0, 2)])
def test_missing_branch_or_one_sample_is_incomplete(csv_file, cc_rows, remove):
    data = cc_rows()
    del data[remove]
    rows, _ = analyze_cycles(csv_file(CC_HEADER, data), kind="cycling", **OPTIONS)
    assert not rows[0]["complete"]
    assert rows[0]["coulombic_efficiency_pct"] is None


@pytest.mark.parametrize(
    "mode",
    ["wrong_sign", "time_reversal", "duplicate", "fractional_cycle", "unknown_phase", "nonfinite"],
)
def test_invalid_cycling_data(csv_file, cc_rows, mode):
    data = cc_rows()
    if mode == "wrong_sign":
        data[4][2] = 0.9
    elif mode == "time_reversal":
        data[4][1] = 1
    elif mode == "duplicate":
        data[1][1] = 0
    elif mode == "fractional_cycle":
        data[0][0] = 0.5
    elif mode == "unknown_phase":
        data[1][4] = "charging"
    else:
        data[1][2] = "inf"
    with pytest.raises(ValueError):
        analyze_cycles(csv_file(CC_HEADER, data), kind="cycling", **OPTIONS)


def test_exact_zero_crossing_integration():
    charge, discharge = signed_charge([0, 2], [-1, 1])
    assert charge == pytest.approx(0.5 / 3.6)
    assert discharge == pytest.approx(0.5 / 3.6)
    charge, discharge = signed_charge([0, 3], [-2, 1])
    assert charge == pytest.approx(0.5 / 3.6)
    assert discharge == pytest.approx(2 / 3.6)


@pytest.mark.parametrize("reverse", [False, True])
def test_cv_closed_triangle_analytic_integrals(csv_file, reverse):
    voltage = [0, 0.5, 1, 0.5, 0]
    if reverse:
        voltage = [1 - v for v in voltage]
    path = csv_file(CV_HEADER, zip([1] * 5, range(5), [1, 1, 0, -1, -1], voltage, strict=True))
    rows, _ = analyze_cycles(path, kind="cv", **OPTIONS)
    assert rows[0]["complete"]
    assert rows[0]["charge_mah"] == pytest.approx(1.5 / 3.6)
    assert rows[0]["discharge_mah"] == pytest.approx(1.5 / 3.6)
    assert rows[0]["coulombic_efficiency_pct"] == pytest.approx(100)


@pytest.mark.parametrize(
    "voltages",
    [[0, 0.5, 1, 0.7, 0.6], [0, 0.5, 0.8, 0.5, 0], [0, 1, 0.5, 1, 0], [0.2, 0.5, 1, 0.5, 0.2]],
)
def test_cv_truncated_or_extra_reversal(csv_file, voltages):
    path = csv_file(CV_HEADER, zip([1] * 5, range(5), [1, 1, 0, -1, -1], voltages, strict=True))
    rows, _ = analyze_cycles(path, kind="cv", **OPTIONS)
    assert not rows[0]["complete"]
    assert rows[0]["retention_pct"] is None


def test_cv_one_sided_current_is_not_valid_efficiency(csv_file):
    path = csv_file(CV_HEADER, zip([1] * 5, range(5), [1] * 5, [0, 0.5, 1, 0.5, 0], strict=True))
    rows, _ = analyze_cycles(path, kind="cv", **OPTIONS)
    assert rows[0]["coulombic_efficiency_pct"] is None
    assert "missing_capacity" in rows[0]["flags"]


@pytest.mark.parametrize(
    "options",
    [{"voltage_max_v": 0}, {"mass_g": -1}, {"voltage_tolerance_v": 0}, {"drift_fraction": -1}],
)
def test_invalid_configuration(csv_file, cc_rows, options):
    with pytest.raises(ValueError):
        analyze_cycles(csv_file(CC_HEADER, cc_rows()), kind="cycling", **{**OPTIONS, **options})
