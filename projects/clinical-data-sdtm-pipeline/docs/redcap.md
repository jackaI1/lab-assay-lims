# REDCap export and local round trip

REDCap uses a data dictionary to define data-entry fields. I follow the [REDCap dictionary column and choice rules documented by UT Dallas](https://atlas.utdallas.edu/TDClient/30/Portal/KB/Article/1142/Editing-the-REDCap-Data-Dictionary): lowercase unique field names, the record ID first, grouped forms, field types and coded choices.

The generated CSV has the standard 18 dictionary columns. `record_id` is the first variable on `dm`, a nonrepeating demographics form. The remaining forms are `vs`, `lb`, `ae`, `ex` and `ds`. Field names have domain prefixes, such as `dm_sex`, so the same SDTM name can appear in multiple forms without colliding. Dropdown choices use integer codes; the codec translates these back to the exact SDTM text. Text fields have date_ymd, integer or number validation when appropriate. Study IDs are synthetic identifiers and are not marked as personal identifiers.

Repeated visits are separate rows with `redcap_repeat_instrument` and `redcap_repeat_instance`. The instance is the original domain sequence number. DM rows have blank repeat fields. There are no longitudinal events in this project.

The pipeline writes the dictionary and records, reads both CSVs back, validates the coded values using that dictionary, reconstructs each domain and compares every released value. The decoder rejects invalid choices, missing required values, invalid dates/numbers, duplicate instances, misplaced fields and mismatched record identities. `roundtrip.json` records the result. This proves the offline codec works against the exported dictionary; it does not prove a particular REDCap server accepted the import.

## Optional manual sandbox check

In a new blank REDCap project that permits repeating instruments:

1. Upload `redcap_dictionary.csv` in the Data Dictionary tool and review its preview.
2. In Project Setup, enable repeating instruments for `vs`, `lb`, `ae`, `ex` and `ds`. Leave `dm` nonrepeating. The dictionary alone does not configure repetition.
3. Import `redcap_records.csv` through Data Import Tool using raw coded values. Review errors before accepting it. Keep this as synthetic test data.
4. Export all records in raw CSV form with repeat-instrument columns. Compare demographic counts, field codes, instances and converted lab values with the original export.

No account, API token or network service is needed for the automated project checks. Server permissions, local REDCap versions, calculated fields, checkbox encodings, surveys and longitudinal events are outside this codec's scope.

## Review a discrepancy and rerun

I use the same review pattern as the [Data Quality tool described by Wisconsin's REDCap support team](https://kb.wisc.edu/smph/informatics/159530): execute checks, inspect discrepancies, review the underlying data and check again. The pipeline's rule names (`CT`, `RANGE`, `REQUIRED`, `DATE_ORDER`, `DOSE`) are local rule identifiers, not REDCap's built-in rule letters or executable REDCap expressions.

After `make demo`, open `build/demo/output/redcap_queries.csv`. It contains all columns from `query_log.csv` plus:

| Column | How I use it |
| --- | --- |
| `record_id` | Find the synthetic subject, such as `SYNTH01-0002` |
| `form_name` | Find the dictionary instrument, such as `vs` |
| `redcap_repeat_instrument` | Same form name for repeated forms; blank for demographics |
| `redcap_repeat_instance` | Original domain sequence within the subject; blank for demographics |
| `field_name` | Find the exact Data Dictionary variable, such as `vs_vsstresn` |
| `source_derivation` | Identify the collected field or calculation to review |

For example, the blood-pressure finding is `SYNTH01-0002`, form `vs`, instance `1`, field `vs_vsstresn`, value `400`. Its source is CSV record `8` in `vitals.csv`, column `value`. The first CSV record is the header; quoted multiline values still count as one record. Repeat instances count measurements, not visits: two blood-pressure measurements at each visit occupy separate instances. Duplicate keys can share a locator, so I keep the source file and record number to distinguish them. Those row numbers and query IDs apply only to the saved run.

The queried records are quarantined before export. I review their mapped values in `staging/` and their collected values in `source/`; I do not expect to find the quarantined rows in the accepted REDCap import CSV. The worksheet keeps readable SDTM values, including invalid values such as sex `X`, without trying to encode them as valid dropdown choices. It is not a Data Import Tool file or a native REDCap query export.

To simulate a reviewer-confirmed correction without losing the original:

```sh
cp -R build/demo/source build/reviewed-source
```

In the copied `subjects.csv`, change the first subject's sex from `X` to `F` **only as a fictional reviewer-confirmed example**. There is no evidence in the generated data that lets the program infer that value. Then run:

```sh
uv run clinical-pipeline run --source build/reviewed-source --output build/reviewed-output
```

The new run has four open findings and 120 released subjects; the four record-level errors remain quarantined. Compare the source fingerprints in each `manifest.json` and both worksheets. The previous output stays unchanged. If a legitimate value still violates an example rule, leave it quarantined while reviewing the rule rather than guessing a correction.

All findings that remain are OPEN. A finding absent from the new run means the check no longer triggers; the program does not record who approved a correction or create a CLOSED query history. Query IDs restart per run, so compare source identity, field and rule rather than query ID alone. I preserve source snapshots and previous outputs for comparison. A production study would need managed query responses, reviewer sign-off, access controls and an audit trail before database lock.

The [FAU REDCap FAQ](https://helpdesk.fau.edu/TDClient/2061/Portal/KB/PrintArticle?ID=141506) documents the raw repeat-instrument columns used by the local export. Uploading the dictionary, configuring repeating instruments and using the Data Import Tool remain separate manual sandbox steps; the automated tests exercise the offline format and checks.

## Define-style metadata

`define.xml` uses ODM and Define namespaces for domain groups, variable definitions, origins and code-list references. Its fixed creation timestamp identifies the fictional study metadata baseline, not the time it was run. It is deliberately called Define-XML-style: it is not XSD-validated or complete enough for a regulatory submission. The project does not produce SAS transport files, full value-level metadata, annotated CRFs, external controlled-terminology dictionaries or submission hyperlinks.
