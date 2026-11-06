"""Small JSON command-line interface for generation and preflight checks."""

import argparse
import json
import sys

from .builder import CELL, PART, build_cell
from .validation import open_stage, validate_stage


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] not in {"generate", "validate", "inspect", "-h", "--help"}:
        from .layout_cli import main as layout_main

        return layout_main(argv)
    parser = argparse.ArgumentParser(
        description="Build, check and inspect a manufacturing cell.",
        epilog="JSON layout export: factory-cell layout.json output.usda",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    generate = sub.add_parser(
        "generate", help="Create a new cell bundle, never overwrite a directory"
    )
    generate.add_argument("--output", required=True)
    generate.add_argument("--fixture", choices=["clamp", "nest"], default="clamp")
    generate.add_argument("--seconds", type=float, default=8)
    generate.add_argument("--fps", type=int, default=24)
    for name in ("validate", "inspect"):
        sub.add_parser(name).add_argument("stage")
    args = parser.parse_args(argv)
    try:
        if args.command == "generate":
            path = build_cell(args.output, fixture=args.fixture, seconds=args.seconds, fps=args.fps)
            report = validate_stage(path)
            payload = {"stage": str(path), **report.to_dict()}
        else:
            report = validate_stage(args.stage)
            payload = report.to_dict()
            if args.command == "inspect" and report.valid:
                stage = open_stage(args.stage)
                payload = {
                    **report.summary,
                    "sublayers": list(stage.GetRootLayer().subLayerPaths),
                    "prims": [str(p.GetPath()) for p in stage.Traverse()],
                    "fixture_options": stage.GetPrimAtPath(CELL + "/Fixtures")
                    .GetVariantSet("fixture")
                    .GetVariantNames(),
                    "part_samples": stage.GetPrimAtPath(PART)
                    .GetAttribute("xformOp:translate")
                    .GetNumTimeSamples(),
                }
        print(json.dumps(payload, indent=2, allow_nan=False))
        return 0 if report.valid else 1
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, indent=2))
        return 1
