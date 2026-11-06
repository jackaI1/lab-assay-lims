import csv
import hashlib
import json
import subprocess
import sys

import matplotlib.pyplot as plt
import pytest

from co2_analysis.batch import run_batch
from co2_analysis.cli import main
from co2_analysis.demo import generate_demo


def test_real_cli_batch_and_documented_noise_accuracy(tmp_path):
    manifest = generate_demo(tmp_path / "runs")
    output = tmp_path / "results"
    result = subprocess.run(
        [sys.executable, "-m", "co2_analysis.cli", "batch", str(manifest), "--output", str(output)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    with (output / "summary.csv").open() as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 7
    truth = json.loads((manifest.parent / "truth.json").read_text())
    assert float(rows[0]["captured_mmol"]) == pytest.approx(
        truth["breakthrough"]["captured_mmol_noiseless"], rel=0.005
    )
    assert abs(float(rows[0]["t50_s"]) - 600) < 5
    assert abs(float(rows[0]["mass_balance_residual_mmol"])) < 1e-12
    assert float(rows[1]["charge_mah"]) == pytest.approx(100 * 0.1 / 3.6, rel=0.005)
    for index in [2, 5]:
        assert "capacity_drift" in rows[index]["flags"]
        assert float(rows[index]["retention_pct"]) == pytest.approx(80, abs=0.5)
    for index in [3, 6]:
        assert "incomplete_cycle" in rows[index]["flags"]
        assert rows[index]["retention_pct"] == ""
    for name in ["adsorption", "cycling", "cv"]:
        assert (output / f"{name}.png").read_bytes().startswith(b"\x89PNG")
    provenance = json.loads((output / "provenance.json").read_text())
    assert (
        provenance["runs"][0]["sha256"]
        == hashlib.sha256((manifest.parent / "adsorption.csv").read_bytes()).hexdigest()
    )
    assert json.loads((output / "errors.json").read_text()) == []


def test_seed_reproducibility(tmp_path):
    a = generate_demo(tmp_path / "a")
    b = generate_demo(tmp_path / "b")
    for filename in ["adsorption.csv", "cycling.csv", "cv.csv", "manifest.json", "truth.json"]:
        assert (a.parent / filename).read_bytes() == (b.parent / filename).read_bytes()


def test_one_bad_run_does_not_hide_others(tmp_path):
    manifest = generate_demo(tmp_path / "runs")
    (manifest.parent / "cycling.csv").write_text("invalid csv")
    output = tmp_path / "results"
    assert main(["batch", str(manifest), "--output", str(output)]) == 1
    errors = json.loads((output / "errors.json").read_text())
    assert len(errors) == 1 and errors[0]["run_id"] == "cycling"
    with (output / "summary.csv").open() as handle:
        assert len(list(csv.DictReader(handle))) == 4
    assert not plt.get_fignums()


def test_outputs_and_inputs_are_not_overwritten(tmp_path):
    manifest = generate_demo(tmp_path / "runs")
    output = tmp_path / "results"
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_text("original")
    assert main(["batch", str(manifest), "--output", str(output)]) == 2
    assert main(["demo", str(manifest.parent)]) == 2
    assert marker.read_text() == "original"


@pytest.mark.parametrize(
    "bad",
    [
        [],
        {},
        {"runs": []},
        {"runs": [1]},
        {"runs": [{"id": "../unsafe"}]},
        {"runs": [{"id": "x", "kind": "unknown", "file": "x", "options": {}}]},
    ],
)
def test_manifest_validation(tmp_path, bad):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(bad))
    with pytest.raises(ValueError):
        run_batch(path, tmp_path / "results")
    assert not (tmp_path / "results").exists()


def test_duplicate_ids_rejected(tmp_path):
    manifest = generate_demo(tmp_path / "runs")
    data = json.loads(manifest.read_text())
    data["runs"][1]["id"] = "adsorption"
    manifest.write_text(json.dumps(data))
    assert main(["batch", str(manifest), "--output", str(tmp_path / "results")]) == 2


def test_figures_closed_on_save_failure(tmp_path, monkeypatch):
    from matplotlib.figure import Figure

    def fail(*args, **kwargs):
        raise OSError("simulated full disk")

    monkeypatch.setattr(Figure, "savefig", fail)
    manifest = generate_demo(tmp_path / "runs")
    count, errors = run_batch(manifest, tmp_path / "results")
    assert count == 0 and len(errors) == 3
    assert not plt.get_fignums()
