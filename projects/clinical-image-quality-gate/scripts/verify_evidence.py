"""Check saved counts against CSV, and optionally compare a fresh run to published evidence."""

import argparse
import csv
import json
import math
from pathlib import Path

from image_qc.data import load_manifest
from image_qc.experiment import summarize
from image_qc.images import VARIANTS


def compare(actual, expected, path="metrics", tolerance=1e-7):
    if isinstance(expected, dict):
        assert actual.keys() == expected.keys(), f"{path}: fields differ"
        for key in expected:
            compare(actual[key], expected[key], f"{path}.{key}", tolerance)
    elif isinstance(expected, list):
        assert len(actual) == len(expected), f"{path}: lengths differ"
        for i, (a, e) in enumerate(zip(actual, expected, strict=True)):
            compare(a, e, f"{path}[{i}]", tolerance)
    elif isinstance(expected, float):
        assert math.isclose(actual, expected, abs_tol=tolerance, rel_tol=tolerance), (
            f"{path}: value differs"
        )
    else:
        assert actual == expected, f"{path}: {actual!r} != {expected!r}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, default=Path("reports"))
    parser.add_argument("--manifest", type=Path, default=Path("data/manifest.json"))
    parser.add_argument("--expected", type=Path)
    args = parser.parse_args()
    metrics = json.loads((args.report / "metrics.json").read_text())
    splits = json.loads((args.report / "splits.json").read_text())
    records = load_manifest(args.manifest)
    ids = {r["isic_id"] for r in records}
    assert set(splits) == ids, "source partition is incomplete"
    assert set(splits.values()) == {"train", "validation", "test"}, "source partition invalid"
    labels = {r["isic_id"]: r["label"] for r in records}
    groups = {r["isic_id"]: r["lesion_id"] for r in records}
    with (args.report / "predictions.csv").open() as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for key in ("label", "lesion_pred", "strength", "bad"):
            r[key] = int(r[key])
        for key in ("rules_accept", "learned_accept"):
            assert r[key] in ("True", "False"), "invalid acceptance value"
            r[key] = r[key] == "True"
        r["reject_probability"] = (
            float(r["reject_probability"]) if r["reject_probability"] else None
        )
        assert splits[r["isic_id"]] == "test", "training/validation source in report"
        assert r["label"] == labels[r["isic_id"]], "source label changed"
        assert r["lesion_id"] == groups[r["isic_id"]], "source lesion changed"
        assert r["bad"] == int(r["strength"] >= 2), "damage target changed"
    expected_versions = {
        (source, kind, strength)
        for source, split in splits.items()
        if split == "test"
        for kind, strength in VARIANTS
    }
    actual_versions = {(r["isic_id"], r["kind"], r["strength"]) for r in rows}
    assert actual_versions == expected_versions, "missing or unexpected held-out version"
    assert len(rows) == len(expected_versions), "duplicate held-out versions"
    reconstructed = summarize(rows)
    for key in reconstructed:
        compare(metrics[key], reconstructed[key], key)
    for split in ("train", "validation", "test"):
        assert metrics["dataset"]["split_counts"][split] == list(splits.values()).count(split)
    if args.expected:
        compare(metrics, json.loads((args.expected / "metrics.json").read_text()))
        # Portable numeric models must also reproduce across fresh runs.
        compare(
            json.loads((args.report / "models.json").read_text()),
            json.loads((args.expected / "models.json").read_text()),
            "models",
            tolerance=1e-4,
        )
        with (args.expected / "predictions.csv").open() as f:
            published = list(csv.DictReader(f))
        decisions = [
            (
                r["isic_id"],
                r["kind"],
                r["strength"],
                r["label"],
                r["rules_accept"],
                r["learned_accept"],
                r["lesion_pred"],
            )
            for r in rows
        ]
        expected_decisions = [
            (
                r["isic_id"],
                r["kind"],
                int(r["strength"]),
                int(r["label"]),
                r["rules_accept"] == "True",
                r["learned_accept"] == "True",
                int(r["lesion_pred"]),
            )
            for r in published
        ]
        assert sorted(decisions) == sorted(expected_decisions), "per-version decisions changed"
    print(f"Verified {len(rows)} held-out versions against source manifest and saved counts.")


if __name__ == "__main__":
    main()
