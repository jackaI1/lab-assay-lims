import json
from pathlib import Path
from hpo_validator.evaluation import evaluate


def test_metrics_distinguish_abstention_from_wrong_mapping(ontology, tmp_path):
    path = tmp_path / "sample.csv"
    path.write_text(
        "split,phrase,expected_id,rationale\n"
        "eval,Seizure,HP:0001250,label\n"
        "eval,seizurre,HP:0001250,typo\n"
        "eval,no seizure,,negated\n"
        "eval,Ataxia,HP:0001252,intentionally wrong gold for metric test\n"
    )
    result = evaluate(path, ontology)
    metrics = result["splits"]["eval"]
    assert metrics["total"] == 4
    assert metrics["accepted"] == 2
    assert metrics["correct_accepted"] == 1
    assert metrics["precision"] == 0.5
    assert metrics["coverage"] == 0.5
    assert metrics["exact_decision_accuracy"] == 0.5
    assert metrics["abstained"] == 2
    assert metrics["top3_correct"] == 2
    assert len(result["predictions"]) == 4


def test_real_gold_ids_resolve_to_active_phenotypes():
    from hpo_validator.ontology import Ontology

    ontology = Ontology.load(Path("data/hp.obo"), verify=True)
    import csv

    for row in csv.DictReader(Path("examples/phrases.csv").open()):
        if row["expected_id"]:
            assert ontology.resolve(row["expected_id"])["id"] == row["expected_id"]
            assert ontology.is_phenotype(row["expected_id"])


def test_committed_packet_uses_official_schema():
    from phenopackets import Phenopacket
    from google.protobuf.json_format import ParseDict

    packet = ParseDict(
        json.loads(Path("reports/accepted/phenopacket.json").read_text()), Phenopacket()
    )
    assert packet.subject.id == "fictional-demo"
    assert len(packet.phenotypic_features) == 4


def test_undefined_precision_is_null_when_every_phrase_abstains(ontology, tmp_path):
    path = tmp_path / "none.csv"
    path.write_text("split,phrase,expected_id,rationale\neval,no seizure,,negation\n")
    metrics = evaluate(path, ontology)["splits"]["eval"]
    assert metrics["precision"] is None
    assert metrics["coverage"] == 0.0
    assert metrics["exact_decision_accuracy"] == 1.0
