import pytest
from hpo_validator.validation import validate_record


def record(*features):
    return {"subject_id": "fictional-test", "fictional": True, "features": list(features)}


def test_redundancy_keeps_most_specific_present_term(ontology):
    report = validate_record(record({"id": "HP:0001250"}, {"id": "HP:0002069"}), ontology)
    assert report["cleaned"] == [
        {"id": "HP:0002069", "label": "Bilateral tonic-clonic seizure", "excluded": False}
    ]
    assert report["redundant_pairs"][0]["removed"] == "HP:0001250"


def test_redundancy_keeps_broadest_exclusion(ontology):
    report = validate_record(
        record({"id": "HP:0001250", "excluded": True}, {"id": "HP:0002069", "excluded": True}),
        ontology,
    )
    assert [x["id"] for x in report["cleaned"]] == ["HP:0001250"]


@pytest.mark.parametrize(
    "present,excluded,conflicts",
    [
        ("HP:0002069", "HP:0001250", True),
        ("HP:0001250", "HP:0001250", True),
        ("HP:0001250", "HP:0002069", False),
    ],
)
def test_contradictions_follow_correct_direction(ontology, present, excluded, conflicts):
    report = validate_record(record({"id": present}, {"id": excluded, "excluded": True}), ontology)
    assert bool(report["contradictions"]) is conflicts
    assert report["exportable"] is (not conflicts)


def test_normalization_deduplicates_and_keeps_row_trace(ontology):
    report = validate_record(
        record({"id": "HP:0990001"}, {"id": "HP:0001275"}, {"text": "Seizures"}), ontology
    )
    assert len(report["cleaned"]) == 1
    assert report["rows"][0]["resolution"]["status"] == "replaced"
    assert report["duplicates"] == [1, 2]


def test_unknown_ambiguous_text_and_nonphenotype_block_export(ontology):
    report = validate_record(
        record({"id": "HP:9999999"}, {"text": "seizurre"}, {"id": "HP:0012823"}), ontology
    )
    assert report["exportable"] is False
    assert report["review_rows"] == [0, 1, 2]
    assert report["cleaned"] == []


@pytest.mark.parametrize(
    "value",
    [
        {},
        [],
        {"fictional": False, "subject_id": "real", "features": []},
        record({"id": "HP:1"}),
        record({"text": ""}),
        record({"id": "HP:0001250", "text": "seizure"}),
        record({"id": "HP:0001250", "excluded": "false"}),
        record({"label": "Seizure"}),
        record({"id": "HP:0001250", "onset": "ignored"}),
        record(),
        {"fictional": True, "subject_id": "", "features": [{"text": "Seizure"}]},
    ],
)
def test_malformed_or_nonfictional_inputs_rejected(ontology, value):
    with pytest.raises(ValueError):
        validate_record(value, ontology)
