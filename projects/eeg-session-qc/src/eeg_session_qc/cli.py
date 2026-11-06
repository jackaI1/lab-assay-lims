"""Small CLI for a complete public demo or one local public EDF."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import mne
import numpy as np
import scipy

from .data import download_demo, read_edf
from .quality import analyze
from .report import save_report
from .validation import validate


def write_json(path, content):
    path.write_text(json.dumps(content, indent=2, allow_nan=False) + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="EEG session quality screening, not a diagnostic tool"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    report = sub.add_parser("report", help="Read a public EDF and save HTML plus JSON")
    report.add_argument("edf", type=Path)
    report.add_argument("--output", type=Path, default=Path("reports/session"))
    report.add_argument("--line-hz", type=int, choices=(50, 60), default=60)
    demo = sub.add_parser("demo", help="Download pinned public recordings, report and validate")
    demo.add_argument("--data", type=Path, default=Path("data"))
    demo.add_argument("--output", type=Path, default=Path("reports"))
    demo.add_argument("--seed", type=int, default=42)
    summary = sub.add_parser("summary", help="Print measured numbers from a demo output folder")
    summary.add_argument("--output", type=Path, default=Path("reports"))
    args = parser.parse_args(argv)
    try:
        if args.command == "report":
            result = analyze(read_edf(args.edf), args.edf.stem, args.line_hz)
            save_report(result, args.output)
            print(
                f"{result['session']}: {result['status']}, {result['score']}/100; {args.output}.html"
            )
        elif args.command == "demo":
            paths = download_demo(args.data)
            recordings = []
            sources = []
            args.output.mkdir(parents=True, exist_ok=True)
            for path in paths:
                raw = read_edf(path)
                recordings.append((path.stem, raw))
                result = analyze(raw, path.stem)
                save_report(result, args.output / path.stem)
                sources.append(
                    {
                        "file": path.name,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "channels": len(raw.ch_names),
                        "sfreq": raw.info["sfreq"],
                        "duration_seconds": raw.n_times / raw.info["sfreq"],
                    }
                )
                print(f"{path.stem}: {result['status']}, {result['score']}/100")
            validation = validate(recordings, args.seed)
            write_json(args.output / "validation.json", validation)
            write_json(
                args.output / "provenance.json",
                {
                    "sources": sources,
                    "substitute": None,
                    "versions": {
                        "mne": mne.__version__,
                        "numpy": np.__version__,
                        "scipy": scipy.__version__,
                    },
                    "command": f"uv run eeg-qc demo --seed {args.seed}",
                },
            )
            print_summary(args.output)
        else:
            print_summary(args.output)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f"error: {exc}\n")


def print_summary(directory):
    data = json.loads((directory / "validation.json").read_text())
    provenance = json.loads((directory / "provenance.json").read_text())
    print(f"Public recordings: {len(provenance['sources'])}")
    for source in provenance["sources"]:
        result = json.loads((directory / (Path(source["file"]).stem + ".json")).read_text())
        print(
            f"{result['session']}: {len(result['channels'])} channels, "
            f"{result['sfreq']:g} Hz, {result['duration_seconds']:g} s, "
            f"{result['score']:g}/100, {result['status']}"
        )
    print(
        f"Reference segments: {data['reference_segments']}/{data['candidate_segments']}; "
        f"rejected: {data['rejected_segments']}; seed: {data['seed']}"
    )
    for ref in data["reference_details"]:
        print(
            f"{ref['reference']}: {len(ref['channels'])} retained sensors, "
            f"{len(ref['excluded_channels'])} excluded sensors"
        )
    print(f"Injection trials: {len(data['trials'])}")
    for kind, row in data["summary"].items():
        print(
            f"{kind}: {row['detected']}/{row['trials']} ({row['detection_rate']:.1%}); "
            f"new: {row['new_detections']}/{row['unflagged_control_trials']}; "
            f"untreated segments flagged: {row['untreated_segments_flagged']}/{data['reference_segments']}"
        )
        for level, values in row["by_level"].items():
            print(f"  level {level}: {values['detected']}/{values['trials']}")


if __name__ == "__main__":
    sys.exit(main())
