import unittest
from trial_criteria.parser import parse_criteria
from trial_criteria.evaluate import evaluate


def parsed(text):
    return parse_criteria('Inclusion Criteria:\n\n* ' + text)[0]


class ParserTests(unittest.TestCase):
    def test_age_and_exact_source_offsets(self):
        text = 'Inclusion Criteria:\n\n* Age ≥18 years\n\nExclusion Criteria:\n\n* Platelets < 100 x 10^9/L.'
        rows = parse_criteria(text)
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertEqual(text[row['start']:row['end']], row['sentence'])
        self.assertEqual(rows[0]['rule'], dict(field='age', op='>=', value=18.0, unit='years'))
        self.assertEqual(rows[1]['section'], 'exclusion')
        self.assertEqual(rows[1]['rule'], dict(field='platelets', op='<', value=100.0, unit='10^9/L'))

    def test_simple_fields(self):
        cases = [
            ('Age 18 years or older', 'age', '>=', 18.0, 'years'),
            ('Adults 18 years of age or older.', 'age', '>=', 18.0, 'years'),
            ('Aged 18 to 65 years.', 'age', 'between', [18.0, 65.0], 'years'),
            ('Female participants only.', 'sex', '==', 'female', None),
            ('Patients with classic hairy cell leukemia', 'diagnosis', 'contains', 'classic hairy cell leukemia', None),
            ('Hemoglobin >= 9 g/dL.', 'hemoglobin', '>=', 9.0, 'g/dL'),
            ('Absolute neutrophil count ≥ 1500 cells/µL.', 'anc', '>=', 1500.0, 'cells/uL'),
            ('HbA1c ≥8%.', 'hba1c', '>=', 8.0, '%'),
            ('Creatinine <= 1.5 mg/dL', 'creatinine', '<=', 1.5, 'mg/dL'),
        ]
        for sentence, field, op, value, unit in cases:
            with self.subTest(sentence=sentence):
                self.assertEqual(parsed(sentence)['rule'],dict(field=field,op=op,value=value,unit=unit))

    def test_complex_or_ambiguous_criteria_abstain(self):
        for text in ['Age ≥18 years unless approved by investigator.',
                     'Age ≥18 years or hemoglobin >9 g/dL.',
                     'Patients with diabetes for at least 1 year.',
                     'Patients with no history of diabetes.',
                     'Hemoglobin ≥9 g/dL without transfusion.',
                     'Hemoglobin ≥9 g/dL. Transfusion permitted.',
                     'Platelets >100', 'Age at diagnosis <1 year',
                     'Age 65 to 18 years', 'Hemoglobin < 10 mg/dL',
                     'Diagnosis of suspected diabetes', 'Age ≥18 years and consent obtained.']:
            with self.subTest(text=text):
                self.assertTrue(all(r['rule'] is None for r in parse_criteria('Inclusion:\n* '+text)))

    def test_unknown_section_and_nested_context_abstain(self):
        self.assertIsNone(parse_criteria('Age ≥18 years')[0]['rule'])
        rows = parse_criteria('Inclusion:\n* For cohort A:\n  * Age ≥18 years\nInclusion Criteria:\n* Age ≥21 years\nExclusion:\n* Male')
        self.assertIsNone(rows[1]['rule'])
        self.assertIsNotNone(rows[2]['rule'])
        self.assertEqual(rows[3]['section'], 'exclusion')

    def test_unrecognised_subheadings_do_not_lose_cohort_scope(self):
        for heading in ['Cohort A only:', 'Healthy adult part', 'Additional Exclusion Criteria:']:
            rows = parse_criteria('Inclusion:\n'+heading+'\n\n* Age ≥18 years')
            self.assertIsNone(rows[-1]['rule'])

    def test_nested_exception_also_blocks_parent_rule(self):
        rows = parse_criteria('Inclusion:\n* Age ≥18 years\n  * Unless approved by investigator')
        self.assertIsNone(rows[0]['rule'])
        self.assertIn('Unless approved', rows[0]['context'])
        self.assertEqual(evaluate(rows[0], {'age':17})['status'], 'unknown')

    def test_bulleted_headings_preserve_direction_or_abstain(self):
        rows = parse_criteria('Inclusion:\n* Exclusion Criteria:\n* Age <18 years')
        self.assertEqual(evaluate(rows[-1], {'age':17})['status'], 'not met')
        for heading in ['**Exclusion Criteria:**', '## Exclusion Criteria', '__Exclusion Criteria__']:
            rows = parse_criteria('Inclusion:\n* Age ≥18 years\n'+heading+'\n* Age <18 years')
            self.assertEqual(evaluate(rows[-1], {'age':17})['status'], 'not met')
        for heading in ['Cohort A only:', 'Healthy adult part']:
            rows = parse_criteria('Inclusion:\n* '+heading+'\n* Age ≥18 years')
            self.assertIsNone(rows[-1]['rule'])
        rows = parse_criteria('Inclusion:\n* Age ≥18 years\nAdditional Exclusion Criteria:\n* Female')
        self.assertIsNone(rows[-1]['rule'])
        rows = parse_criteria('Inclusion:\n* Cohort A only:\n  * Exclusion Criteria:\n  * Age <18 years')
        self.assertIsNone(rows[-1]['rule'])

    def test_multiple_sentences_keep_context_and_source(self):
        text = 'Inclusion:\n* Hemoglobin ≥9 g/dL. No transfusion allowed.\n* Age ≥18 years'
        rows = parse_criteria(text)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]['sentence'], 'Hemoglobin ≥9 g/dL.')
        self.assertTrue(all(r['rule'] is None for r in rows[:2]))
        for row in rows:
            self.assertEqual(text[row['start']:row['end']], row['sentence'])


