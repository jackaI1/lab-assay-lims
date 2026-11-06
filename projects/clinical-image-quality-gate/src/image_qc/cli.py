"""Commands for public-data reproduction and genuinely abstaining local inference."""

import argparse
import json
import sys
from pathlib import Path

from .data import download, freeze_manifest, load_manifest
from .experiment import run
from .images import load_image
from .models import selective_predict


def main():
    parser = argparse.ArgumentParser(description="Research photo QC. Not a diagnostic tool.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("download", "reproduce"):
        p = sub.add_parser(name)
        p.add_argument("--manifest", default="data/manifest.json")
        p.add_argument("--images", default="data/images")
        if name == "reproduce":
            p.add_argument("--output", default="reports")
    p = sub.add_parser("check")
    p.add_argument("image")
    p.add_argument("--model", default="reports/models.json")
    p.add_argument("--method", choices=("rules", "learned"), default="learned")
    p = sub.add_parser(
        "freeze", help="explicitly refresh the source snapshot, changing the experiment"
    )
    p.add_argument("--manifest", default="data/manifest.json")
    p.add_argument("--per-class", type=int, default=180)
    args = parser.parse_args()
    try:
        if args.command == "check":
            result = selective_predict(
                load_image(args.image), json.loads(Path(args.model).read_text()), args.method
            )
        elif args.command == "download":
            records = load_manifest(args.manifest)
            download(records, args.images)
            result = {"verified_sources": len(records)}
        elif args.command == "freeze":
            freeze_manifest(args.manifest, args.per_class)
            result = {"manifest": args.manifest}
        else:
            m = run(args.manifest, args.images, args.output)
            result = {
                "report": str(Path(args.output) / "REPORT.md"),
                "test_versions": m["overall"]["n"],
                "learned_bad_rejected": m["learned"]["bad_rejected"],
                "learned_accepted_accuracy": m["learned"]["accepted"],
            }
        print(json.dumps(result, indent=2, allow_nan=False))
    except (OSError, ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
