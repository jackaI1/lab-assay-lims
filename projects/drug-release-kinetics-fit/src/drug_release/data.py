"""CSV curves use fraction of known total, never inferred from terminal release."""

import csv
import json
from pathlib import Path
from urllib.parse import urlparse

import numpy as np


def load_curve(csv_path, metadata_path):
    meta = json.loads(Path(metadata_path).read_text())
    required = [
        "title",
        "source_url",
        "time_unit",
        "extraction",
        "error_halfwidth_fraction",
        "error_description",
        "notes",
    ]
    if any(key not in meta for key in required):
        raise ValueError("Metadata requires " + ", ".join(required))
    if any(
        not isinstance(meta[k], str) or not meta[k].strip()
        for k in ["title", "source_url", "time_unit", "extraction", "error_description"]
    ):
        raise ValueError("Metadata text fields must be nonempty strings")
    if urlparse(meta["source_url"]).scheme not in ("http", "https"):
        raise ValueError("Source URL must use http or https")
    error = meta["error_halfwidth_fraction"]
    if not isinstance(error, (int, float)) or not np.isfinite(error) or error < 0:
        raise ValueError("Error must be a finite nonnegative fraction half-width")
    if not isinstance(meta["notes"], list) or any(not isinstance(x, str) for x in meta["notes"]):
        raise ValueError("Metadata notes must be a list of strings")
    with Path(csv_path).open(newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["time", "fraction"]:
            raise ValueError("CSV header must be time,fraction; use fractions, not percentages")
        rows = [(float(row["time"]), float(row["fraction"])) for row in reader]
    if not rows:
        raise ValueError("CSV is empty")
    values = np.asarray(rows)
    return values[:, 0], values[:, 1], meta
