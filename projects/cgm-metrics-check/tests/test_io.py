import csv
import json
import subprocess
import sys
from datetime import timedelta

import pytest
from fhir.resources.observation import Observation

from cgm_metrics_check import Reading
from cgm_metrics_check.io import read_csv, markdown_report
from cgm_metrics_check.fhir import observations
from test_metrics import START, short, rows


def test_csv_reads_mixed_declared_units(tmp_path):
    path = tmp_path / 'mixed.csv'
    path.write_text('timestamp,glucose,unit\n2025-01-01T00:00:00Z,100,mg/dL\n2025-01-01T00:05:00+00:00,6,mmol/L\n')
    data = read_csv(path)
    assert [(r.value, r.unit) for r in data] == [(100, 'mg/dL'), (6, 'mmol/L')]
    assert short(data, 2)['quality']['mixed_units']


@pytest.mark.parametrize('body', [
    'timestamp,glucose\n2025-01-01T00:00:00Z,100\n',
    'timestamp,glucose,unit\n2025-01-01T00:00:00Z,,mg/dL\n',
    'timestamp,glucose,unit\n2025-01-01T00:00:00Z,NaN,mg/dL\n',
    'timestamp,glucose,unit\n2025-01-01,100,mg/dL\n',
    'timestamp,glucose,unit\n2025-01-01T00:00:00Z,100,mg/L\n',
    'timestamp,glucose,unit\n2025-01-01T00:00:00Z,100,\n',
    'timestamp,glucose,unit\n2025-01-01T00:00:00Z,100,mg/dL,extra\n',
])
def test_csv_rejects_ambiguous_or_malformed_rows(tmp_path, body):
    path = tmp_path / 'bad.csv'
    path.write_text(body)
    with pytest.raises(ValueError):
        read_csv(path)


def test_fhir_r4_validation_preserves_values_offsets_and_units():
    source = [Reading(START, 100, 'mg/dL'), Reading(START + timedelta(minutes=5), 5.6, 'mmol/L')]
    exported = observations(source)
    assert len(exported) == 2
    for raw, original in zip(exported, source):
        validated = Observation.parse_obj(raw)
        assert float(validated.valueQuantity.value) == original.value
        assert raw['valueQuantity']['unit'] == original.unit
        assert raw['valueQuantity']['code'] == original.unit
        assert raw['valueQuantity']['system'] == 'http://unitsofmeasure.org'
        assert raw['effectiveDateTime'] == original.timestamp.isoformat()
        assert raw['status'] == 'final'
        assert 'subject' not in raw
    assert exported[0]['id'] != exported[1]['id']


def test_export_does_not_silently_drop_conflicts():
    assert len(observations([Reading(START, 100, 'mg/dL'), Reading(START, 200, 'mg/dL')])) == 2


def test_markdown_exposes_refusal_and_supporting_data():
    text = markdown_report(short(rows([100] * 6), 10))
    assert 'REFUSED' in text
    assert '6 / 10' in text
    assert '60.00%' in text
    assert 'Not a medical device' in text


def test_cli_generates_readable_report_json_and_fhir(tmp_path):
    path = tmp_path / 'input.csv'
    path.write_text('timestamp,glucose,unit\n2025-01-01T00:00:00Z,100,mg/dL\n')
    out = tmp_path / 'output'
    cmd = [sys.executable, '-m', 'cgm_metrics_check', str(path), '--start', START.isoformat(),
           '--end', (START + timedelta(minutes=5)).isoformat(), '--cadence-minutes', '5',
           '--allow-short-window', '--out', str(out)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads((out / 'report.json').read_text())['metrics']['mean_glucose']['value'] == 100
    assert '100.00' in (out / 'report.md').read_text()
    assert len((out / 'observations.ndjson').read_text().splitlines()) == 1
    assert Observation.parse_raw((out / 'observations.ndjson').read_text()).valueQuantity.unit == 'mg/dL'
    # A real refusal still writes the audit report and returns a distinct exit code.
    cmd.remove('--allow-short-window')
    refused = subprocess.run(cmd, capture_output=True, text=True)
    assert refused.returncode == 2
    assert all(m['value'] is None for m in json.loads((out / 'report.json').read_text())['metrics'].values())


def test_cli_invalid_input_is_actionable_without_traceback(tmp_path):
    source = tmp_path / 'bad.csv'
    source.write_text('bad,input\n')
    result = subprocess.run([sys.executable, '-m', 'cgm_metrics_check', str(source), '--start', START.isoformat(),
                             '--end', START.isoformat(), '--cadence-minutes', '5', '--out', str(tmp_path / 'out')],
                            capture_output=True, text=True)
    assert result.returncode == 1
    assert 'error:' in result.stderr
    assert 'Traceback' not in result.stderr


@pytest.mark.parametrize('offset', ['+00:00:30', '+14:01', '-15:00'])
def test_rejects_offsets_that_cannot_be_exported_as_fhir(offset):
    from cgm_metrics_check.io import parse_timestamp
    with pytest.raises(ValueError, match='offset'):
        Reading(parse_timestamp('2025-01-01T00:00:00' + offset), 100, 'mg/dL')


def test_preserves_supported_non_utc_offset_in_fhir():
    from cgm_metrics_check.io import parse_timestamp
    reading = Reading(parse_timestamp('2025-01-01T00:00:00-05:00'), 100, 'mg/dL')
    resource = observations([reading])[0]
    assert resource['effectiveDateTime'] == '2025-01-01T00:00:00-05:00'
    Observation.parse_obj(resource)
