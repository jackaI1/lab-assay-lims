"""Catch mapping, data-loss and release errors using real CSV inputs."""
import copy
import csv
import json
import xml.etree.ElementTree as ET

import pytest

from clinical_pipeline import pipeline
from clinical_pipeline.synthetic import generate
from clinical_pipeline.redcap import dictionary, encode, decode


@pytest.fixture
def trial(tmp_path):
    source = tmp_path / "source"
    generate(source, n=120, seed=2026, issues=False)
    return pipeline.map_sources(source)


def test_mapping_retains_subjects_and_converts_lab_units(trial):
    assert len(trial["DM"]) == 120
    assert trial["DM"][0]["USUBJID"] == "SYNTH01-0001"
    assert len(trial["VS"]) == 720
    assert len(trial["LB"]) == 360
    first = trial["LB"][0]
    assert float(first["LBSTRESN"]) == pytest.approx(float(first["LBORRES"]) / 18.0182, abs=0.00001)
    assert first["LBSTRESU"] == "mmol/L"
    assert pipeline.check_domains(trial) == []


def test_pipeline_produces_actionable_queries_and_quarantines(tmp_path):
    generate(tmp_path / "raw")
    result = pipeline.run(tmp_path / "raw", tmp_path / "out")
    assert result["subjects_released"] == 119
    assert result["queries"] == 5
    queries = pipeline.read_csv(tmp_path / "out/query_log.csv")
    assert {q["rule"] for q in queries} == {"CT", "RANGE", "REQUIRED", "DATE_ORDER", "DOSE"}
    assert all(q["status"] == "OPEN" and q["question"] and q["source_row"] for q in queries)
    assert len({q["query_id"] for q in queries}) == 5
    for domain in ["DM", "VS", "LB", "AE", "EX", "DS"]:
        rows = pipeline.read_csv(tmp_path / f"out/sdtm/{domain}.csv")
        assert all(r["USUBJID"] != "SYNTH01-0001" for r in rows)
    released = {d: pipeline.read_csv(tmp_path / f"out/sdtm/{d}.csv") for d in pipeline.SPEC}
    assert pipeline.check_domains(released) == []
    assert json.loads((tmp_path / "out/roundtrip.json").read_text())["equal"] is True
    assert (tmp_path / "out/data_quality.html").exists()


@pytest.mark.parametrize("domain,field,value,rule", [
    ("DM", "SEX", "X", "CT"), ("DM", "AGE", "NaN", "NUMERIC"),
    ("DM", "RFSTDTC", "2025-02-30", "DATE"),
    ("VS", "VSSTRESN", "400", "RANGE"),
    ("LB", "LBORRESU", "", "REQUIRED"),
    ("AE", "AEENDTC", "2020-01-01", "DATE_ORDER"),
    ("EX", "EXDOSE", "-1", "DOSE"),
    ("DS", "DSDECOD", "UNKNOWN", "CT"),
])
def test_invalid_values_raise_queries(trial, domain, field, value, rule):
    trial[domain][0][field] = value
    assert any(q["domain"] == domain and q["variable"] == field and q["rule"] == rule
               for q in pipeline.check_domains(trial))


def test_duplicate_keys_query_both_records(trial):
    trial["VS"].append(copy.deepcopy(trial["VS"][0]))
    q = [q for q in pipeline.check_domains(trial) if q["rule"] == "DUPLICATE"]
    assert len(q) == 2
    clean, rejected = pipeline.release(trial, q)
    assert len(clean["VS"]) == 719
    assert len(rejected) == 2


def test_orphan_and_subject_date_checks(trial):
    trial["LB"][0]["USUBJID"] = "SYNTH01-9999"
    trial["VS"][0]["VSDTC"] = "2010-01-01"
    assert {"ORPHAN", "STUDY_WINDOW"} <= {q["rule"] for q in pipeline.check_domains(trial)}


def test_missing_input_fails_without_success_artifacts(tmp_path):
    generate(tmp_path / "raw", issues=False)
    (tmp_path / "raw/labs.csv").unlink()
    with pytest.raises(ValueError, match="labs.csv"):
        pipeline.run(tmp_path / "raw", tmp_path / "out")
    assert not (tmp_path / "out/manifest.json").exists()


def test_roundtrip_preserves_values_and_repeated_forms(trial):
    dd = dictionary()
    records = encode(trial, dd)
    assert decode(records, dd) == trial
    assert records[0]["dm_sex"] in {"1", "2", "3"}
    assert any(r["redcap_repeat_instrument"] == "vs" and r["redcap_repeat_instance"] == "2" for r in records)
    assert dd[0]["Variable / Field Name"] == "record_id"


def test_redcap_rejects_bad_choice_and_duplicate_instance(trial):
    dd = dictionary()
    records = encode(trial, dd)
    bad = copy.deepcopy(records)
    bad[0]["dm_sex"] = "99"
    with pytest.raises(ValueError, match="choice"):
        decode(bad, dd)
    with pytest.raises(ValueError, match="Duplicate"):
        decode(records + [records[0]], dd)


def test_metadata_describes_all_released_columns(tmp_path):
    generate(tmp_path / "raw", issues=False)
    pipeline.run(tmp_path / "raw", tmp_path / "out")
    tree = ET.parse(tmp_path / "out/define.xml")
    ns = {"o": "http://www.cdisc.org/ns/odm/v1.3"}
    items = {x.attrib["OID"] for x in tree.findall(".//o:ItemDef", ns)}
    for d, columns in pipeline.SPEC.items():
        assert all(f"{d}.{v}" in items for v in columns["fields"])
    manifest = json.loads((tmp_path / "out/manifest.json").read_text())
    assert manifest["synthetic_only"] is True
    assert manifest["source_sha256"]["subjects.csv"]


def test_reproducible_run(tmp_path):
    generate(tmp_path / "raw", issues=False)
    pipeline.run(tmp_path / "raw", tmp_path / "one")
    pipeline.run(tmp_path / "raw", tmp_path / "two")
    for name in ["sdtm/DM.csv", "query_log.csv", "redcap_dictionary.csv", "define.xml", "manifest.json"]:
        assert (tmp_path / "one" / name).read_bytes() == (tmp_path / "two" / name).read_bytes()
