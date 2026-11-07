import json
import numpy as np
import pytest
from microscopy_qc.cli import audit_report
from microscopy_qc.metrics import evaluate, summarize
from microscopy_qc.report import write_report


def test_audit_recomputes_metrics_and_rejects_tampering(tmp_path):
    image = np.zeros((12, 12), dtype=np.uint16)
    labels = np.zeros_like(image)
    labels[2:5, 2:5] = 1
    metric = evaluate(labels, labels, 0.5)
    row = {
        "image": "a",
        "method": "watershed",
        **metric,
        "metrics": {"0.5": metric},
        "qc": {"focus_score": 0, "focus_flag": False, "merge_ids": []},
    }
    run = {
        "rows": [row],
        "summary": summarize([row], [0.5]),
        "provenance": {"thresholds": [0.5]},
    }
    write_report(tmp_path, run, [("a", image, labels, {"watershed": labels})])
    assert audit_report(tmp_path)["watershed"]["count_mae"] == 0
    run["rows"][0]["metrics"]["0.5"]["f1"] = 0.1
    (tmp_path / "results.json").write_text(json.dumps(run))
    with pytest.raises(ValueError, match="Metric mismatch"):
        audit_report(tmp_path)
