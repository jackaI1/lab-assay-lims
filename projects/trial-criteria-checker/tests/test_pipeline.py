import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse
from trial_criteria.api import fetch_studies
from trial_criteria.benchmark import score
from trial_criteria.report import build_report, render_html
from trial_criteria import report as report_module


class ApiTests(unittest.TestCase):
    def test_recruiting_query_paginates_and_limits_records(self):
        urls = []
        def opener(request, timeout):
            urls.append(request.full_url)
            page = len(urls)
            study = {'protocolSection': {'identificationModule': {'nctId': 'NCT0000000'+str(page)},
                     'statusModule': {'overallStatus': 'RECRUITING'},
                     'eligibilityModule': {'eligibilityCriteria': 'Inclusion:\n* Age ≥18 years'},
                     'contactsLocationsModule': {'centralContacts': [{'name':'Public contact', 'email':'nobody@example.invalid'}]}}}
            return io.BytesIO(json.dumps({'studies':[study], 'nextPageToken':'a +/b'}).encode())
        result = fetch_studies('leukemia', limit=2, opener=opener)
        self.assertEqual(len(result['studies']), 2)
        first = parse_qs(urlparse(urls[0]).query)
        second = parse_qs(urlparse(urls[1]).query)
        self.assertEqual(first['filter.overallStatus'], ['RECRUITING'])
        self.assertEqual(first['query.cond'], ['leukemia'])
        self.assertEqual(second['pageToken'], ['a +/b'])
        self.assertEqual(result['requests'], urls)
        self.assertNotIn('contactsLocationsModule', result['studies'][0]['protocolSection'])

    def test_access_denied_is_not_retried(self):
        calls = []
        def denied(request, timeout):
            calls.append(1)
            raise HTTPError(request.full_url,403,'Forbidden',{},None)
        with self.assertRaises(HTTPError):
            fetch_studies('diabetes', opener=denied)
        self.assertEqual(len(calls),1)

    def test_invalid_limits_and_ids_fail_before_network(self):
        for kw in [dict(limit=0),dict(limit=10001),dict(ids=['bad-id'])]:
            with self.assertRaises(ValueError):
                fetch_studies('diabetes', **kw)


class BenchmarkTests(unittest.TestCase):
    def test_exact_micro_scores_penalize_wrong_threshold_and_missing_rule(self):
        def item(start, value):
            return {'nct_id':'NCT00000001','start':start,'end':start+4,'section':'inclusion',
                    'rule':{'field':'age','op':'>=','value':value,'unit':'years'}}
        scores = score([item(0,18),item(10,21)],[item(0,18),item(10,20),item(20,65)])
        self.assertEqual((scores['true_positives'],scores['false_positives'],scores['false_negatives']), (1,1,2))
        self.assertEqual(scores['precision'],0.5)
        self.assertAlmostEqual(scores['recall'],1/3)
        self.assertEqual(len(scores['missed']),2)
        self.assertEqual(score([],[])['precision'],None)

    def test_duplicate_predictions_count_as_false_positives(self):
        x = {'nct_id':'NCT00000001','start':0,'end':4,'section':'inclusion','rule':{'field':'age'}}
        self.assertEqual(score([x,x],[x])['false_positives'],1)


class ReportTests(unittest.TestCase):
    def test_saved_report_keeps_unknown_and_escapes_untrusted_text(self):
        snapshot = {'retrieved_at':'2026-01-01T00:00:00Z','requests':[], 'studies':[
            {'protocolSection': {'identificationModule': {'nctId':'NCT00000001','briefTitle':'<script>bad</script>'},
             'statusModule': {'overallStatus':'RECRUITING'},
             'eligibilityModule': {'eligibilityCriteria':'Inclusion:\n* Age ≥18 years\n* <script>bad</script>'}}}]}
        report = build_report(snapshot, {'fictional':True,'age':18})
        self.assertEqual(report['counts'], {'met':1,'not met':0,'unknown':1})
        html = render_html(report)
        self.assertNotIn('<script>',html)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn('https://clinicaltrials.gov/study/NCT00000001',html)
        with self.assertRaises(ValueError):
            build_report(snapshot, {'age':18})

    def test_markdown_report_is_readable_on_github(self):
        self.assertTrue(callable(getattr(report_module, 'render_markdown', None)))
        report = {'warning': 'Fictional demonstration', 'counts': {'unknown': 1},
                  'retrieved_at': 'saved', 'patient': {'fictional': True}, 'studies': [
                    {'nct_id': 'NCT00000001', 'title': '<script>x</script>',
                     'url': 'https://clinicaltrials.gov/study/NCT00000001', 'status': 'RECRUITING',
                     'missing_criteria': False, 'criteria': [
                       {'sentence': 'A | B', 'section': 'inclusion', 'start': 0, 'end': 5,
                        'rule': None, 'status': 'unknown', 'evaluation_reason': 'unsupported'}]}]}
        rendered = report_module.render_markdown(report)
        self.assertIn('unknown', rendered)
        self.assertIn('A &#124; B', rendered)
        self.assertNotIn('<script>', rendered)
        self.assertIn('https://clinicaltrials.gov/study/NCT00000001', rendered)

    def test_published_sample_scores_and_preserves_every_source_span(self):
        from trial_criteria.benchmark import benchmark
        from trial_criteria.parser import parse_criteria
        snapshot = json.loads(Path('data/studies.json').read_text())
        labels = json.loads(Path('data/labels.json').read_text())
        result = benchmark(snapshot, labels)
        self.assertEqual((result['true_positives'], result['false_positives'], result['false_negatives']), (10, 0, 2))
        self.assertEqual(result['source_sentence_count'], 61)
        for study in snapshot['studies']:
            text = study['protocolSection']['eligibilityModule']['eligibilityCriteria']
            for row in parse_criteria(text):
                self.assertEqual(text[row['start']:row['end']], row['sentence'])

    def test_empty_benchmark_renders_undefined_metrics(self):
        report = {'warning':'Fictional', 'retrieved_at':'saved', 'counts':{}, 'patient':{'fictional':True},
                  'studies':[], 'benchmark':dict(score([],[]),study_count=0)}
        self.assertIn('undefined', report_module.render_markdown(report))

    def test_cli_generates_readable_offline_report(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)/'report'
            p = subprocess.run([sys.executable,'-m','trial_criteria','report','--snapshot','data/studies.json',
                 '--patient','examples/fictional_patient.json','--output',str(out)],capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertIn('unknown',json.loads(out.with_suffix('.json').read_text())['counts'])
            self.assertIn('Fictional',out.with_suffix('.html').read_text())


if __name__ == '__main__':
    unittest.main()
