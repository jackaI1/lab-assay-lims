import pytest
from hpo_validator.mapping import Mapper


def test_exact_label_and_synonym_are_mapped(ontology):
    mapper = Mapper(ontology)
    assert mapper.suggest("  LOW muscle tone ")["id"] == "HP:0001252"
    assert mapper.suggest("Seizures")["id"] == "HP:0001250"
    assert mapper.suggest("Seizures")["score"] == 1.0


def test_shared_synonym_is_ambiguous(ontology):
    result = Mapper(ontology).suggest("Shared description")
    assert result["id"] is None
    assert result["status"] == "ambiguous"
    assert {x["id"] for x in result["candidates"]} == {"HP:0001251", "HP:0001252"}


def test_typo_suggested_but_never_silently_accepted(ontology):
    result = Mapper(ontology).suggest("seizurre")
    assert result["id"] is None
    assert result["candidates"][0]["id"] == "HP:0001250"
    assert 0 < result["score"] < 1


@pytest.mark.parametrize(
    "phrase",
    ["no seizure", "possible Seizure", "Seizure?", "family history of Seizure", "not Seizure"],
)
def test_context_does_not_become_a_positive_feature(ontology, phrase):
    result = Mapper(ontology).suggest(phrase)
    assert result["id"] is None
    assert result["status"] == "context_review"


def test_broad_synonym_and_nonphenotype_are_not_accepted(ontology):
    mapper = Mapper(ontology)
    assert mapper.suggest("Fits")["id"] is None
    assert mapper.suggest("Clinical modifier")["id"] is None
    assert mapper.suggest("obsolete seizure")["id"] is None


def test_blank_phrase_abstains(ontology):
    assert Mapper(ontology).suggest("   ")["candidates"] == []
