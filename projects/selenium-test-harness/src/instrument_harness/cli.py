"""A useful default sweep, with deterministic fault injection for troubleshooting."""

import argparse
from pathlib import Path

from .browser import chrome
from .instrument import BenchSupply
from .models import Limits, Settings
from .page import SupplyPage
from .runner import SweepRunner, SweepStep
from .simulator import simulator


def main() -> int:
    parser = argparse.ArgumentParser(description="Check a simulated supply at 1, 3, and 5 V")
    parser.add_argument("--output", type=Path, default=Path("results/sweep.json"))
    parser.add_argument("--headed", action="store_true", help="show the owned Chrome window")
    parser.add_argument(
        "--fault",
        default="normal",
        choices=[
            "normal",
            "timeout",
            "bad-reading",
            "non-finite",
            "wrong-unit",
            "drift",
            "error",
            "stale",
        ],
    )
    args = parser.parse_args()
    steps = [SweepStep(Settings(v), Limits(v - 0.01, v + 0.01)) for v in (1.0, 3.0, 5.0)]
    with simulator() as url, chrome(headless=not args.headed) as driver:
        page = SupplyPage(driver, url)
        instrument = BenchSupply(page)
        instrument.connect()
        page.select_fault(args.fault)
        report = SweepRunner(instrument).run(steps, args.output)
    print(
        f"{'PASS' if report['passed'] else 'FAIL'}: {len(report['steps'])} steps -> {args.output}"
    )
    return 0 if report["passed"] else 1
