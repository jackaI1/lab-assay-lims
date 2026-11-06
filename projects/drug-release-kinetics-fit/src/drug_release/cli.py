"""Reproducible offline report command."""

import argparse
import hashlib
from pathlib import Path

from .analysis import analyze
from .data import load_curve
from .report import write_report


def main():
    parser = argparse.ArgumentParser(description="Fit cumulative drug release fractions")
    parser.add_argument("csv", type=Path)
    parser.add_argument(
        "--metadata",
        required=True,
        type=Path,
        help="JSON source citation, units, extraction and error half-width",
    )
    parser.add_argument("--output", type=Path, default=Path("reports/custom"))
    parser.add_argument("--bootstrap", type=int, default=500)
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()
    try:
        t, y, meta = load_curve(args.csv, args.metadata)
        report = analyze(
            t, y, bootstrap=args.bootstrap, seed=args.seed, error=meta["error_halfwidth_fraction"]
        )
        report["source"] = meta
        report["warnings"] += meta["notes"]
        report["input_sha256"] = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [args.csv, args.metadata]
        }
        write_report(report, args.output)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(2, f"release-fit: {exc}\n")
    print(f"Report: {args.output}/report.html; GitHub view: {args.output}/report.md")
    for scope in report["scopes"]:
        print(
            f"{scope['label']}: {len(scope['indices'])} observations, "
            f"{len(scope['models'])} fitted models"
        )


if __name__ == "__main__":
    main()
