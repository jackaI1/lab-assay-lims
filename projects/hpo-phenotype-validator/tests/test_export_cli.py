import json
import subprocess
import sys
import pytest
from google.protobuf.json_format import ParseDict
from phenopackets import Phenopacket
from hpo_validator.export import to_phenopacket
from hpo_validator.reporting import validation_html
from hpo_validator.validation import validate_record


def clean_record():
    return {
        "subject_id": "fictional-demo",
        "fictional": True,
        "features": [
            {"id": "HP:0002069"},
            {"text": "Low muscle tone"},
            {"id": "HP:0001251", "excluded": True},
        ],
    }


def test_export_matches_official_schema_and_preserves_exclusion(ontology):
    report = validate_record(clean_record(), ontology)
    result = to_phenopacket(report, created="2026-11-05T00:00:00Z")
    packet = ParseDict(result, Phenopacket())
    assert packet.subject.id == "fictional-demo"
    assert packet.meta_data.phenopacket_schema_version == "2.0"
    assert packet.meta_data.resources[0].version == "test-release"
    assert packet.meta_data.created_by == "hpo-phenotype-validator"
    assert [(f.type.id, f.excluded) for f in packet.phenotypic_features] == [
        ("HP:0001251", True),
        ("HP:0001252", False),
        ("HP:0002069", False),
    ]


@pytest.mark.parametrize(
    "feature", [{"id": "HP:9999999"}, {"text": "seizurre"}, {"id": "HP:0002069", "excluded": True}]
)
def test_export_refuses_unresolved_or_contradictory_list(ontology, feature):
    record = clean_record()
    record["features"].append(feature)
    with pytest.raises(ValueError, match="review"):
        to_phenopacket(validate_record(record, ontology))


def test_html_escapes_input_and_shows_audit(ontology):
    record = clean_record()
    record["subject_id"] = "<script>alert(1)</script>"
    record["features"].append({"text": "<img src=x onerror=alert(1)>"})
    html = validation_html(validate_record(record, ontology))
    assert "<script>" not in html
    assert "<img src=x" not in html
    assert "&lt;script&gt;" in html
    assert "HP:0002069" in html


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "hpo_validator", *map(str, args)],
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_cli_writes_real_reports_and_packet(tmp_path):
    source = tmp_path / "subject.json"
    source.write_text(json.dumps(clean_record()))
    out = tmp_path / "out"
    result = run_cli("validate", source, "--ontology", "tests/fixtures/mini.obo", "--out", out)
    assert result.returncode == 0, result.stderr
    packet = ParseDict(json.loads((out / "phenopacket.json").read_text()), Phenopacket())
    assert len(packet.phenotypic_features) == 3
    assert (out / "validation.html").is_file()
    assert json.loads((out / "validation.json").read_text())["exportable"] is True


def test_cli_review_exit_and_no_packet(tmp_path):
    source = tmp_path / "subject.json"
    source.write_text(
        json.dumps(
            {
                "subject_id": "fictional-review",
                "fictional": True,
                "features": [{"text": "seizurre"}],
            }
        )
    )
    out = tmp_path / "out"
    result = run_cli("validate", source, "--ontology", "tests/fixtures/mini.obo", "--out", out)
    assert result.returncode == 2
    assert not (out / "phenopacket.json").exists()
    assert (out / "validation.html").is_file()


def test_cli_does_not_overwrite_existing_outputs(tmp_path):
    source = tmp_path / "subject.json"
    source.write_text(json.dumps(clean_record()))
    out = tmp_path / "out"
    out.mkdir()
    sentinel = out / "phenopacket.json"
    sentinel.write_text("original")
    result = run_cli("validate", source, "--out", out)
    assert result.returncode == 1
    assert sentinel.read_text() == "original"


@pytest.mark.parametrize("content", ["not JSON", '{"fictional":true,"fictional":false}', "[]"])
def test_cli_bad_input_fails_cleanly(tmp_path, content):
    source = tmp_path / "subject.json"
    source.write_text(content)
    result = run_cli("validate", source, "--out", tmp_path / "out")
    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize(
    "timestamp,expected",
    [
        ("2026-11-05 12:30:00+00:00", "2026-11-05T12:30:00Z"),
        ("2026-11-05T12:30:00+01:00:30", "2026-11-05T11:29:30Z"),
    ],
)
def test_timestamp_overrides_are_normalized_for_official_schema(ontology, timestamp, expected):
    report = validate_record(clean_record(), ontology)
    result = to_phenopacket(report, created=timestamp)
    assert result["metaData"]["created"] == expected
    ParseDict(result, Phenopacket())


def test_export_rejects_naive_timestamp(ontology):
    with pytest.raises(ValueError, match="timezone"):
        to_phenopacket(validate_record(clean_record(), ontology), created="2026-11-05T12:30:00")
