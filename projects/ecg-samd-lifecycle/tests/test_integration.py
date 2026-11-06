import json
import subprocess
import sys

import pytest
import wfdb
from ecg_lifecycle.data import ensure_record
from ecg_lifecycle.core import detect_peaks, match_beats, beat_samples, rates


@pytest.mark.integration
def test_public_record_qrs():
    path = ensure_record('100')
    record = wfdb.rdrecord(str(path), sampto=21600, channels=[0])
    ann = wfdb.rdann(str(path), 'atr', sampto=21600)
    peaks = detect_peaks(record.p_signal[:, 0], record.fs)
    scores = rates(match_beats(beat_samples(ann.sample, ann.symbol), peaks, 54))
    assert scores['sensitivity'] >= 0.98
    assert scores['ppv'] >= 0.98
    assert len(peaks) > 60


@pytest.mark.integration
def test_cli_full_benchmark(tmp_path):
    output = tmp_path / 'results.json'
    completed = subprocess.run([sys.executable, '-m', 'ecg_lifecycle.cli',
                                'evaluate', '--output', str(output)],
                               capture_output=True, text=True, timeout=180)
    assert completed.returncode == 0, completed.stderr
    report = json.loads(output.read_text())
    assert report['learning_only'] is True
    assert 'not a cleared device' in report['warning']
    assert set(report['records']) == {'100', '201', '203'}
    for row in report['records'].values():
        assert row['qrs']['sensitivity'] >= 0.90
        assert row['qrs']['ppv'] >= 0.90
        assert row['qrs']['tp'] > 1500
        assert len(row['windows']) == 60
        assert row['window_counts']['total'] == 60
        assert sum(row['window_counts'][k] for k in ['regular', 'irregular', 'insufficient_data']) == 60
    assert report['records']['100']['afib_proxy']['sensitivity'] is None
    assert report['records']['203']['afib_proxy']['tp'] > 0


def test_cli_rejects_unknown_record(tmp_path):
    output = tmp_path / 'bad.json'
    result = subprocess.run([sys.executable, '-m', 'ecg_lifecycle.cli', 'evaluate',
                             '--records', '../private', '--output', str(output)],
                            capture_output=True, text=True, timeout=15)
    assert result.returncode != 0
    assert not output.exists()
