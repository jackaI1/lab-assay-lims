import copy
import csv
import json
import subprocess
import sys
from pathlib import Path


def test_checked_in_evidence_matches_rows():
    p = subprocess.run(
        [sys.executable, "scripts/verify_evidence.py", "--report", "reports"],
        capture_output=True,
        text=True,
    )
    assert p.returncode == 0, p.stderr


def test_evidence_check_rejects_changed_accuracy(tmp_path):
    m = json.loads(Path("reports/metrics.json").read_text())
    changed = copy.deepcopy(m)
    changed["learned"]["accepted"]["correct"] += 1
    (tmp_path / "metrics.json").write_text(json.dumps(changed))
    (tmp_path / "predictions.csv").write_bytes(Path("reports/predictions.csv").read_bytes())
    (tmp_path / "splits.json").write_bytes(Path("reports/splits.json").read_bytes())
    p = subprocess.run(
        [sys.executable, "scripts/verify_evidence.py", "--report", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert p.returncode != 0


def test_saved_sources_and_predictions_are_disjoint():
    records = json.loads(Path("data/manifest.json").read_text())
    split = json.loads(Path("reports/splits.json").read_text())
    lesions = {r["lesion_id"] for r in records}
    assert len(lesions) == len(records)
    with Path("reports/predictions.csv").open() as f:
        rows = list(csv.DictReader(f))
    assert all(split[r["isic_id"]] == "test" for r in rows)
    assert len({(r["isic_id"], r["kind"], r["strength"]) for r in rows}) == len(rows)


def test_parameter_tolerance_allows_small_platform_rounding_only():
    import runpy

    import pytest

    compare = runpy.run_path("scripts/verify_evidence.py")["compare"]
    compare({"coefficient": [1.00001]}, {"coefficient": [1.0]}, tolerance=1e-4)
    with pytest.raises(AssertionError):
        compare({"coefficient": [1.01]}, {"coefficient": [1.0]}, tolerance=1e-4)
    with pytest.raises(AssertionError):
        compare({"correct": 11}, {"correct": 10}, tolerance=1e-4)
    with pytest.raises(AssertionError):
        compare({"accuracy": 0.6846}, {"accuracy": 0.6845})
