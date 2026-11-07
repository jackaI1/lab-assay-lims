import io
import json
import unittest
from surveillance.core import decisions, normalize, read_csv, redcap_export, trend

class SurveillanceTests(unittest.TestCase):
    def setUp(self):
        self.rows = normalize(read_csv('data/complaints.csv'))
    def test_seeded_signal(self):
        points = trend(self.rows, read_csv('data/exposure.csv'))
        self.assertFalse(points[0]['signal'])
        self.assertTrue(points[-1]['signal'])
    def test_fda_malfunction(self):
        result = decisions(self.rows[0])
        self.assertEqual(result['FDA']['days'], 30)
        self.assertIn('803.50(a)(2)', result['FDA']['clause'])
    def test_eu_priority(self):
        row = dict(self.rows[0], event='death', eu_serious=True, public_health_threat=True)
        self.assertEqual(decisions(row)['EU']['days'], 2)
        row['public_health_threat'] = False
        self.assertEqual(decisions(row)['EU']['days'], 10)
        row['event'] = 'other'
        self.assertEqual(decisions(row)['EU']['days'], 15)
    def test_duplicate_and_missing_exposure(self):
        with self.assertRaises(ValueError): normalize(read_csv('data/complaints.csv') * 2)
        with self.assertRaises(ValueError): trend(self.rows, read_csv('data/exposure.csv')[:-1])
    def test_redcap_api_post(self):
        def opener(request, timeout):
            self.assertIn(b'content=record', request.data)
            self.assertEqual(timeout, 30)
            return io.BytesIO(json.dumps(read_csv('data/complaints.csv')).encode())
        self.assertEqual(len(normalize(redcap_export('https://example.org/api/', 'fake', opener))), 17)
        with self.assertRaises(ValueError): redcap_export('http://example.org', 'fake', opener)

if __name__ == '__main__': unittest.main()
