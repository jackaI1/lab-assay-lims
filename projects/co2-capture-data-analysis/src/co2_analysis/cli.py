import argparse
import sys

from .batch import run_batch
from .demo import generate_demo


def main(argv=None):
    parser = argparse.ArgumentParser(description="CO2 breakthrough and cycling batch analysis")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="write seeded synthetic input CSVs and manifest")
    demo.add_argument("folder")
    demo.add_argument("--seed", type=int, default=42)
    batch = sub.add_parser("batch", help="process runs listed in a folder's manifest")
    batch.add_argument("manifest")
    batch.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            print(generate_demo(args.folder, seed=args.seed))
            return 0
        count, errors = run_batch(args.manifest, args.output)
        print(f"Wrote {count} summary rows; {len(errors)} failed runs; output: {args.output}")
        return 1 if errors else 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
