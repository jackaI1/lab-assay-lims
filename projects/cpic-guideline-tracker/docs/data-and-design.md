# Data and design

## Reproduce the historical evidence

The release labels below identify CPIC publications of its database. They do not claim that I ran this project on those release dates. Both snapshots record their actual import timestamps. Download the official release files and import them into new filenames:

```sh
curl --fail --location https://files.cpicpgx.org/data/database/cpic_db_dump-v1.57.0.sql.gz -o /tmp/cpic-old.sql.gz
curl --fail --location https://files.cpicpgx.org/data/database/cpic_db_dump-v1.61.0.sql.gz -o /tmp/cpic-new.sql.gz
python3 -m cpic_tracker import-release /tmp/cpic-old.sql.gz \
  --release-tag v1.57.0 \
  --source-url https://files.cpicpgx.org/data/database/cpic_db_dump-v1.57.0.sql.gz \
  --output old.json
python3 -m cpic_tracker import-release /tmp/cpic-new.sql.gz \
  --release-tag v1.61.0 \
  --source-url https://files.cpicpgx.org/data/database/cpic_db_dump-v1.61.0.sql.gz \
  --output new.json
python3 -m cpic_tracker compare old.json new.json --output changes.md
```

The report values should agree; retrieval timestamps will differ. To reproduce the checked-in report exactly, use the checked-in snapshots:

```sh
python3 -m cpic_tracker compare snapshots/release-v1.57.0.json snapshots/release-v1.61.0.json --output /tmp/reproduced-cpic-report.md
diff -u reports/release-changes.md /tmp/reproduced-cpic-report.md
```

The `source.download_sha256` value in each release snapshot hashes the original compressed download. Check it with `shasum -a 256 /tmp/cpic-old.sql.gz /tmp/cpic-new.sql.gz`. The live API snapshot records each request URL, page retrieval time, Content-Range and response-byte SHA-256. The separate `tables_sha256` hashes normalized saved tables and is verified when a snapshot is loaded. A checksum detects modification, not source authenticity or medical validity.

## Data boundaries

`source.py` reads the public API's `pair`, `drug`, `guideline`, `recommendation`, and `publication` endpoints. Publications are filtered to `guidelineid=not.is.null`. API requests select the same columns as the release importer. The release importer reads only these COPY blocks, decodes PostgreSQL text escapes, converts source JSON and arrays, and discards unrelated tables. No SQL is executed. The snapshots contain selected source columns, not the entire CPIC database.

A snapshot is written only after the complete download/import passes validation. Each API page requests `Prefer: count=exact` and uses primary-key ordering with offsets. Server page-size caps are supported. Missing counts, gaps, unexpected empty pages, changed totals, duplicate IDs, missing tables and broken references fail closed. HTTP denial is surfaced without retrying it. A read timeout bounds each request. Run again later if the source is being updated.

There is no claim of transaction-level consistency across endpoints or across pages. Count checks cannot detect same-count content changes during retrieval. Release exports are the stronger source for consistent historical comparisons. The importer requires the documented columns; an incompatible future schema should fail instead of silently losing fields.

`compare.py` compares pairs by gene and drug; recommendations by guideline, drug, population and full lookup key; guidelines and publications by their source IDs; drugs by drug ID. Source order and regenerated recommendation IDs do not create changes. A changed lookup key is represented as a removal and an addition. Changed guideline URLs retain links to both versions. For records with no linked guideline, the report explicitly says there is no linked guideline and links to the current API source record. Numeric API row IDs may be reassigned later, so the saved snapshot and release provenance remain the evidence for historical rows. Removed rows use the older snapshot for citations.

`lookup.py` accepts only exact phenotype and lookup-key maps, normalized for case and edge whitespace. The complete map must match, and every gene must have an active, recommendation-linked pair for that drug and guideline. Rows keyed by activity score or allele status are outside this lookup's scope. All matching rows for a selected population are returned with unchanged recommendation, comments, implications, classification and guideline usage notes. Lookup results include the snapshot source and label numeric-ID API links as current records, because those IDs may be regenerated. Multiple populations require selection. No result is extrapolated to another drug, gene, population or phenotype.

## Offline fixtures and saved artifacts

`tests/fixtures/*.json` are bounded subsets of the checked-in live API capture, selected by source IDs. They contain actual CPIC source text. Test-only changes use labels such as `DEMO-LEVEL` and are never represented as CPIC updates. Tests include single-gene, multigene, activity-score, allele-status and population cases. The release parser also has a synthetic COPY encoding fixture. The test suite regenerates the historical report and lookup example exactly, validates the live capture's page totals, and compares its content with the later release.

`reports/release-changes.md` is the historical comparison. `reports/lookup-example.json` is an example from the later release, not a suggested treatment. The live snapshot was taken separately and its agreement with that release is tested. The repository retains snapshots for reproducibility; a fresh download may differ as CPIC updates its data.

## Limitations

This is a learning project, not clinical decision support. I have not validated it for clinical use. It has no patient input, genotype translation, drug interaction checking, treatment ranking or medical interpretation. CPIC levels alone are never used to generate recommendations. Source text can include “no recommendation”; when an exact source row exists that wording is preserved. An unmatched lookup says “no guideline” within this snapshot and supported input model only.
