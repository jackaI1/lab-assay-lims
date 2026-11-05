import csv
import hashlib
import json
from pathlib import Path

import pytest

from lab_assay.analysis import fit_curve, invert

DATA = Path(__file__).resolve().parents[1] / "data" / "public"


def test_attributed_public_calibration_is_reproducible():
    content = (DATA / "elisatools-standards.csv").read_bytes()
    provenance = json.loads((DATA / "provenance.json").read_text())
    assert hashlib.sha256(content).hexdigest() == provenance["subset_sha256"]
    rows = list(csv.DictReader(content.decode().splitlines()))
    assert len(rows) == 24
    x = [float(r["concentration"]) for r in rows]
    y = [float(r["signal"]) for r in rows]
    fit = fit_curve(x, y, "4pl")
    assert fit["r_squared"] > 0.98
    # The public source has noisy triplicates; do not invent ground truth for unknowns.
    for concentration in [93.8, 187.5, 375, 750, 1500]:
        signal = sum(float(r["signal"]) for r in rows if float(r["concentration"]) == concentration) / 3
        assert invert(fit, signal) == pytest.approx(concentration, rel=0.2)
