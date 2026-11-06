"""Validate a list without inventing replacements or resolving clinical conflicts."""

from .mapping import Mapper
from .ontology import ID_PATTERN, Ontology


def check_input(record: dict) -> None:
    if not isinstance(record, dict) or set(record) != {"subject_id", "fictional", "features"}:
        raise ValueError("Input must contain only subject_id, fictional and features")
    if record["fictional"] is not True:
        raise ValueError("Only fictional examples are supported; fictional must be true")
    if not isinstance(record["subject_id"], str) or not record["subject_id"].strip():
        raise ValueError("subject_id must be a nonempty fictional identifier")
    features = record["features"]
    if not isinstance(features, list) or not features:
        raise ValueError("features must be a nonempty list")
    for i, item in enumerate(features):
        if not isinstance(item, dict) or set(item) - {"id", "text", "excluded"}:
            raise ValueError(f"Row {i}: unsupported feature fields")
        if ("id" in item) == ("text" in item):
            raise ValueError(f"Row {i}: supply exactly one of id or text")
        if type(item.get("excluded", False)) is not bool:
            raise ValueError(f"Row {i}: excluded must be a JSON boolean")
        value = item.get("id", item.get("text"))
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Row {i}: id/text must be a nonempty string")
        if "id" in item and not ID_PATTERN.fullmatch(value):
            raise ValueError(f"Row {i}: HPO IDs must look like HP:0001250")
        if len(value) > 500:
            raise ValueError(f"Row {i}: id/text exceeds the supported phrase length")


def validate_record(record: dict, ontology: Ontology, mapper: Mapper | None = None) -> dict:
    check_input(record)
    mapper = mapper or Mapper(ontology)
    rows, review, duplicates = [], [], []
    features = {}
    for i, item in enumerate(record["features"]):
        resolution = ontology.resolve(item["id"]) if "id" in item else mapper.suggest(item["text"])
        key = resolution["id"]
        if key is not None and not ontology.is_phenotype(key):
            resolution = {**resolution, "id": None, "status": "not_phenotype"}
            key = None
        rows.append({"index": i, "input": item, "resolution": resolution})
        if key is None:
            review.append(i)
            continue
        pair = (key, item.get("excluded", False))
        if pair in features:
            duplicates.append(i)
        else:
            features[pair] = {"id": key, "label": ontology.terms[key].name, "excluded": pair[1]}
    present = sorted(key for key, excluded in features if not excluded)
    excluded = sorted(key for key, excluded in features if excluded)
    contradictions = [
        {"present": p, "excluded": e}
        for p in present
        for e in excluded
        if p == e or e in ontology.ancestors(p)
    ]
    redundant = []
    removed = set()
    for keys, is_excluded in [(present, False), (excluded, True)]:
        for ancestor in keys:
            for descendant in keys:
                if ancestor in ontology.ancestors(descendant):
                    drop = descendant if is_excluded else ancestor
                    removed.add((drop, is_excluded))
                    redundant.append(
                        {
                            "ancestor": ancestor,
                            "descendant": descendant,
                            "excluded": is_excluded,
                            "removed": drop,
                        }
                    )
    cleaned = [feature for pair, feature in sorted(features.items()) if pair not in removed]
    return {
        "subject_id": record["subject_id"],
        "fictional": True,
        "ontology_version": ontology.version,
        "ontology_sha256": ontology.sha256,
        "rows": rows,
        "review_rows": review,
        "duplicates": duplicates,
        "redundant_pairs": redundant,
        "contradictions": contradictions,
        "cleaned": cleaned,
        "exportable": not review and not contradictions,
    }
