import copy
import unittest

from cpic_tracker.compare import compare_snapshots, render_report
from cpic_tracker.lookup import lookup
from cpic_tracker.snapshot import build_snapshot
from tests.test_sources import tables


def snapshot():
    return build_snapshot(tables(), {'kind': 'fixture', 'url': 'https://api.cpicpgx.org/v1/'})


class CompareTests(unittest.TestCase):
    def test_unchanged_and_reassigned_recommendation_ids_are_quiet(self):
        old = snapshot(); new = copy.deepcopy(old)
        for r in new['tables']['recommendation']:
            r['id'] += 100
        self.assertEqual(compare_snapshots(old, new), [])

    def test_added_removed_level_and_recommendation_changes_have_sources(self):
        old = snapshot(); new = copy.deepcopy(old)
        pairs = new['tables']['pair']
        removed = pairs.pop(0)
        added = copy.deepcopy(removed); added['genesymbol'] = 'DEMO-GENE'; added['pairid'] = 123456789
        pairs.append(added)
        pairs[0]['cpiclevel'] = 'DEMO-LEVEL'
        new['tables']['recommendation'][0]['drugrecommendation'] = 'DEMONSTRATION CHANGE'
        changes = compare_snapshots(old, new)
        self.assertEqual(len(changes), 4)
        self.assertEqual({c['kind'] for c in changes}, {'added', 'removed', 'changed'})
        self.assertTrue(all(c['sources'] for c in changes))
        report = render_report(old, new)
        self.assertIn('DEMONSTRATION CHANGE', report)
        self.assertIn('DEMO-LEVEL', report)
        self.assertIn('https://www.clinpgx.org/guideline/', report)
        self.assertIn('Learning project', report)

    def test_semantic_duplicate_recommendations_rejected(self):
        s = snapshot()
        row = copy.deepcopy(s['tables']['recommendation'][0]); row['id'] = 1
        s['tables']['recommendation'].append(row)
        with self.assertRaises(ValueError):
            compare_snapshots(snapshot(), s)

    def test_guideline_url_change_links_both_versions(self):
        old = snapshot(); new = copy.deepcopy(old)
        new['tables']['guideline'][0]['url'] = 'https://example.org/new-guideline'
        c = compare_snapshots(old, new)
        self.assertEqual(len(c), 1)
        self.assertEqual(len(c[0]['sources']), 2)
        self.assertIn('url', c[0]['fields'])

    def test_pair_without_guideline_uses_explicit_source_record(self):
        old = snapshot(); new = copy.deepcopy(old)
        r = next(p for p in new['tables']['pair'] if p['guidelineid'] is None)
        r['cpiclevel'] = 'DEMO-LEVEL'
        report = render_report(old, new)
        self.assertIn('No linked guideline', report)
        self.assertIn('https://api.cpicpgx.org/v1/pair?', report)

    def test_retirement_and_publication_changes_reported(self):
        old = snapshot(); new = copy.deepcopy(old)
        new['tables']['pair'][0]['removed'] = True
        new['tables']['publication'][0]['title'] = 'DEMO TITLE'
        changes = compare_snapshots(old, new)
        self.assertEqual(len(changes), 2)
        self.assertTrue(all(c['sources'] for c in changes))


class LookupTests(unittest.TestCase):
    def test_verbatim_text_citation_and_context(self):
        s = snapshot()
        result = lookup(s, 'VORICONAZOLE', {'cyp2c19': ' poor metabolizer '}, 'adults')
        self.assertEqual(result['status'], 'guideline')
        row = next(r for r in s['tables']['recommendation'] if r['id'] == 8610618)
        match = result['matches'][0]
        self.assertEqual(match['recommendation'], row['drugrecommendation'])
        self.assertEqual(match['comments'], row['comments'])
        self.assertIn('https://www.clinpgx.org/guideline/', match['guideline_url'])
        self.assertTrue(match['citations'])
        self.assertEqual(match['population'], 'adults')

    def test_population_must_be_explicit_when_ambiguous(self):
        r = lookup(snapshot(), 'voriconazole', {'CYP2C19': 'Poor Metabolizer'})
        self.assertEqual(r['status'], 'needs population')
        self.assertEqual(r['populations'], ['adults', 'pediatrics'])
        self.assertNotIn('matches', r)

    def test_no_inference_for_unknown_or_partial_or_wrong_population(self):
        cases = [('unknown', {'CYP2C19': 'Poor Metabolizer'}, None),
                 ('voriconazole', {'CYP2C19': 'invented'}, 'adults'),
                 ('amitriptyline', {'CYP2C19': 'Intermediate Metabolizer'}, None),
                 ('amitriptyline', {'CYP2C19': 'Intermediate Metabolizer', 'CYP2D6': 'Poor Metabolizer'}, None),
                 ('abacavir', {'HLA-B': '*57:01 negative'}, None),
                 ('voriconazole', {'CYP2C19': 'Poor Metabolizer'}, 'nonexistent'),
                 ('voriconazole', {'CYP2C19': 'Poor Metabolizer', 'OTHER': 'Normal'}, 'adults')]
        for drug, genes, pop in cases:
            with self.subTest(drug=drug, genes=genes):
                result = lookup(snapshot(), drug, genes, pop)
                self.assertEqual(result['status'], 'no guideline')
                self.assertNotIn('matches', result)

    def test_multigene_phenotype_match_requires_all_keys(self):
        s = snapshot(); row = s['tables']['recommendation'][1]
        # Synthetic test variant: a row explicitly keyed by phenotypes only.
        row['lookupkey'] = row['phenotypes'].copy()
        r = lookup(s, 'amitriptyline', row['phenotypes'], 'general')
        self.assertEqual(r['status'], 'guideline')

    def test_retired_pairs_cannot_supply_recommendations(self):
        s = snapshot()
        for p in s['tables']['pair']:
            if p['drugid'] == 'RxNorm:121243': p['removed'] = True
        self.assertEqual(lookup(s, 'voriconazole', {'CYP2C19': 'Poor Metabolizer'}, 'adults')['status'], 'no guideline')

    def test_conflicting_normalized_gene_keys_are_rejected(self):
        s = snapshot()
        row = next(r for r in s['tables']['recommendation'] if r['id'] == 8610618)
        for field in ['phenotypes', 'lookupkey']:
            row[field] = {'CYP2C19': 'Ultrarapid Metabolizer', 'cyp2c19': 'Poor Metabolizer'}
        with self.assertRaises(ValueError):
            lookup(s, 'voriconazole', {'CYP2C19': 'Poor Metabolizer'}, 'adults')
        with self.assertRaises(ValueError):
            lookup(snapshot(), 'voriconazole', {'CYP2C19': 'Normal', 'cyp2c19': 'Poor Metabolizer'}, 'adults')

    def test_drug_id_is_supported_without_fuzzy_matching(self):
        self.assertEqual(lookup(snapshot(), 'RxNorm:121243', {'CYP2C19': 'Poor Metabolizer'}, 'adults')['status'], 'guideline')
        self.assertEqual(lookup(snapshot(), 'voriconazol', {'CYP2C19': 'Poor Metabolizer'}, 'adults')['status'], 'no guideline')
