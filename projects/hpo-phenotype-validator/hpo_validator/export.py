"""Export the accepted list as a GA4GH Phenopacket v2 JSON object."""

from datetime import datetime, timezone


def to_phenopacket(report: dict, created: str | None = None) -> dict:
    if not report["exportable"] or report["review_rows"] or report["contradictions"]:
        raise ValueError("Resolve all review rows and contradictions before export")
    created = created or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    stamp = datetime.fromisoformat(created.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("created timestamp must include a timezone")
    created = stamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "id": f"{report['subject_id']}-phenopacket",
        "subject": {"id": report["subject_id"]},
        "phenotypicFeatures": [
            {"type": {"id": f["id"], "label": f["label"]}, "excluded": f["excluded"]}
            for f in report["cleaned"]
        ],
        "metaData": {
            "created": created,
            "createdBy": "hpo-phenotype-validator",
            "phenopacketSchemaVersion": "2.0",
            "resources": [
                {
                    "id": "hp",
                    "name": "Human Phenotype Ontology",
                    "url": "http://purl.obolibrary.org/obo/hp.owl",
                    "version": report["ontology_version"],
                    "namespacePrefix": "HP",
                    "iriPrefix": "http://purl.obolibrary.org/obo/HP_",
                }
            ],
        },
    }
