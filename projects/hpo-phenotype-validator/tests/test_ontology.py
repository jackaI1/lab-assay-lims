from pathlib import Path
import pytest
from hpo_validator.ontology import Ontology


def test_alternative_id_resolves(ontology):
    result = ontology.resolve("HP:0001275")
    assert result["id"] == "HP:0001250"
    assert result["status"] == "alternative"


def test_obsolete_chain_preserves_trace(ontology):
    result = ontology.resolve("HP:0990001")
    assert result["id"] == "HP:0001250"
    assert result["path"] == ["HP:0990001", "HP:0990002", "HP:0001275", "HP:0001250"]
    assert result["status"] == "replaced"


@pytest.mark.parametrize("term", ["HP:0990003", "HP:0990004", "HP:0990005", "HP:9999999"])
def test_unresolved_ids_are_never_guessed(ontology, term):
    assert ontology.resolve(term)["id"] is None


def test_transitive_ancestry_and_phenotype_scope(ontology):
    assert "HP:0000118" in ontology.ancestors("HP:0002069")
    assert ontology.is_phenotype("HP:0002069")
    assert not ontology.is_phenotype("HP:0012823")
    assert not ontology.is_phenotype("HP:0000118")


@pytest.mark.parametrize(
    "body",
    [
        "[Term]\nid: HP:0000001\nname: A\nis_a: HP:0000002\n",
        "[Term]\nid: HP:0000001\nname: A\nis_a: HP:0000001\n",
        "[Term]\nid: HP:0000001\nname: A\n\n[Term]\nid: HP:0000001\nname: B\n",
    ],
)
def test_broken_graphs_are_rejected(tmp_path, body):
    path = tmp_path / "bad.obo"
    path.write_text("data-version: test\n" + body)
    with pytest.raises(ValueError):
        Ontology.load(path)


def test_obsolete_cycle_abstains(tmp_path):
    path = tmp_path / "cycle.obo"
    path.write_text(
        "data-version: test\n[Term]\nid: HP:0000001\nname: A\n"
        "is_obsolete: true\nreplaced_by: HP:0000001\n"
    )
    assert Ontology.load(path).resolve("HP:0000001")["id"] is None


def test_pinned_ontology_integrity_and_real_terms():
    ont = Ontology.load(Path("data/hp.obo"), verify=True)
    assert ont.resolve("HP:0000057")["id"] == "HP:0008665"
    assert ont.resolve("HP:0001366")["id"] == "HP:0000252"
    assert ont.resolve("HP:0000489")["id"] is None
    assert "HP:0001250" in ont.ancestors("HP:0002069")


def test_checksum_failure_is_explicit(tmp_path):
    path = tmp_path / "hp.obo"
    path.write_text("corrupt")
    (tmp_path / "manifest.json").write_text('{"sha256":"wrong"}')
    with pytest.raises(ValueError, match="checksum"):
        Ontology.load(path, verify=True)


def test_obsolete_stanza_also_used_as_alias_retains_replacement_status(tmp_path):
    path = tmp_path / "overlap.obo"
    path.write_text(
        "data-version: test\n[Term]\nid: HP:0000001\nname: A\n"
        "alt_id: HP:0000002\n[Term]\nid: HP:0000002\nname: obsolete B\n"
        "is_obsolete: true\nreplaced_by: HP:0000001\n"
    )
    result = Ontology.load(path).resolve("HP:0000002")
    assert result["id"] == "HP:0000001"
    assert result["status"] == "replaced"


def test_alias_cannot_override_ambiguous_retirement(tmp_path):
    path = tmp_path / "ambiguous.obo"
    path.write_text(
        "data-version: test\n[Term]\nid: HP:0000001\nname: A\n"
        "alt_id: HP:0000002\n[Term]\nid: HP:0000002\nname: obsolete B\n"
        "is_obsolete: true\nconsider: HP:0000001\n"
    )
    assert Ontology.load(path).resolve("HP:0000002")["id"] is None


def test_missing_replacement_does_not_map(tmp_path):
    path = tmp_path / "missing.obo"
    path.write_text(
        "data-version: test\n[Term]\nid: HP:0000001\nname: obsolete A\n"
        "is_obsolete: true\nreplaced_by: HP:0000002\n"
    )
    assert Ontology.load(path).resolve("HP:0000001")["id"] is None


def test_obo_comments_and_modifiers_do_not_hide_retirement(tmp_path):
    path = tmp_path / "commented.obo"
    path.write_text(r"""data-version: test-version ! version comment
[Term]
id: HP:0000001
name: Current \! finding \{example\} ! name comment
[Term]
id: HP:0000002
name: obsolete finding
is_obsolete: true {source="test"} ! retired
replaced_by: HP:0000001 {source="test"} ! current
""")
    ont = Ontology.load(path)
    assert ont.version == "test-version"
    assert ont.terms["HP:0000001"].name == "Current ! finding {example}"
    result = ont.resolve("HP:0000002")
    assert result["status"] == "replaced"
    assert result["id"] == "HP:0000001"
