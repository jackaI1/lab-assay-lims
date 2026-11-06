"""Rebuild saved reports offline from the pinned public extract."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

from cgm_metrics_check import Reading, analyze
from cgm_metrics_check.fhir import observations
from cgm_metrics_check.io import markdown_report, read_csv

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_NOTE = ('Source: public CGMacros version 1.0.0, series 001, first glucose column. '
               'These are published processed minute-resolution values. Coverage means available rows, '
               'not verified original sensor wear; upstream filling cannot be audited. Dates are publisher-shifted. '
               'UTC is an explicit placeholder because the source timezone is unknown. '
               'This example does not establish clinical data sufficiency.')


def damaged_copy(source):
    """A deliberately damaged example, never presented as original study data."""
    result = []
    for index, reading in enumerate(source):
        if 3000 <= index < 6000:
            continue
        if index % 50 == 0:
            reading = Reading(reading.timestamp, reading.value / 18.0182, 'mmol/L')
        result.append(reading)
    result.extend(result[:40])
    result.append(Reading(result[40].timestamp, result[40].value + 50, result[40].unit))
    return result


def build_reports():
    manifest = json.loads((ROOT / 'data/provenance.json').read_text())
    path = ROOT / 'data/cgmacros_001.csv'
    if hashlib.sha256(path.read_bytes()).hexdigest() != manifest['normalized_sha256']:
        raise ValueError('public extract checksum mismatch')
    source = read_csv(path)
    start = source[0].timestamp
    kwargs = dict(start=start, end=start + timedelta(days=14), cadence_minutes=1)
    public = analyze(source, **kwargs)
    public['provenance_note'] = PUBLIC_NOTE
    damaged = analyze(damaged_copy(source), **kwargs)
    damaged['provenance_note'] = ('DELIBERATELY DAMAGED COPY: removed a block of rows, changed some declared units '
                                 'with values converted, and injected duplicates and a conflicting timestamp. ' + PUBLIC_NOTE)
    hand_start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    hand = analyze([Reading(hand_start + timedelta(minutes=5*i), value, 'mg/dL')
                    for i, value in enumerate([50, 100, 150, 200])],
                   start=hand_start, end=hand_start + timedelta(minutes=20),
                   cadence_minutes=5, allow_short_window=True)
    hand['provenance_note'] = ('SYNTHETIC HAND CASE, not study data: 50, 100, 150, 200 mg/dL. '
                               'Mean = 500/4 = 125. Population variance = 12500/4 = 3125. '
                               'CV = sqrt(3125)/125*100. GMI = 3.31+0.02392*125 = 6.3. '
                               'Two of four readings in range, one below, one above.')
    return {'public': public, 'damaged': damaged, 'hand': hand}, source


def main():
    reports, source = build_reports()
    print('Policy: minimum 14 days, 70% coverage; range 70-180 mg/dL; low split 54, high split 250 mg/dL.')
    print('Formulas: GMI=3.31+0.02392*mean_mg_dl; CV=100*population_SD/mean; mmol/L to mg/dL factor=18.0182.')
    out = ROOT / 'reports'
    out.mkdir(exist_ok=True)
    for name, report in reports.items():
        (out / f'{name}.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
        (out / f'{name}.md').write_text(markdown_report(report))
        print(f'{name}: {report["readings_used"]}/{report["expected_readings"]} readings, '
              f'{report["coverage_percent"]:.2f}% coverage, '
              f'TIR={report["metrics"]["tir"]["value"]}, '
              f'mean={report["metrics"]["mean_glucose"]["value"]}, '
              f'GMI={report["metrics"]["gmi"]["value"]}, '
              f'CV={report["metrics"]["cv"]["value"]}')
    (out / 'fhir-example.ndjson').write_text(''.join(json.dumps(item) + '\n' for item in observations(source[:3])))


if __name__ == '__main__':
    main()
