"""Evaluate extraction on complete annotated pages, including abstentions."""


def validate(extractions, gold):
    editions = {e["source"]["label"]: e for e in extractions}
    expected_total = accepted_total = exact = review_total = review_caught = 0
    resolved_sample_rows = 0
    fields = {"code": 0, "description": 0, "fee": 0, "page": 0, "prefix": 0}
    errors = []
    for sample in gold["pages"]:
        label, page = sample["label"], sample["page"]
        edition = editions[label]
        actual = {r["code"]: r for r in edition["rows"] if r["page"] == page}
        expected = {r["code"]: r for r in sample["items"]}
        resolved = {r["code"] for r in edition["items"]}
        resolved_sample_rows += sum(code in resolved for code in actual)
        expected_total += len(expected)
        accepted_total += len(actual)
        for code, row in expected.items():
            found = actual.get(code)
            matches = {
                key: found is not None and found[key] == (page if key == "page" else row[key])
                for key in fields
            }
            for key, match in matches.items():
                fields[key] += int(match)
            exact += int(all(matches.values()))
            if not all(matches.values()):
                errors.append(
                    {
                        "label": label,
                        "page": page,
                        "code": code,
                        "mismatched": [k for k, v in matches.items() if not v],
                    }
                )
        for code in actual.keys() - expected.keys():
            errors.append({"label": label, "page": page, "unexpected": code})
        for code in sample["review_codes"]:
            review_total += 1
            caught = any(r.get("code") == code and r["page"] == page for r in edition["review"])
            review_caught += int(caught)
            if not caught or code in actual:
                errors.append({"label": label, "page": page, "review_not_caught": code})
    return {
        "metrics": {
            "sample_pages": len(gold["pages"]),
            "expected_fixed_rows": expected_total,
            "accepted_sample_rows": accepted_total,
            "sample_rows_resolved_within_edition": resolved_sample_rows,
            "exact_rows": exact,
            "exact_precision": exact / accepted_total if accepted_total else 0,
            "exact_recall": exact / expected_total if expected_total else 0,
            "field_correct": fields,
            "review_cases": review_total,
            "review_caught": review_caught,
        },
        "errors": errors,
    }
