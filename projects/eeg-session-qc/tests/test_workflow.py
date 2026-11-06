import json
import subprocess
import sys

import pytest
from test_quality import raw_signal

from eeg_session_qc.quality import analyze
from eeg_session_qc.report import render_report
from eeg_session_qc.validation import inject, validate


def test_report_is_standalone_and_escapes_labels():
    result = analyze(raw_signal(), "<script>alert(1)</script>")
    html = render_report(result)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    assert "Not a diagnostic tool" in html
    assert "100" in html and "usable" in html.lower()
    assert 'src="http' not in html


def test_injections_do_not_change_original_and_validation_has_denominators():
    raw = raw_signal(seconds=16)
    before = raw.get_data().copy()
    changed, target = inject(raw, "flat", 1, seed=3)
    assert target and (changed.get_data() != before).any()
    assert (raw.get_data() == before).all()
    result = validate([("synthetic-test-only", raw)], seed=3)
    assert result["reference_segments"] > 0
    for kind, outcome in result["summary"].items():
        assert kind in ("flat", "noisy", "line", "blink", "muscle")
        assert outcome["trials"] > 0
        assert 0 <= outcome["detected"] <= outcome["trials"]
        assert 0 <= outcome["detection_rate"] <= 1
    assert result["controls"] and result["trials"]
    assert validate([("synthetic-test-only", raw)], seed=3) == result


def test_no_reference_is_explicit_error():
    raw = raw_signal(seconds=16)
    raw._data[:] = 0
    with pytest.raises(ValueError, match="reference"):
        validate([("dead", raw)])


def test_cli_help_and_missing_edf(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "eeg_session_qc", "--help"], capture_output=True, text=True
    )
    assert result.returncode == 0
    result = subprocess.run(
        [sys.executable, "-m", "eeg_session_qc", "report", str(tmp_path / "missing.edf")],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "error:" in result.stderr and "Traceback" not in result.stderr


def test_saved_report_matches_json(tmp_path):
    from eeg_session_qc.report import save_report

    result = analyze(raw_signal(), "demo")
    save_report(result, tmp_path / "demo")
    assert json.loads((tmp_path / "demo.json").read_text()) == result
    assert (tmp_path / "demo.html").read_text() == render_report(result)


def test_reference_excludes_bad_sensors_instead_of_discarding_quiet_neighbors():
    raw = raw_signal(seconds=16)
    raw._data[4] *= 50
    result = validate([("partly-noisy", raw)])
    assert result["reference_segments"] == 2
    assert all("C3" in ref["excluded_channels"] for ref in result["reference_details"])
    assert all("C3" not in trial["targets"] for trial in result["trials"])


def test_report_summarizes_many_sensors_to_keep_page_readable():
    raw = raw_signal()
    raw._data[:] = 0
    html = render_report(analyze(raw, "all flat"))
    assert "All 8 sensors" in html
