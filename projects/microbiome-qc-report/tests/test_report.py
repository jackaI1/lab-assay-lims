import csv
from pathlib import Path
import tempfile
import unittest
from scripts.report import build, table


class ReportTests(unittest.TestCase):
    def test_tables_escape_pipes(self):
        self.assertIn(r'a\|b',table([{'name':'a|b'}]))

    def test_no_eligible_samples_produces_honest_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            def write(name,rows):
                with (p/name).open('w') as f:
                    w=csv.DictWriter(f,fieldnames=rows[0].keys(),delimiter='\t')
                    w.writeheader();w.writerows(rows)
            write('read_tracking.tsv',[{'sample':'shallow','type':'sample','raw_pairs':10,'nonchimeric':3}])
            write('sample_decisions.tsv',[{'sample':'shallow','eligible':'FALSE','status':'TOO SHALLOW'}])
            write('parameters.tsv',[{'parameter':'depth','value':'100'}, {'parameter':'control_screen','value':'unavailable: no negative controls'}])
            result=build(p)
            self.assertEqual(result['too_shallow_samples'],1)
            self.assertEqual(result['eligible_samples'],0)
            self.assertIn('Not available',(p/'report.md').read_text())
            self.assertIn('no negative controls',(p/'report.html').read_text())
