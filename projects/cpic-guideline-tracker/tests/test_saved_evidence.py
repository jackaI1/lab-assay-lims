"""Keep the checked-in reports reproducible without reaching any service."""
import json
import unittest
from pathlib import Path

from cpic_tracker.compare import compare_snapshots, render_report
from cpic_tracker.lookup import lookup
from cpic_tracker.snapshot import load_snapshot

ROOT = Path(__file__).resolve().parents[1]


class SavedEvidenceTests(unittest.TestCase):
    def test_release_report_reproduces_byte_for_byte(self):
        old = load_snapshot(ROOT / 'snapshots/release-v1.57.0.json')
        new = load_snapshot(ROOT / 'snapshots/release-v1.61.0.json')
        self.assertEqual(render_report(old, new).rstrip('\n') + '\n',
                         (ROOT / 'reports/release-changes.md').read_text())

    def test_lookup_example_reproduces_and_text_is_verbatim(self):
        s = load_snapshot(ROOT / 'snapshots/release-v1.61.0.json')
        result = lookup(s, 'voriconazole', {'CYP2C19': 'Poor Metabolizer'}, 'adults')
        self.assertEqual(result, json.loads((ROOT / 'reports/lookup-example.json').read_text()))
        self.assertEqual(result['matches'][0]['recommendation'],
                         next(r['drugrecommendation'] for r in s['tables']['recommendation'] if r['id'] == 8610618))

    def test_live_capture_is_complete_and_each_page_has_provenance(self):
        s = load_snapshot(ROOT / 'snapshots/api-2026-11-05.json')
        self.assertEqual(s['source']['kind'], 'api')
        for table, rows in s['tables'].items():
            pages = [p for p in s['source']['requests'] if '/' + table + '?' in p['url']]
            self.assertEqual(sum(p['rows'] for p in pages), len(rows))
            self.assertTrue(all(len(p['sha256']) == 64 for p in pages))
        # These were separate captures; agreement is checked, not assumed.
        release = load_snapshot(ROOT / 'snapshots/release-v1.61.0.json')
        self.assertEqual(compare_snapshots(release, s), [])