class EvaluationTests(unittest.TestCase):
    def check(self, text, patient, section='inclusion'):
        row = parsed(text)
        row['section'] = section
        return evaluate(row, patient)['status']

    def test_three_states_and_exclusion_direction(self):
        self.assertEqual(self.check('Age ≥18 years', {'age':18}), 'met')
        self.assertEqual(self.check('Age ≥18 years', {'age':17}), 'not met')
        self.assertEqual(self.check('Age ≥18 years', {}), 'unknown')
        self.assertEqual(self.check('Age ≥18 years', {'age':18}, 'exclusion'), 'not met')
        self.assertEqual(self.check('Age ≥18 years', {'age':17}, 'exclusion'), 'met')
        self.assertEqual(self.check('Age ≥18 years unless approved', {'age':18}), 'unknown')

    def test_units_and_boundaries(self):
        self.assertEqual(self.check('Hemoglobin ≥9 g/dL', {'labs':{'hemoglobin':{'value':90,'unit':'g/L'}}}), 'met')
        self.assertEqual(self.check('Platelets >100 x 10^9/L', {'labs':{'platelets':{'value':100000,'unit':'cells/uL'}}}), 'not met')
        self.assertEqual(self.check('Hemoglobin ≥9 g/dL', {'labs':{'hemoglobin':{'value':9,'unit':'mg/dL'}}}), 'unknown')
        self.assertEqual(self.check('Creatinine ≥1.5 mg/dL', {'labs':{'creatinine':{'value':132.6,'unit':'umol/L'}}}), 'met')
        self.assertEqual(self.check('Aged 18 to 65 years', {'age':65}), 'met')
        self.assertEqual(self.check('Aged 18 to 65 years', {'age':66}), 'not met')

    def test_lab_timepoint_is_required_when_source_names_it(self):
        row = parsed('HbA1c ≥8% at screening/baseline.')
        self.assertEqual(row['rule'], dict(field='hba1c', op='>=', value=8.0,
                                          unit='%', timepoint='screening/baseline'))
        patient = {'labs': {'hba1c': {'value': 8, 'unit': '%'}}}
        self.assertEqual(evaluate(row, patient)['status'], 'unknown')
        patient['labs']['hba1c']['timepoint'] = 'screening/baseline'
        self.assertEqual(evaluate(row, patient)['status'], 'met')

    def test_invalid_and_missing_values_never_become_matches(self):
        for v in [None, True, -1, float('nan'), float('inf'), '18', [], {}]:
            self.assertEqual(self.check('Age ≥18 years', {'age':v}), 'unknown')
        for v in [None, True, -1, float('nan'), '9']:
            self.assertEqual(self.check('Hemoglobin ≥9 g/dL', {'labs':{'hemoglobin':{'value':v,'unit':'g/dL'}}}), 'unknown')
        self.assertEqual(self.check('Female', {'sex':'unknown'}), 'unknown')

    def test_diagnosis_absence_requires_explicit_completeness(self):
        text = 'Patients with classic hairy cell leukemia'
        self.assertEqual(self.check(text, {'diagnoses':['classic hairy cell leukemia']}), 'met')
        self.assertEqual(self.check(text, {'diagnoses':['no classic hairy cell leukemia']}), 'unknown')
        self.assertEqual(self.check(text, {'diagnoses':[]}), 'unknown')
        self.assertEqual(self.check(text, {'diagnoses':[], 'diagnoses_complete':True}), 'not met')
        self.assertEqual(self.check(text, {'diagnoses':[], 'diagnoses_complete':'yes'}), 'unknown')


if __name__ == '__main__':
    unittest.main()
