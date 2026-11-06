"""Reproducible download, benchmark, and saved-result audit commands."""

import argparse
import importlib.metadata
import json
import platform
from pathlib import Path
import time

import numpy as np
from scipy.ndimage import gaussian_filter

from .data import download_dataset, load_pair, load_splits, sha256, verify_download
from .metrics import evaluate, summarize
from .qc import calibrate, focus_score, inspect_image
from .report import write_report
from .segment import cellpose_segment, load_cellpose, watershed_segment

THRESHOLDS = [0.5, 0.75, 0.9]


def run_benchmark(args):
    if len(args.methods) != len(set(args.methods)):
        raise ValueError("Duplicate methods would double-count images")
    if args.limit is not None and args.limit < 1:
        raise ValueError("--limit must be positive")
    if args.threads < 1:
        raise ValueError("--threads must be positive")
    root = Path(args.data)
    source_manifest = (
        verify_download(root) if (root / "download_provenance.json").exists() else None
    )
    splits = load_splits(root)
    config = calibrate(load_pair(root, stem) for stem in splits["training"])
    selected = splits["test"][: args.limit]
    model = load_cellpose(args.threads) if "cellpose" in args.methods else None
    provenance = {
        "dataset": source_manifest["dataset"]
        if source_manifest is not None
        else "Local supplied images (not verified BBBC039)",
        "sources": source_manifest,
        "splits": splits,
        "evaluated_test_images": selected,
        "partial_run": len(selected) != len(splits["test"]),
        "calibration": config,
        "thresholds": THRESHOLDS,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "dependencies": {
            name: importlib.metadata.version(name)
            for name in ["numpy", "scipy", "scikit-image", "pillow", "tifffile"]
        },
        "input_sha256": {
            stem: {
                "image": sha256(root / "images" / f"{stem}.tif"),
                "mask": sha256(root / "masks" / f"{stem}.png"),
            }
            for members in splits.values()
            for stem in members
        },
        "model": None,
        "pretraining_independence": "Unknown; related public data may overlap with pretraining",
    }
    if model is not None:
        provenance["dependencies"].update(
            {name: importlib.metadata.version(name) for name in ["cellpose", "torch"]}
        )
        provenance["model"] = {
            "name": "nuclei",
            "weights_sha256": sha256(model.pretrained_model),
            "device": "cpu",
            "threads": args.threads,
            "seed": 0,
            "channels": [0, 0],
            "flow_threshold": 0.4,
            "cellprob_threshold": 0.0,
            "augment": False,
        }
    rows, images = [], []
    start = time.monotonic()
    for index, stem in enumerate(selected, 1):
        image, truth = load_pair(root, stem)
        predictions = {}
        for method in args.methods:
            prediction = (
                watershed_segment(image, config["diameter"], config["min_area"])
                if method == "watershed"
                else cellpose_segment(
                    model, image, config["diameter"], config["min_area"]
                )
            )
            predictions[method] = prediction
            scores = {str(t): evaluate(truth, prediction, t) for t in THRESHOLDS}
            rows.append(
                {
                    "image": stem,
                    "method": method,
                    **scores["0.5"],
                    "metrics": scores,
                    "qc": inspect_image(image, prediction, config),
                }
            )
        images.append((stem, image, truth, predictions))
        print(f"{index}/{len(selected)} {stem}", flush=True)
    sample = images[0][1]
    provenance["blur_sensitivity_check"] = {
        "image": selected[0],
        "original_score": focus_score(sample),
        "gaussian_sigma4_score": focus_score(gaussian_filter(sample.astype(float), 4)),
        "note": "Synthetic blur only, not a real focus-defect label; excluded from evaluation",
    }
    provenance["inference_seconds"] = round(time.monotonic() - start, 3)
    result = {
        "provenance": provenance,
        "summary": summarize(rows, THRESHOLDS),
        "rows": rows,
    }
    write_report(args.output, result, images)
    print(json.dumps(result["summary"], indent=2))


def audit_report(output):
    output = Path(output)
    run = json.loads((output / "results.json").read_text())
    for row in run["rows"]:
        with np.load(output / "labels" / f'{row["image"]}.npz') as labels:
            for threshold, expected in row["metrics"].items():
                actual = evaluate(
                    labels["truth"], labels[row["method"]], float(threshold)
                )
                if actual != expected:
                    raise ValueError(
                        f'Metric mismatch: {row["image"]} {row["method"]} {threshold}'
                    )
        if any(row[key] != row["metrics"]["0.5"][key] for key in row["metrics"]["0.5"]):
            raise ValueError("Top-level image metrics disagree with IoU 0.5 metrics")
    if summarize(run["rows"], run["provenance"]["thresholds"]) != run["summary"]:
        raise ValueError("Summary does not agree with per-image metrics")
    print(f'Audited {len(run["rows"])} image/method rows against saved labels')
    return run["summary"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    download = commands.add_parser("download")
    download.add_argument("--data", default="data/bbbc039")
    download.add_argument("--sources", default="sources.json")
    run = commands.add_parser("run")
    run.add_argument("--data", default="data/bbbc039")
    run.add_argument("--output", default="reports/bbbc039")
    run.add_argument(
        "--methods",
        nargs="+",
        choices=["watershed", "cellpose"],
        default=["watershed", "cellpose"],
    )
    run.add_argument("--threads", type=int, default=2)
    run.add_argument("--limit", type=int)
    audit = commands.add_parser("audit")
    audit.add_argument("--output", default="reports/bbbc039")
    render = commands.add_parser("render")
    render.add_argument("--data", default="data/bbbc039")
    render.add_argument("--output", default="reports/bbbc039")
    args = parser.parse_args()
    if args.command == "download":
        download_dataset(args.data, args.sources)
    elif args.command == "run":
        run_benchmark(args)
    elif args.command == "render":
        audit_report(args.output)
        output = Path(args.output)
        result = json.loads((output / "results.json").read_text())

        def saved_images():
            for stem in result["provenance"]["evaluated_test_images"]:
                image_path = Path(args.data) / "images" / f"{stem}.tif"
                if (
                    sha256(image_path)
                    != result["provenance"]["input_sha256"][stem]["image"]
                ):
                    raise ValueError(f"Input image changed: {stem}")
                image, _ = load_pair(args.data, stem)
                with np.load(output / "labels" / f"{stem}.npz") as labels:
                    truth = labels["truth"]
                    predictions = {
                        key: labels[key] for key in labels.files if key != "truth"
                    }
                yield stem, image, truth, predictions

        write_report(output, result, saved_images())
    else:
        print(json.dumps(audit_report(args.output), indent=2))
