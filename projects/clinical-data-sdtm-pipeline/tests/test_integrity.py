"""Adversarial release checks catch errors that could change downstream results."""
import copy
import pytest
from clinical_pipeline.pipeline import check_domains, map_sources, release
from clinical_pipeline.synthetic import generate
from clinical_pipeline.redcap import dictionary, encode, decode

@pytest.fixture
def trial(tmp_path):
    generate(tmp_path / 'raw',issues=False)
    return map_sources(tmp_path / 'raw')


def test_lab_conversion_is_validated_against_original(trial):
    trial['LB'][0]['LBSTRESN']='999'
    assert any(q['rule']=='CONVERSION' for q in check_domains(trial))


def test_invalid_disposition_excludes_the_subject_across_domains(trial):
    trial['DS'][0]['DSSTDTC']='2025-01-01'
    queries=check_domains(trial)
    assert any(q['rule']=='ENDPOINT' for q in queries)
    accepted,_=release(trial,queries)
    assert all(r['USUBJID']!='SYNTH01-0001' for rows in accepted.values() for r in rows)
    assert check_domains(accepted)==[]


def test_missing_disposition_does_not_silently_censor_subject(trial):
    trial['DS'].pop(0)
    queries=check_domains(trial)
    assert any(q['USUBJID']=='SYNTH01-0001' and q['rule']=='ENDPOINT' for q in queries)
    accepted,_=release(trial,queries)
    assert len(accepted['DM'])==119


@pytest.mark.parametrize('field,value', [('dm_age','NaN'),('dm_rfstdtc','2025-02-30'),('dm_age','17'),('dm_sex','')])
def test_dictionary_enforces_validation_types_and_requiredness(trial,field,value):
    dd=dictionary(); records=encode(trial,dd)
    records[0][field]=value
    with pytest.raises(ValueError):
        decode(records,dd)


def test_repeat_instance_and_record_identity_must_match(trial):
    dd=dictionary(); records=encode(trial,dd)
    records[120]['redcap_repeat_instance']='999'
    with pytest.raises(ValueError,match='identity'):
        decode(records,dd)


def test_child_end_date_outside_followup_is_queried(trial):
    trial['AE'][0]['AEENDTC']='2099-01-01'
    assert any(q['rule']=='STUDY_WINDOW' and q['variable']=='AEENDTC' for q in check_domains(trial))


def test_mismatched_test_name_is_queried(trial):
    trial['VS'][0]['VSTEST']='Diastolic Blood Pressure'
    assert any(q['rule']=='TEST_NAME' for q in check_domains(trial))


def test_malformed_quoted_source_is_rejected_without_silent_text_changes(tmp_path):
    from clinical_pipeline.pipeline import run
    generate(tmp_path/'raw',issues=False)
    path=tmp_path/'raw/events.csv'
    path.write_text(path.read_text().replace('Headache','"Headache"x',1))
    with pytest.raises(ValueError,match='events.csv.*CSV'):
        run(tmp_path/'raw',tmp_path/'out')
    assert not (tmp_path/'out/manifest.json').exists()
