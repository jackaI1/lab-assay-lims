"""Measure exact decisions and review suggestions on an authored labelled sample."""

import csv
from pathlib import Path

from .mapping import Mapper
from .ontology import Ontology


def evaluate(sample: Path, ontology: Ontology, mapper: Mapper | None = None) -> dict:
    mapper = mapper or Mapper(ontology)
    predictions = []
    with sample.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["split", "phrase", "expected_id", "rationale"]:
            raise ValueError("Sample columns must be split,phrase,expected_id,rationale")
        for row in reader:
            expected = row["expected_id"] or None
            if row["split"] not in {"dev", "eval"} or not row["phrase"] or not row["rationale"]:
                raise ValueError("Every sample row needs split (dev/eval), phrase and rationale")
            if expected and (
                ontology.resolve(expected)["id"] != expected or not ontology.is_phenotype(expected)
            ):
                raise ValueError(f"Gold ID must be an active primary phenotype: {expected}")
            result = mapper.suggest(row["phrase"])
            predictions.append(
                {
                    **row,
                    "expected_id": expected,
                    **result,
                    "correct_decision": result["id"] == expected,
                    "top3_correct": bool(
                        expected and expected in {c["id"] for c in result["candidates"][:3]}
                    ),
                }
            )
    if not predictions:
        raise ValueError("Sample must not be empty")
    splits = {}
    for split in sorted({r["split"] for r in predictions}):
        rows = [r for r in predictions if r["split"] == split]
        accepted = sum(r["id"] is not None for r in rows)
        correct_accepted = sum(r["id"] is not None and r["correct_decision"] for r in rows)
        positives = sum(r["expected_id"] is not None for r in rows)
        correct_decisions = sum(r["correct_decision"] for r in rows)
        top3 = sum(r["top3_correct"] for r in rows)
        negatives = len(rows) - positives
        correct_abstentions = sum(r["expected_id"] is None and r["id"] is None for r in rows)
        splits[split] = {
            "total": len(rows),
            "mappable": positives,
            "expected_unmapped": negatives,
            "accepted": accepted,
            "correct_accepted": correct_accepted,
            "abstained": len(rows) - accepted,
            "correct_decisions": correct_decisions,
            "correct_abstentions": correct_abstentions,
            "precision": correct_accepted / accepted if accepted else None,
            "coverage": accepted / len(rows),
            "mapping_recall": correct_accepted / positives if positives else None,
            "exact_decision_accuracy": correct_decisions / len(rows),
            "top3_correct": top3,
            "top3_recall": top3 / positives if positives else None,
        }
    return {
        "ontology_version": ontology.version,
        "ontology_sha256": ontology.sha256,
        "policy": "Unique normalized preferred label or EXACT synonym only; all fuzzy "
        "suggestions require review. Scores are lexical similarity, not probabilities.",
        "splits": splits,
        "predictions": predictions,
    }


def evaluation_markdown(result: dict) -> str:
    lines = [
        "# Phrase mapping report",
        "",
        "I checked an authored, hand-labelled English phrase sample against the bundled HPO. "
        "All subject lists are fictional. This is a small regression benchmark, "
        "not an independent clinical validation.",
        "",
        f"Ontology: `{result['ontology_version']}`. SHA-256: `{result['ontology_sha256']}`.",
        "",
        result["policy"],
        "",
        "| Split | Phrases | Accepted | Correct accepted | Precision | Coverage | "
        "Exact decision accuracy | Top-3 recall |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

    def percent(value):
        return "n/a" if value is None else f"{value:.1%}"

    for split, m in result["splits"].items():
        lines.append(
            f"| {split} | {m['total']} | {m['accepted']} | {m['correct_accepted']} | "
            f"{percent(m['precision'])} | {percent(m['coverage'])} | "
            f"{percent(m['exact_decision_accuracy'])} | {percent(m['top3_recall'])} |"
        )
    lines.extend(
        [
            "",
            "Precision = correct accepted IDs / accepted IDs. Coverage = accepted "
            "phrases / all phrases. Exact decision accuracy counts the correct ID or "
            "a correct abstention when the gold label is empty. Top-3 recall counts "
            "gold IDs among the first three suggestions / phrases with a gold ID. "
            "The JSON report also includes mapping recall and counts for every denominator.",
            "",
            "Development and evaluation rows were labelled before running the matcher. "
            "There is no trained model or fitted threshold. The author also wrote the "
            "matcher, so the evaluation rows are not a blinded independent test. "
            "Label and synonym lookups intentionally overlap the public dictionary. "
            "Paraphrases expose the limits of lexical matching. See "
            "[sample protocol](../docs/evaluation.md) and [every prediction](mapping.json).",
            "",
            "## Every phrase",
            "",
            "| Split | Phrase | Expected | Accepted | Score | Best suggestion | Decision |",
            "| --- | --- | --- | --- | ---: | --- | --- |",
        ]
    )

    def cell(value):
        return str(value or "unmapped").replace("|", "\\|").replace("\n", " ")

    for r in result["predictions"]:
        best = r["candidates"][0]["id"] if r["candidates"] else None
        lines.append(
            "| "
            + " | ".join(
                map(
                    cell,
                    [
                        r["split"],
                        r["phrase"],
                        r["expected_id"],
                        r["id"],
                        str(r["score"]),
                        best,
                        r["status"],
                    ],
                )
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Fictional list walkthrough",
            "",
            "The [unresolved input](../examples/needs-review.json) becomes "
            "[a blocked report](review/validation.json). It includes obsolete and alternative "
            "identifiers, redundancy, explicit exclusions, unknown IDs and uncertain text. "
            "Review the replacement paths and candidates, then edit the source JSON. "
            "I supplied [an accepted revision](../examples/accepted.json) and "
            "[its exported Phenopacket](accepted/phenopacket.json). The accepted revision "
            "removes the contradictory exclusion and unresolved rows; it does not assert "
            "that the uncertain phrases were resolved.",
            "",
            "For formatted offline reports, download and open `review/validation.html`, "
            "`accepted/validation.html` or `mapping.html`. No installation is needed.",
            "",
        ]
    )
    return "\n".join(lines)
