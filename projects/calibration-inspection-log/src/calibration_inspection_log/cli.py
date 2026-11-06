"""Command-line entry for the local inspection record workflow."""

import argparse
import json
import sqlite3
import sys
from datetime import date
from pathlib import Path

from .demo import create_demo
from .report import export_report
from .store import KINDS, UNITS, Log


def parser():
    root = argparse.ArgumentParser(description="Calibration register and receiving inspection log")
    root.add_argument(
        "--db", type=Path, default=Path("quality.db"), help="SQLite file (before command)"
    )
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="Create an empty database, or validate an existing one")
    instrument = commands.add_parser("instrument", help="Register a measuring instrument")
    instrument.add_argument("--id", required=True)
    instrument.add_argument("--kind", choices=KINDS, required=True)
    instrument.add_argument("--serial", required=True)
    instrument.add_argument("--unit", choices=UNITS, required=True)
    calibration = commands.add_parser("calibrate", help="Append a calibration result")
    calibration.add_argument("--instrument", required=True)
    calibration.add_argument("--date", required=True)
    calibration.add_argument("--due", required=True)
    calibration.add_argument("--result", choices=("PASS", "OUT_OF_TOLERANCE"), required=True)
    calibration.add_argument("--certificate", required=True, help="Certificate path or URL")
    receipt = commands.add_parser("receive", help="Record a received part lot and its documents")
    for flag in (
        "id",
        "part",
        "drawing",
        "revision",
        "lot",
        "supplier",
        "po",
        "certificate",
        "date",
    ):
        receipt.add_argument(f"--{flag}", required=True)
    measurement = commands.add_parser(
        "measure", help="Record one sample feature against drawing limits"
    )
    for flag in ("receipt", "sample", "feature", "instrument", "measured", "lower", "upper"):
        measurement.add_argument(f"--{flag}", required=True)
    measurement.add_argument("--unit", choices=UNITS, required=True)
    measurement.add_argument(
        "--defect-type", help="Optional category for an out-of-limit dimension"
    )
    for command in ("status", "report"):
        report = commands.add_parser(
            command,
            help="List calibration status"
            if command == "status"
            else "Export a new Excel snapshot",
        )
        report.add_argument(
            "--as-of", default=date.today().isoformat(), help="YYYY-MM-DD (default today)"
        )
        report.add_argument("--warning-days", type=int, default=30)
        if command == "report":
            report.add_argument("--output", type=Path, required=True)
    demo = commands.add_parser(
        "demo", help="Create a synthetic database, documents and Excel report"
    )
    demo.add_argument(
        "--output", type=Path, default=Path("outputs/demo"), help="New directory to create"
    )
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "demo":
            output = create_demo(args.output)
            print(f"Synthetic demo saved to {output}. Open quality-report.xlsx (as of 2026-11-05).")
            return 0
        if args.command != "init" and not args.db.is_file():
            raise ValueError(f"Database does not exist: {args.db}. Run init first.")
        with Log(args.db) as log:
            if args.command == "init":
                print(f"Database ready: {args.db}")
            elif args.command == "instrument":
                log.add_instrument(args.id, args.kind, args.serial, args.unit)
                print(f"Registered {args.id}")
            elif args.command == "calibrate":
                identifier = log.calibrate(
                    args.instrument, args.date, args.due, args.result, args.certificate
                )
                print(f"Calibration {identifier} recorded for {args.instrument}")
            elif args.command == "receive":
                log.receive(
                    args.id,
                    args.part,
                    args.drawing,
                    args.revision,
                    args.lot,
                    args.supplier,
                    args.po,
                    args.certificate,
                    args.date,
                )
                print(
                    f"Receipt {args.id} recorded. Add each required drawing feature with measure."
                )
            elif args.command == "measure":
                row = log.measure(
                    args.receipt,
                    args.sample,
                    args.feature,
                    args.instrument,
                    args.measured,
                    args.lower,
                    args.upper,
                    args.unit,
                    args.defect_type,
                )
                print(json.dumps(row, indent=2))
            elif args.command == "status":
                rows = log.instruments(args.as_of, args.warning_days)
                for row in rows:
                    print(
                        f"{row['id']:<20} {row['status']:<20} "
                        f"due {row['due_date'] or 'not recorded'}"
                    )
                if not rows:
                    print("No instruments registered.")
            elif args.command == "report":
                output = export_report(log, args.output, args.as_of, args.warning_days)
                print(f"Report saved: {output}")
        return 0
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
