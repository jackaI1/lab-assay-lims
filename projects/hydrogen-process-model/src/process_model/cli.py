"""Command-line entry point: `h2-compare`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from process_model.cost import Assumptions
from process_model.report import build_report
from process_model.workbook import write_workbook


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="h2-compare",
        description="Compare hydrogen from steam methane reforming with electrolysis.",
    )
    parser.add_argument(
        "--assumptions",
        type=Path,
        default=Path("data/assumptions.toml"),
        help="TOML file with prices, capital and efficiencies (default: data/assumptions.toml)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("h2-output"),
        help="folder for hydrogen_comparison.xlsx (default: h2-output)",
    )
    args = parser.parse_args(argv)

    assumptions = Assumptions.from_toml(args.assumptions)
    report = build_report(assumptions)
    args.output.mkdir(parents=True, exist_ok=True)
    workbook = write_workbook(args.output / "hydrogen_comparison.xlsx", report)

    print(
        f"SMR, {report.smr.energy_kwh_per_kg:.1f} kWh/kg H2, "
        f"${report.smr.total_cost_per_kg:.2f}/kg H2"
    )
    print(
        f"Electrolysis, {report.electrolysis.energy_kwh_per_kg:.1f} kWh/kg H2, "
        f"${report.electrolysis.total_cost_per_kg:.2f}/kg H2"
    )
    print(f"Largest mass or atom closure error: {report.max_closure_error:.2e}")
    print(f"Wrote {workbook}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
