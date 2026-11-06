import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cpic_tracker.cli import main
from cpic_tracker.snapshot import build_snapshot, save_snapshot
from tests.test_sources import tables


class CliTests(unittest.TestCase):
    def test_api_command_uses_source_client_and_preserves_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'api.json'
            with patch('cpic_tracker.cli.ApiClient') as client:
                client.return_value.fetch_all.return_value = (tables(), [{'url': 'https://api.cpicpgx.org/v1/pair'}])
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(main(['snapshot', '--output', str(p)]), 0)
            result = json.loads(p.read_text())
            self.assertEqual(result['source']['kind'], 'api')
            self.assertEqual(len(result['source']['requests']), 1)
            self.assertIn('captured_at', result)

    def test_cli_lookup_stats_and_compare_offline(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'snapshot.json'
            save_snapshot(build_snapshot(tables(), {'kind': 'fixture'}), p)
            def run(*args):
                return subprocess.run([sys.executable, '-m', 'cpic_tracker', *args],
                                      text=True, capture_output=True)
            r = run('lookup', str(p), '--drug', 'voriconazole', '--phenotype', 'CYP2C19=Poor Metabolizer', '--population', 'adults')
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(r.stdout)['status'], 'guideline')
            r = run('lookup', str(p), '--drug', 'invented', '--phenotype', 'CYP2C19=Poor Metabolizer')
            self.assertEqual(json.loads(r.stdout)['status'], 'no guideline')
            r = run('stats', str(p))
            self.assertEqual(json.loads(r.stdout)['recommendation_rows'], 5)
            report = Path(directory) / 'report.md'
            r = run('compare', str(p), str(p), '--output', str(report))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('Total changed records: 0', report.read_text())
            r = run('compare', str(p), str(p), '--output', str(report))
            self.assertNotEqual(r.returncode, 0)
            self.assertNotIn('Traceback', r.stderr)

    def test_invalid_duplicate_phenotype_and_broken_input_fail_cleanly(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'bad.json'; p.write_text('{}')
            for args in [['stats', str(p)], ['lookup', str(p), '--drug', 'a', '--phenotype', 'bad'],
                         ['lookup', str(p), '--drug', 'a', '--phenotype', 'CYP2C19=A', '--phenotype', 'cyp2c19=B']]:
                r = subprocess.run([sys.executable, '-m', 'cpic_tracker', *args], text=True, capture_output=True)
                self.assertEqual(r.returncode, 2)
                self.assertNotIn('Traceback', r.stderr)

    def test_malformed_lookup_fields_fail_cleanly(self):
        from cpic_tracker.snapshot import digest
        for bad_field in ['null-guideline', 'numeric-level']:
            s = build_snapshot(tables(), {'kind': 'fixture'})
            if bad_field == 'null-guideline':
                for r in s['tables']['recommendation']:
                    if r['drugid'] == 'RxNorm:121243': r['guidelineid'] = None
                for p in s['tables']['pair']:
                    if p['drugid'] == 'RxNorm:121243': p['guidelineid'] = None
            else:
                for p in s['tables']['pair']:
                    if p['drugid'] == 'RxNorm:121243': p['cpiclevel'] = 1
            s['tables_sha256'] = digest(s['tables'])
            with tempfile.TemporaryDirectory() as directory:
                p = Path(directory) / 'malformed.json'; p.write_text(json.dumps(s))
                r = subprocess.run([sys.executable, '-m', 'cpic_tracker', 'lookup', str(p),
                                    '--drug', 'voriconazole', '--phenotype', 'CYP2C19=Poor Metabolizer',
                                    '--population', 'adults'], text=True, capture_output=True)
                self.assertEqual(r.returncode, 2)
                self.assertNotIn('Traceback', r.stderr)

    def test_failed_download_leaves_no_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'absent.json'
            with patch('cpic_tracker.cli.ApiClient') as client:
                client.return_value.fetch_all.side_effect = ValueError('truncated')
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(main(['snapshot', '--output', str(p)]), 2)
            self.assertFalse(p.exists())
