"""Rebuild the saved comparison from pinned public PDFs. Run from the repo root."""

import json
from pathlib import Path

from fee_schedule_diff.cli import download, write
from fee_schedule_diff.compare import compare, markdown
from fee_schedule_diff.extract import extract_pdf
from fee_schedule_diff.validate import validate


def main():
    editions = []
    for source in json.loads(Path("data/sources.json").read_text()):
        path = download(source, "data/snapshots")
        edition = extract_pdf(path, source["url"], source["label"])
        write(f"tmp/{source['label']}.json", edition)
        editions.append(edition)
        print(
            source["label"],
            len(edition["items"]),
            "accepted;",
            len(edition["review"]),
            "review",
            flush=True,
        )
    result = compare(*editions)
    write("reports/comparison.json", result)
    Path("reports/comparison.md").write_text(markdown(result))
    Path("reports/summary.md").write_text(markdown(result, limit=12))
    gold = json.loads(Path("tests/fixtures/gold.json").read_text())
    validation = validate(editions, gold)
    write("reports/accuracy.json", validation)
    print(json.dumps(result["counts"], indent=2))
    print(json.dumps(validation["metrics"], indent=2))
    raise SystemExit(bool(validation["errors"]))


if __name__ == "__main__":
    main()
