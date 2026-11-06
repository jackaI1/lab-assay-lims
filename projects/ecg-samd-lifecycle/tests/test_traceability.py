from copy import deepcopy
from pathlib import Path
import subprocess
import sys

import pytest
from scripts.traceability import validate, read_junit, render_matrix

NODE = 'tests/test_core.py::test_signal_rejection'


def baseline():
    return {'requirements': [{'id': 'SWR-001', 'description': 'Reject invalid input', 'tests': [NODE]}],
            'risks': [{'id': 'R-001', 'controls': [{'id': 'RC-001', 'description': 'Reject bad input',
                       'requirements': ['SWR-001'], 'tests': [NODE]}]}]}


def test_requirement_without_test_fails():
    spec = baseline()
    spec['requirements'][0]['tests'] = []
    with pytest.raises(ValueError, match='SWR-001'):
        validate(spec, {NODE}, {NODE: 'passed'})


def test_control_without_verification_fails():
    spec = baseline()
    spec['risks'][0]['controls'][0]['tests'] = []
    with pytest.raises(ValueError, match='RC-001'):
        validate(spec, {NODE}, {NODE: 'passed'})


def test_absent_skipped_or_failed_test_fails():
    for collected, result in [(set(), {NODE: 'passed'}), ({NODE}, {}),
                               ({NODE}, {NODE: 'skipped'}), ({NODE}, {NODE: 'failed'})]:
        with pytest.raises(ValueError):
            validate(baseline(), collected, result)


def test_unknown_links_and_duplicate_ids_fail():
    for kind in ['requirement', 'duplicate', 'empty_risks', 'empty_controls']:
        spec = baseline()
        if kind == 'requirement':
            spec['risks'][0]['controls'][0]['requirements'] = ['SWR-999']
        elif kind == 'duplicate':
            spec['requirements'].append(deepcopy(spec['requirements'][0]))
        elif kind == 'empty_risks':
            spec['risks'] = []
        else:
            spec['risks'][0]['controls'] = []
        with pytest.raises(ValueError):
            validate(spec, {NODE}, {NODE: 'passed'})


def test_matrix_contains_executed_links():
    spec = baseline()
    validate(spec, {NODE}, {NODE: 'passed'})
    text = render_matrix(spec)
    assert 'SWR-001' in text and 'RC-001' in text and NODE in text


def test_junit_outcomes_and_duplicates(tmp_path):
    report = tmp_path / 'junit.xml'
    report.write_text('<testsuites><testsuite><testcase classname="tests.test_core" '
                      'name="test_signal_rejection"/><testcase classname="tests.test_core" '
                      'name="test_skip"><skipped/></testcase></testsuite></testsuites>')
    assert read_junit(report) == {NODE: 'passed', 'tests/test_core.py::test_skip': 'skipped'}
    report.write_text('<testsuites><testsuite><testcase classname="tests.test_core" '
                      'name="test_signal_rejection"/><testcase classname="tests.test_core" '
                      'name="test_signal_rejection"/></testsuite></testsuites>')
    with pytest.raises(ValueError):
        read_junit(report)


def test_gate_cli_fails_for_uncovered_requirement(tmp_path):
    import json
    spec = baseline()
    spec['requirements'][0]['tests'] = []
    source = tmp_path / 'lifecycle.json'
    source.write_text(json.dumps(spec))
    junit = tmp_path / 'junit.xml'
    junit.write_text('<testsuites><testsuite><testcase classname="tests.test_core" '
                     'name="test_signal_rejection"/></testsuite></testsuites>')
    out = tmp_path / 'matrix.md'
    result = subprocess.run([sys.executable, '-m', 'scripts.traceability', '--spec', str(source),
                             '--junit', str(junit), '--output', str(out)],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode != 0
    assert 'SWR-001' in result.stderr
    assert not out.exists()


def test_omitted_unlinked_execution_fails():
    collected = {NODE, 'tests/test_core.py::test_regular_and_irregular_windows'}
    with pytest.raises(ValueError, match='execution'):
        validate(baseline(), collected, {NODE: 'passed'})
