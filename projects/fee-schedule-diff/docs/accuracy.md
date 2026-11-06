# How I checked extraction

I transcribed the fee rows from rendered PDF pages into `tests/fixtures/gold.json`. The expected descriptions and fees are separate from the parser output. The adjacent word-coordinate fixtures came from those same public PDF pages using pdfplumber with `x_tolerance=2, y_tolerance=3`. They let tests run without a network connection. The full reproduction command verifies the original PDF snapshots and extracts their text again; it does not use the coordinate fixtures. The snapshots are exact copies of the successful gov.bc.ca downloads, retained because GitHub runners could not download them directly.

The sample contains complete fee-table pages from the out-of-office, critical-care and vascular-surgery sections. It includes wrapped descriptions, a continuation after a price, leading-zero codes, letter prefixes, anesthesia-unit columns, percentage-of-body-area descriptions and multi-price rows. Source links are in the manifest, and the physical page is in each fixture filename and gold entry. The December and April editions sometimes repeat the same service wording, so these are not independent random observations.

Run:

```sh
uv run python scripts/reproduce.py
cat reports/accuracy.json
```

The report counts an exact row only when code, prefix, description, fee and physical page all match. Precision is exact rows divided by all accepted sample rows; recall is exact rows divided by all expected fixed-price sample rows. An omitted row therefore lowers recall, and an unexpected row lowers precision. Multi-price entries have their own review-detection count rather than being called successful fixed-price extractions. The validator exits unsuccessfully on any mismatch.

These scores measure row extraction before edition-wide duplicate quarantine. A correctly read row can still be excluded from comparison because another occurrence of the same code has conflicting wording or a missing fee. That is intentional. The report also records how many sampled rows survive that later filter.

This is a small, deliberately selected regression sample, used while developing the parser. It is not a blind evaluation or an estimate of accuracy across every page, future editions, scanned PDFs, or billing rules. I corrected transcription mistakes by checking the rendered pages. I would enlarge it with separately selected pages before using the output for decisions that depend on complete coverage.

To inspect the same pages locally, with Poppler installed:

```sh
mkdir -p tmp/pdfs
pdftoppm -f 49 -l 50 -scale-to 1800 -png data/snapshots/2025-04-30.pdf tmp/pdfs/april
pdftoppm -f 100 -l 100 -scale-to 1800 -png data/snapshots/2025-04-30.pdf tmp/pdfs/critical
pdftoppm -f 440 -l 440 -scale-to 1800 -png data/snapshots/2025-04-30.pdf tmp/pdfs/surgery
pdftoppm -f 50 -l 51 -scale-to 1800 -png data/snapshots/2024-12-31.pdf tmp/pdfs/december
pdftoppm -f 101 -l 101 -scale-to 1800 -png data/snapshots/2024-12-31.pdf tmp/pdfs/december-critical
```

Every fee-table row on these pages is annotated. General explanatory prose and billing notes are not fee rows. The parser retains the literal row description; a short label such as “Day 1” still depends on the section heading in the PDF. Matching that literal label does not establish that the underlying policy or context stayed the same.
