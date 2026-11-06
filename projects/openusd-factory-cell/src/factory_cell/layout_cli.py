"""Command-line entry point for the factory-cell exporter."""

import argparse
import json
from pathlib import Path

from pxr import Tf

from . import write_stage


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Turn a JSON equipment layout into an OpenUSD scene."
    )
    parser.add_argument(
        "layout", type=Path, help="JSON file with equipment sizes and centre positions in metres"
    )
    parser.add_argument("output", type=Path, help="destination .usd, .usda or .usdc file")
    args = parser.parse_args(argv)
    try:
        layout = json.loads(args.layout.read_text(encoding="utf-8"))
        write_stage(layout, args.output)
    except (ValueError, OSError, Tf.ErrorException) as error:
        parser.exit(2, f"factory-cell: {error}\n")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    main()
