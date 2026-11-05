import csv
import io

import numpy as np
import pytest
from openpyxl import Workbook

from lab_assay.analysis import analyse, fit_curve, invert, predict
from lab_assay.importers import parse_reader


def test_linear_fit_and_inverse():
    fit = fit_curve([0, 1, 2, 3], [0.1, 2.1, 4.1, 6.1], "linear")
    assert fit["r_squared"] == pytest.approx(1)
    assert invert(fit, 4.1) == pytest.approx(2)
    assert predict(fit, [2])[0] == pytest.approx(4.1)


@pytest.mark.parametrize("descending", [False, True])
def test_4pl_recovers_known_truth(descending):
    x = np.array([0, 0.2, 0.5, 1, 2, 5, 10, 30, 100])
    y = 0.1 + 2.8 / (1 + (x / 7) ** 1.3)
    if not descending:
        y = 3 - y
    fit = fit_curve(x, y, "4pl")
    target = 0.1 + 2.8 / (1 + (3.5 / 7) ** 1.3)
    if not descending:
        target = 3 - target
    assert invert(fit, target) == pytest.approx(3.5, rel=0.001)
    assert fit["r_squared"] > 0.99999
    assert invert(fit, 100) is None


@pytest.mark.parametrize(
    "x,y,model",
    [
        ([1, 1, 1], [1, 2, 3], "linear"),
        ([0, 1, 2, 3], [1, 2, 3, 4], "4pl"),
        ([0, 1, 2], [1, 1, 1], "linear"),
        ([0, 1, 2], [1, float("nan"), 2], "linear"),
    ],
)
def test_unidentifiable_curves_rejected(x, y, model):
    with pytest.raises(ValueError):
        fit_curve(x, y, model)


def make_plate(bad=False):
    mapping, signals = [], {}

    def add(well, role, value, **extra):
        mapping.append(dict(well=well, role=role, dilution=1, **extra))
        signals[well] = value

    add("A1", "blank", 0.1)
    add("A2", "blank", 0.1)
    for i, x in enumerate([0, 1, 2, 3, 4, 5]):
        add(f"B{i + 1}", "standard", 0.1 + 2 * x, concentration=x)
    for i in range(3):
        add(f"C{i + 1}", "positive", 10.1 + (i - 1) * (5 if bad else 0.01))
        add(f"D{i + 1}", "negative", 0.2 + (i - 1) * 0.01)
    add("E1", "sample", 4.1, sample_id="S1", dilution_factor=2)
    add("E2", "sample", 4.1, sample_id="S1", dilution_factor=2)
    add("F1", "sample", 40, sample_id="S2")
    return mapping, signals


def test_analysis_blank_dilution_range_cv_and_qc():
    mapping, signals = make_plate()
    result = analyse(mapping, signals, "linear")
    assert result["blank_mean"] == 0.1
    assert result["z_prime"] > 0.98
    s1 = next(g for g in result["groups"] if g["key"] == "sample:S1")
    assert s1["concentration"] == pytest.approx(4)
    assert s1["cv_percent"] == pytest.approx(0)
    assert "OUT_OF_RANGE" in result["wells"]["F1"]["flags"]
    assert not result["passed"]  # out-of-range sample blocks a clean plate
    assert result["wells"]["F1"]["concentration"] is None


def test_bad_controls_fail_and_missing_controls_are_explicit():
    mapping, signals = make_plate(bad=True)
    assert "Z_PRIME_FAIL" in analyse(mapping, signals, "linear")["flags"]
    mapping = [w for w in mapping if w["role"] not in ["positive", "negative"]]
    signals = {w["well"]: signals[w["well"]] for w in mapping}
    result = analyse(mapping, signals, "linear")
    assert result["z_prime"] is None
    assert "INSUFFICIENT_CONTROLS" in result["flags"]


@pytest.mark.parametrize("xlsx", [False, True])
@pytest.mark.parametrize("matrix", [False, True])
def test_long_and_matrix_import(xlsx, matrix):
    rows = [["well", "signal"], ["A01", 1.2], ["B2", 2.3]]
    if matrix:
        rows = [
            ["", *range(1, 13)],
            *[[letter, *[i + j / 10 for j in range(12)]] for i, letter in enumerate("ABCDEFGH")],
        ]
    stream = io.BytesIO()
    if xlsx:
        wb = Workbook()
        ws = wb.active
        for row in rows:
            ws.append(row)
        wb.save(stream)
        content = stream.getvalue()
        name = "reader.xlsx"
    else:
        output = io.StringIO()
        csv.writer(output).writerows(rows)
        content = output.getvalue().encode()
        name = "reader.csv"
    parsed = parse_reader(name, content)
    assert len(parsed) == (96 if matrix else 2)
    if not matrix:
        assert parsed == {"A1": 1.2, "B2": 2.3}


@pytest.mark.parametrize(
    "content",
    [
        b"well,signal\nA1,1\nA01,2",
        b"well,signal\nI1,3",
        b"well,signal\nA1,nan",
        b"well,signal\nA1,OVRFLW",
        b"well,signal\nA1,",
        b"well,signal\n",
    ],
)
def test_invalid_import_rejected(content):
    with pytest.raises(ValueError):
        parse_reader("x.csv", content)


def test_noisy_standard_endpoints_use_residual_qc_not_unknown_range():
    from lab_assay.demo import synthetic_plate

    mapping, content, _ = synthetic_plate()
    result = analyse(mapping, parse_reader("x.csv", content))
    for well in mapping:
        if well["role"] == "standard":
            assert result["wells"][well["well"]]["concentration"] == well["concentration"]
            assert "OUT_OF_RANGE" not in result["wells"][well["well"]]["flags"]
    assert result["passed"]


def test_out_of_range_sample_does_not_report_signal_cv_as_concentration_cv():
    mapping, signals = make_plate()
    mapping.append(dict(well="F2", role="sample", sample_id="S2"))
    signals["F2"] = 45
    result = analyse(mapping, signals, "linear")
    group = next(g for g in result["groups"] if g["key"] == "sample:S2")
    assert group["cv_percent"] is None


def test_4pl_extreme_out_of_domain_signal_is_flagged_without_overflow():
    from lab_assay.analysis import logistic

    x = [0, 0.01, 0.1, 1, 10, 100, 1000, 10000]
    fit = fit_curve(x, logistic(x, 0, 1e6, 1, 0.05), "4pl")
    assert invert(fit, fit["parameters"]["low"] + 1e-10) is None
