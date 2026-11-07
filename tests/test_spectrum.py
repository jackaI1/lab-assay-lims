import json

import numpy as np
import pytest

from lab_assay.spectrum import analyze, run


def test_simulated_sweep_and_saved_artifacts(tmp_path):
    report = run(tmp_path)
    measurement = report["measurement"]
    assert report["instrument"] == "simulated"
    assert measurement["peak"]["frequency_hz"] == pytest.approx(2e6, abs=5000)
    assert measurement["peak"]["power_dbm"] == pytest.approx(-10, abs=0.1)
    assert measurement["noise_floor_dbm"] == pytest.approx(-70, abs=0.1)
    assert [h["relative_dbc"] for h in measurement["harmonics"]] == pytest.approx([-30, -40], abs=0.5)
    assert measurement["spur"]["relative_dbc"] == pytest.approx(-50, abs=1)
    assert measurement["spur"]["pass"] is True
    assert json.loads((tmp_path / "report.json").read_text()) == report
    assert (tmp_path / "spectrum.png").read_bytes().startswith(b"\x89PNG")
    assert run(tmp_path, spur_limit_dbc=-55)["measurement"]["spur"]["pass"] is False


def test_rbw_changes_noise_and_source_changes_peak(tmp_path):
    result = run(tmp_path, rbw=200e3, source_frequency=2.5e6, source_power=-20)
    m = result["measurement"]
    assert m["noise_floor_dbm"] == pytest.approx(-120 + 10 * np.log10(200e3), abs=0.1)
    assert m["peak"]["frequency_hz"] == pytest.approx(2.5e6, abs=5000)
    assert m["peak"]["power_dbm"] == pytest.approx(-20, abs=0.1)


def test_invalid_and_out_of_span(tmp_path):
    with pytest.raises(ValueError):
        run(tmp_path, start=10e6, stop=1e6)
    with pytest.raises(ValueError):
        run(tmp_path, rbw=100)
    result = analyze(np.arange(1, 11), np.array([-80, -80, -80, -10, -80, -80, -80, -80, -80, -80]), 1)
    assert result["harmonics"][1]["status"] == "outside sweep"
    assert result["spur"]["pass"] is None
