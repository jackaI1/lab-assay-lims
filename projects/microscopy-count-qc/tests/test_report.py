import json
import numpy as np
from microscopy_qc.report import write_report
from microscopy_qc.metrics import evaluate


def test_report_is_offline_and_exposes_errors(tmp_path):
    truth = np.zeros((16, 16), dtype=int)
    truth[3:8, 3:8] = 1
    pred = np.zeros_like(truth)
    row = {
        "image": "a",
        "method": "watershed",
        **evaluate(truth, pred, 0.5),
        "metrics": {"0.5": evaluate(truth, pred, 0.5)},
        "qc": {"focus_score": 0.0, "focus_flag": True, "merge_ids": []},
    }
    run = {"rows": [row], "summary": {}, "provenance": {"dataset": "BBBC039"}}
    write_report(
        tmp_path, run, [("a", truth.astype(float), truth, {"watershed": pred})]
    )
    html = (tmp_path / "index.html").read_text()
    assert "data:image/png;base64," in html
    assert "Missed" in html
    assert "a" in html
    assert "<script src=" not in html
    saved = json.loads((tmp_path / "results.json").read_text())
    assert saved["rows"][0]["fn"] == 1
    assert (tmp_path / "per_image.csv").exists()


def test_github_gallery_has_image_links_and_counts(tmp_path):
    labels = np.zeros((8, 8), dtype=int)
    labels[2:4, 2:4] = 1
    row = {
        "image": "field",
        "method": "watershed",
        **evaluate(labels, labels, 0.5),
        "metrics": {"0.5": evaluate(labels, labels, 0.5)},
        "qc": {"focus_score": 0.2, "focus_flag": False, "merge_ids": []},
    }
    write_report(
        tmp_path,
        {"rows": [row], "summary": {}, "provenance": {}},
        [("field", labels.astype(float), labels, {"watershed": labels})],
    )
    gallery = (tmp_path / "gallery.md").read_text()
    assert "overlays/field-watershed.png" in gallery
    assert "overlays/field-reference.png" in gallery
    assert "reference 1" in gallery


def test_local_data_report_does_not_claim_official_bbbc039_holdout(tmp_path):
    labels = np.zeros((8, 8), dtype=int)
    row = {
        "image": "local",
        "method": "watershed",
        **evaluate(labels, labels, 0.5),
        "metrics": {"0.5": evaluate(labels, labels, 0.5)},
        "qc": {"focus_score": 0, "focus_flag": True, "merge_ids": []},
    }
    write_report(
        tmp_path,
        {
            "rows": [row],
            "summary": {},
            "provenance": {"dataset": "Local supplied images (not verified BBBC039)"},
        },
        [("local", labels.astype(float), labels, {"watershed": labels})],
    )
    text = (tmp_path / "index.html").read_text()
    assert "Local supplied images (not verified BBBC039)" in text
    assert "using the publisher's test list" not in text
