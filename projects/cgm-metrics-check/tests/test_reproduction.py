"""Offline regression evidence from the real public extract and saved reports."""
import importlib.util
import json
from pathlib import Path

import pytest
from fhir.resources.observation import Observation

from cgm_metrics_check.fhir import observations
from cgm_metrics_check.io import markdown_report

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('reproduce', ROOT / 'scripts/reproduce.py')
reproduce = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reproduce)


def test_public_data_and_saved_reports_reproduce_exactly():
    reports, source = reproduce.build_reports()
    assert len(source) == 14730
    public = reports['public']
    assert public['expected_readings'] == 20160
    assert public['coverage_percent'] == pytest.approx(73.06547619047619)
    assert public['quality']['gaps'][0]['missing_readings'] == 5430
    for name, report in reports.items():
        assert report == json.loads((ROOT / f'reports/{name}.json').read_text())
        assert markdown_report(report) == (ROOT / f'reports/{name}.md').read_text()
    expected_fhir = ''.join(json.dumps(item) + '\n' for item in observations(source[:3]))
    assert expected_fhir == (ROOT / 'reports/fhir-example.ndjson').read_text()


def test_damaged_public_copy_is_flagged_and_all_metrics_refused():
    reports, _ = reproduce.build_reports()
    damaged = reports['damaged']
    assert damaged['quality']['mixed_units'] is True
    assert damaged['quality']['duplicate_rows'] == 41
    assert damaged['quality']['conflicting_timestamps'] == 1
    assert damaged['readings_used'] == 11729
    assert damaged['coverage_percent'] < 70
    assert all(m['status'] == 'refused' and m['value'] is None for m in damaged['metrics'].values())


def test_every_public_quantity_exports_as_valid_fhir_r4():
    _, source = reproduce.build_reports()
    for reading, resource in zip(source, observations(source)):
        model = Observation.parse_obj(resource)
        assert float(model.valueQuantity.value) == reading.value
        assert model.valueQuantity.code == reading.unit
