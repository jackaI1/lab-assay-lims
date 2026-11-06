"""Strict CSV import and a report readable in any text viewer."""
import csv
from datetime import datetime
from pathlib import Path

from .model import Reading, utc


def parse_timestamp(text: str) -> datetime:
    try:
        value = datetime.fromisoformat(text.strip().replace('Z', '+00:00'))
        utc(value)
        return value
    except (ValueError, AttributeError) as exc:
        raise ValueError('timestamp must be ISO 8601 with a timezone offset') from exc


def read_csv(path: str | Path) -> list[Reading]:
    """Read timestamp,glucose,unit. Never infer units or silently skip bad rows."""
    readings = []
    with open(path, newline='', encoding='utf-8-sig') as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ['timestamp', 'glucose', 'unit']:
            raise ValueError('CSV header must be timestamp,glucose,unit in that order')
        for row in reader:
            try:
                if None in row or any(v is None or not v.strip() for v in row.values()):
                    raise ValueError('missing or extra CSV field')
                readings.append(Reading(parse_timestamp(row['timestamp']), float(row['glucose']), row['unit'].strip()))
            except (ValueError, TypeError) as exc:
                raise ValueError(f'CSV line {reader.line_num}: {exc}') from exc
    return readings


LABELS = {
    'tir': 'Time in range (70 to 180 mg/dL)',
    'tbr': 'Time below range (below 70 mg/dL)',
    'tar': 'Time above range (above 180 mg/dL)',
    'tbr_level1': 'Low band (54 to below 70 mg/dL)',
    'tbr_level2': 'Very low band (below 54 mg/dL)',
    'tar_level1': 'High band (above 180 to 250 mg/dL)',
    'tar_level2': 'Very high band (above 250 mg/dL)',
    'mean_glucose': 'Mean glucose', 'gmi': 'Glucose management indicator (GMI)',
    'cv': 'Coefficient of variation (CV)',
}


def markdown_report(report: dict) -> str:
    window, quality = report['window'], report['quality']
    lines = ['# Glucose data check', '', report['notice'], '',
             f"Window: {window['start']} to {window['end_exclusive']} (end excluded).",
             f"Expected interval: {window['cadence_minutes']:g} minutes. No missing values filled.",
             f"Coverage: {report['readings_used']} / {report['expected_readings']} readings ({report['coverage_percent']:.2f}%).", '']
    if window['exploratory']:
        lines += ['Exploratory short window: these results do not meet the recommended fourteen-day window.', '']
    if report.get('provenance_note'):
        lines += [report['provenance_note'], '']
    lines += ['| Metric | Value | Supporting readings | Coverage |',
              '| --- | --- | --- | --- |']
    for name, metric in report['metrics'].items():
        value = f"REFUSED: {metric['reason']}" if metric['value'] is None else f"{metric['value']:.2f} {metric['unit']}"
        lines.append(f"| {LABELS[name]} | {value} | {metric['readings_used']} / {metric['expected_readings']} | {metric['coverage_percent']:.2f}% |")
    lines += ['', 'Time percentages describe accepted readings only. Missing readings are not assumed in range.',
              'GMI is a glucose-based estimate, not a laboratory A1C result. CV uses population standard deviation.', '',
              '## Quality checks', '',
              f"- Mixed declared units: {'yes' if quality['mixed_units'] else 'no'}.",
              f"- Extra duplicate rows: {quality['duplicate_rows']}.",
              f"- Conflicting timestamps excluded: {quality['conflicting_timestamps']}.",
              f"- Rows outside window: {quality['out_of_window_rows']}.",
              f"- Missing runs: {len(quality['gaps'])}. Longest: {quality['longest_gap_minutes']:g} minutes.", '',
              '## Coverage by UTC date', '', '| Date | Supporting readings | Coverage |', '| --- | --- | --- |']
    for day in report['daily_coverage']:
        lines.append(f"| {day['date']} | {day['readings_used']} / {day['expected_readings']} | {day['coverage_percent']:.2f}% |")
    lines += ['', '## Missing runs', '', '| Start | End (excluded) | Missing readings | Minutes |', '| --- | --- | --- | --- |']
    for gap in quality['gaps']:
        lines.append(f"| {gap['start']} | {gap['end_exclusive']} | {gap['missing_readings']} | {gap['minutes']:g} |")
    return '\n'.join(lines) + '\n'
