import json
import subprocess
from pathlib import Path

import pytest

from drug_release.data import load_curve

ROOT = Path(__file__).resolve().parents[1]


def test_published_data_and_offline_report(tmp_path):
    t, y, meta = load_curve(ROOT / "data/ketoprofen_f15.csv", ROOT / "data/ketoprofen_f15.json")
    assert len(t) == 12
    assert t[-1] == 10 and y[-1] == pytest.approx(0.8714)
    assert meta["error_halfwidth_fraction"] == 0.00005
    proc = subprocess.run(
        [
            "release-fit",
            "data/ketoprofen_f15.csv",
            "--metadata",
            "data/ketoprofen_f15.json",
            "--output",
            str(tmp_path),
            "--bootstrap",
            "20",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    report = json.loads((tmp_path / "fit.json").read_text())
    assert report["source"]["title"] == meta["title"]
    assert "discrepancy" in " ".join(report["warnings"])
    html = (tmp_path / "report.html").read_text()
    assert "<svg" in html and "ci95" not in html
    assert "95%" in html and "held-out" in html
    assert "<script src=" not in html and "<link rel=" not in html
    assert "60%" in html and "Source" in html and "Residual" in html


def test_cli_invalid_input_fails_without_output(tmp_path):
    proc = subprocess.run(
        [
            "release-fit",
            "data/ketoprofen_f15.csv",
            "--metadata",
            "data/ketoprofen_f15.json",
            "--output",
            str(tmp_path),
            "--bootstrap",
            "1",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert not (tmp_path / "fit.json").exists()


@pytest.mark.parametrize("error", [-1, float("nan")])
def test_metadata_invalid_error(tmp_path, error):
    meta = dict(
        title="test",
        source_url="https://example.org",
        time_unit="h",
        extraction="table",
        error_description="rounding",
        error_halfwidth_fraction=error,
        notes=[],
    )
    p = tmp_path / "meta.json"
    p.write_text(json.dumps(meta))
    with pytest.raises(ValueError):
        load_curve(ROOT / "data/ketoprofen_f15.csv", p)


def test_generation_failure_preserves_previous_report(tmp_path, monkeypatch):
    from drug_release.analysis import analyze
    from drug_release.report import write_report

    t, y, meta = load_curve(ROOT / "data/ketoprofen_f15.csv", ROOT / "data/ketoprofen_f15.json")
    report = analyze(t, y, bootstrap=20)
    report["source"] = meta
    output = tmp_path / "report"
    write_report(report, output)
    before = {p.name: p.read_bytes() for p in output.iterdir()}
    original = Path.write_text

    def fail_second_plot(path, *args, **kwargs):
        if path.name == "scope-1.svg":
            raise OSError("simulated full disk")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_second_plot)
    report["fraction"][0] += 0.01
    with pytest.raises(OSError):
        write_report(report, output)
    assert {p.name: p.read_bytes() for p in output.iterdir()} == before
