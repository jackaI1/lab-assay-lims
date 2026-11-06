# fee-schedule-diff

I built a tool that compares editions of BC's public medical fee schedule to learn how the underlying idea works. This is a learning project.

## Run it

From a checkout of this repository, with Python and [uv](https://docs.astral.sh/uv/getting-started/installation/) installed:

```sh
uv sync --frozen --extra dev
uv run python scripts/reproduce.py
```

This verifies saved copies of the original public PDFs, extracts their fee rows, rebuilds the reports and checks the extraction against my hand-checked sample. Open `reports/summary.md` afterwards. The original PDF snapshots are in `data/snapshots/`. The separate `fetch` command downloads fresh copies into the ignored `data/source/` cache. No account or private data is needed.

## What I compare

The saved run found these differences among resolved fixed-price codes:

| Added | Removed | Price changed | Description changed | Letter prefix changed |
| --- | --- | --- | --- | --- |
| 12 | 10 | 6 | 15 | 4 |

There are 47 changed codes. The extractor accepted 3,562 codes in the older edition and 3,567 in the newer edition. It recorded 1,067 review entries in the older edition and 1,050 in the newer one. Review entries are occurrences, so a repeated code can appear more than once. Across both editions, 723 unresolved codes are excluded from comparison.

“Added” and “removed” mean present only in the resolved extraction of that edition. I check the source before treating either as an official addition or deletion. If any occurrence of a code is unresolved in either edition, I exclude that code from both sides. This also excludes some readable entries that appear elsewhere in an unpriced reference list. It makes the report less complete, but avoids calling an extraction failure a removal.

Prices expressed as percentages or several rates go to review. I compare the literal row description, with spacing cleaned up; a short label still needs its section heading for context. I do not compare eligibility notes, preambles or anesthesia levels. Scanned PDFs and unfamiliar layouts need more work. [Design and limits](docs/design.md) explains these choices.

## Compare other editions

The command-line tool also accepts local, searchable PDFs. Supply each PDF's public source URL so the output can link back to it:

```sh
uv run fee-schedule-diff fetch
uv run fee-schedule-diff extract data/source/2024-12-31.pdf \
  --url https://www2.gov.bc.ca/assets/gov/health/practitioner-pro/medical-services-plan/msc_payment_schedule_-_dec_31_2024.pdf \
  --label 2024-12-31 --out tmp/old.json
uv run fee-schedule-diff extract data/source/2025-04-30.pdf \
  --url https://www2.gov.bc.ca/assets/gov/health/practitioner-pro/medical-services-plan/msc_payment_schedule_-_april_30_2025.pdf \
  --label 2025-04-30 --out tmp/new.json
uv run fee-schedule-diff compare tmp/old.json tmp/new.json \
  --out tmp/comparison.json --markdown tmp/comparison.md --short tmp/summary.md
uv run fee-schedule-diff validate tmp/old.json tmp/new.json --out tmp/accuracy.json
```

The supplied validation sample belongs to these editions. For other PDFs, add independently checked rows to a new gold file and pass it with `--gold`. Page links use the PDF viewer's physical page number, which can differ from the section number printed on the page.

## Public sources

I used the Province of British Columbia's [MSC Payment Schedule publication page](https://www2.gov.bc.ca/gov/content/health/practitioner-professional-resources/msp/physicians/payment-schedules/msc-payment-schedule) and these original PDFs:

- [December 31, 2024 edition](https://www2.gov.bc.ca/assets/gov/health/practitioner-pro/medical-services-plan/msc_payment_schedule_-_dec_31_2024.pdf)
- [April 30, 2025 edition](https://www2.gov.bc.ca/assets/gov/health/practitioner-pro/medical-services-plan/msc_payment_schedule_-_april_30_2025.pdf)

Both original downloads succeeded on my Mac; I used no substitute. The provincial server closed connections from the GitHub runner, so I included byte-for-byte copies of those original PDFs for reproducible checks without a network connection. These are historical editions. The PDFs are provincial publications, subject to the province's [copyright terms](https://www2.gov.bc.ca/gov/content/home/copyright). I retain the original PDFs, small public-text test fixtures and derived reports here. The PDF snapshots are unchanged provincial publications, provided for reference, and the reports are my own derived work, not official publications. There are no patient records, claims or connections to private systems.

`data/sources.json` records each URL and its SHA-256 hash, a fingerprint of the file's exact bytes. A changed download fails the check rather than silently changing the comparison. The report records those fingerprints too.

## Tests and limits

There are 5 test source files in this copy. No test pass count is claimed here: I have not re-run the project suite as part of this move. This is a source snapshot, and running it on a new machine may need environment-specific setup.


Project checks run from this directory through the path-filtered hub workflows: `fee-schedule-diff-ci.yml`.

Generated output omitted from this copy: reports/ (generated output). Regenerate it with the project scripts.
