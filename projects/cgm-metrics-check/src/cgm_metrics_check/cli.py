"""Command-line report generation. Exit 0: reported, 2: refused, 1: bad input."""
import argparse
import json
from pathlib import Path
import sys

from .fhir import observations
from .io import markdown_report, parse_timestamp, read_csv
from .metrics import analyze


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Check one public CGM series. Not a medical device; no treatment advice.')
    parser.add_argument('csv', type=Path)
    parser.add_argument('--start', required=True, help='ISO timestamp with timezone; included')
    parser.add_argument('--end', required=True, help='ISO timestamp with timezone; excluded')
    parser.add_argument('--cadence-minutes', type=float, required=True)
    parser.add_argument('--allow-short-window', action='store_true', help='exploratory only; never bypasses 70%% coverage')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        readings = read_csv(args.csv)
        report = analyze(readings, start=parse_timestamp(args.start), end=parse_timestamp(args.end),
                         cadence_minutes=args.cadence_minutes, allow_short_window=args.allow_short_window)
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / 'report.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        (args.out / 'report.md').write_text(markdown_report(report), encoding='utf-8')
        with (args.out / 'observations.ndjson').open('w', encoding='utf-8') as handle:
            for item in observations(readings):
                handle.write(json.dumps(item, allow_nan=False) + '\n')
    except (ValueError, OSError, OverflowError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 1
    print(f"{report['readings_used']} / {report['expected_readings']} readings; coverage {report['coverage_percent']:.2f}%; report: {args.out / 'report.md'}")
    return 2 if any(m['status'] == 'refused' for m in report['metrics'].values()) else 0
