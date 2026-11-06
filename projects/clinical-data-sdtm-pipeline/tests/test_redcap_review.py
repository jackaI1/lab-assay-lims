"""Review locators must identify the original record, field and source row."""
import copy

from clinical_pipeline import pipeline, redcap
from clinical_pipeline.synthetic import generate


def test_seeded_queries_have_dictionary_fields_and_original_source_links(tmp_path):
    source, output = tmp_path / 'source', tmp_path / 'output'
    generate(source)
    original = {p.name: p.read_bytes() for p in source.iterdir()}
    pipeline.run(source, output)
    queries = pipeline.read_csv(output / 'query_log.csv')
    worksheet = pipeline.read_csv(output / 'redcap_queries.csv')
    assert len(worksheet) == 5
    assert [(q['record_id'], q['form_name'], q['redcap_repeat_instrument'],
             q['redcap_repeat_instance'], q['field_name'], q['source_file'], q['source_row'])
            for q in worksheet] == [
        ('SYNTH01-0001', 'dm', '', '', 'dm_sex', 'subjects.csv', '2'),
        ('SYNTH01-0002', 'vs', 'vs', '1', 'vs_vsstresn', 'vitals.csv', '8'),
        ('SYNTH01-0003', 'lb', 'lb', '1', 'lb_lborresu', 'labs.csv', '8'),
        ('SYNTH01-0006', 'ae', 'ae', '1', 'ae_aeendtc', 'events.csv', '3'),
        ('SYNTH01-0004', 'ex', 'ex', '1', 'ex_exdose', 'exposure.csv', '5'),
    ]
    fields = {f['Variable / Field Name']: f for f in pipeline.read_csv(output / 'redcap_dictionary.csv')}
    for query, row in zip(queries, worksheet):
        assert {k: row[k] for k in query} == query
        assert row['source_derivation']
        assert fields[row['field_name']]['Form Name'] == row['form_name']
    # Invalid coded choices stay readable; they must not disappear via quarantine.
    assert worksheet[0]['value'] == 'X'
    assert worksheet[1]['source_derivation'] == 'value'
    assert all(q['status'] == 'OPEN' for q in worksheet)
    assert {p.name: p.read_bytes() for p in source.iterdir()} == original


def test_review_uses_sequence_not_visit_and_does_not_mutate_queries(tmp_path):
    generate(tmp_path / 'source', issues=False)
    mapped = pipeline.map_sources(tmp_path / 'source')
    mapped['VS'][3]['VSSTRESN'] = '400'  # second measurement at visit 2
    queries = pipeline.check_domains(mapped)
    original = copy.deepcopy(queries)
    worksheet = redcap.query_worklist(mapped, queries)
    assert worksheet[0]['redcap_repeat_instance'] == '4'
    assert worksheet[0]['source_row'] == '5'
    assert worksheet[0]['field_name'] == 'vs_vsstresn'
    assert queries == original


def test_duplicate_instances_keep_separate_source_rows(tmp_path):
    generate(tmp_path / 'source', issues=False)
    mapped = pipeline.map_sources(tmp_path / 'source')
    mapped['VS'].append(copy.deepcopy(mapped['VS'][0]))
    worksheet = redcap.query_worklist(mapped, pipeline.check_domains(mapped))
    assert len(worksheet) == 2
    assert [q['source_row'] for q in worksheet] == ['2', '722']
    assert {q['redcap_repeat_instance'] for q in worksheet} == {'1'}
    assert {q['field_name'] for q in worksheet} == {'vs_vsseq'}


def test_clean_trial_still_writes_review_headers(tmp_path):
    generate(tmp_path / 'source', issues=False)
    pipeline.run(tmp_path / 'source', tmp_path / 'out')
    path = tmp_path / 'out/redcap_queries.csv'
    assert pipeline.read_csv(path) == []
    assert {'query_id', 'record_id', 'form_name', 'redcap_repeat_instance', 'field_name',
            'source_file', 'source_row', 'source_derivation', 'status'} <= set(path.read_text().strip().split(','))


def test_corrected_synthetic_source_is_rechecked_in_a_fresh_run(tmp_path):
    source = tmp_path / 'source'
    generate(source)
    pipeline.run(source, tmp_path / 'before')
    before = (tmp_path / 'before/redcap_queries.csv').read_bytes()
    rows = pipeline.read_csv(source / 'subjects.csv')
    rows[0]['sex'] = 'F'  # simulated reviewer-confirmed correction, not inference
    pipeline.write_csv(source / 'subjects.csv', rows, rows[0].keys())
    result = pipeline.run(source, tmp_path / 'after')
    worksheet = pipeline.read_csv(tmp_path / 'after/redcap_queries.csv')
    assert result['queries'] == 4
    assert result['subjects_released'] == 120
    assert result['quarantined_records'] == 4
    assert {q['form_name'] for q in worksheet} == {'vs', 'lb', 'ae', 'ex'}
    assert all(q['status'] == 'OPEN' for q in worksheet)
    assert (tmp_path / 'before/redcap_queries.csv').read_bytes() == before
