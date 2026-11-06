# clinical-data-sdtm-pipeline

I built a clinical-trial data pipeline to learn how the underlying idea works. This is a learning project.

## What comes out

The default run starts with 120 fictional subjects and three visits each. I planted five mistakes: an unsupported sex code, an implausible blood pressure, a missing lab unit, an event ending before it starts, and a negative dose. The pipeline raises five open queries, quarantines 16 records, and releases 119 subjects for the survival analysis.

![Kaplan-Meier curves from the generated trial](examples/km.png)

A survival curve estimates how many subjects remain alive as follow-up progresses. Crosses mark subjects whose later outcome is unknown. The separation between these curves comes from the generator's settings.

| Output | What I use it for |
| --- | --- |
| `build/demo/source/` | Original fictional records, left unchanged |
| `build/demo/output/query_log.csv` | Review questions, values, rules and exact source rows |
| `build/demo/output/redcap_queries.csv` | The same questions with dictionary field names, forms and repeat instances |
| `build/demo/output/data_quality.html` | Readable summary of errors and exclusions |
| `build/demo/output/sdtm/` | Released study tables for analysis |
| `build/demo/output/redcap_dictionary.csv` | Field names, forms, choices and validation rules |
| `build/demo/output/redcap_records.csv` | Coded records with repeated visits kept separate |
| `build/demo/output/roundtrip_sdtm/` | Tables recovered from that CSV using the dictionary |
| `build/demo/output/define.xml` | Variable descriptions, origins and allowed values |
| `build/analysis/report.html` | Demographics, survival curves, adjusted model and assumptions |

I included [a sample query log](examples/query_log.csv), [REDCap review worksheet](examples/redcap_queries.csv), [quality report](examples/data_quality.html), [REDCap dictionary](examples/redcap_dictionary.csv) and [rendered analysis](examples/report.html). Download the HTML files and open them locally. Each CI run also saves the full generated dataset and reports as a downloadable artifact.

## How the records move

CDISC SDTM is a standard way to organize study records into tables called domains. I map the source files into DM (demographics), VS (vital signs), LB (laboratory tests), AE (adverse events), EX (treatment exposure), and DS (study disposition, including death or last contact).

The [mapping specification](docs/mapping_spec.csv) describes every output variable. For example, glucose collected in mg/dL becomes mmol/L by dividing by 18.0182. I keep both results and units, flag results outside the example's reference range, and check the conversion. The [design notes](docs/design.md) explain why I used a generated trial, and [the data guide](docs/data-guide.md) covers the terminology and review rules.

Each query stays OPEN. A bad DM or DS record excludes that subject across all released tables. Other errors exclude the affected record. The original mapped rows stay in `staging/`, and `quarantine.csv` records every exclusion. This is a review queue, not an automatic claim that the study is ready to lock.

## How I review data with REDCap-style fields

The Data Dictionary CSV defines one instrument (data-entry form) per domain. It includes variable names, field labels, dropdown choice codes, required fields, date and number validation, and limits. For example, `dm_sex` is a dropdown whose stored numeric codes map back to the study's text values. The Data Import Tool uses those raw codes rather than their display labels.

I keep demographics on the nonrepeating `dm` form. The other forms are repeating instruments: each measurement, event or dose has its own instance. `record_id` identifies the subject; `redcap_repeat_instrument` and `redcap_repeat_instance` identify the form and occurrence. An instance is the original sequence number within a subject and domain, not the visit number. Setting up repeating instruments is a separate Project Setup step from uploading the dictionary.

I use edit checks like the discrepancy checks in REDCap's Data Quality tool: missing required values, invalid choices, implausible results and conflicting dates become review questions. To review a run:

1. Open `redcap_queries.csv` and find the record ID, form, field name and repeat instance. The worksheet also keeps the rule, observed value, question and original source CSV record number, counting the header as 1. Values are readable study values, not dropdown codes.
2. Check the named source file and its `source_derivation` column, which explains the source field or calculation. For example, `vs_vsstresn` points back to `value` in `vitals.csv`. Queried rows are in `staging/` and excluded from the released export, so their locators may not exist in `redcap_records.csv`.
3. Keep a copy of the source and previous output, make a reviewer-confirmed correction in the synthetic source copy, then rerun into a fresh output folder. I compare the new findings before releasing data; I do not edit a query's status to bypass a check. [The review walkthrough](docs/redcap.md#review-a-discrepancy-and-rerun) includes the exact rerun command.

All findings in each run remain OPEN. Query IDs restart each run; this worksheet is a review aid, not a persistent audit trail, a database-lock approval or an upload to REDCap's query-resolution system. I export accepted records, read the written dictionary and records back, and reconstruct the study tables. The run fails if any released value changes. This is an offline compatibility check; I have not tested an import into a live REDCap installation. [The REDCap guide](docs/redcap.md) covers the Data Dictionary, Data Import Tool and a manual sandbox check.

## How I analyze the trial

The R code uses tidyverse for data preparation and survival for Kaplan-Meier estimation and a Cox proportional-hazards model. The endpoint is elapsed days from randomization to death or last contact. A subject alive at last contact is right-censored: I know they survived that long, but not what happened afterward.

The Cox model compares assigned arms while adjusting for age and sex. The report includes confidence intervals, numbers at risk and a proportional-hazards diagnostic. It rejects duplicate or missing endpoints, inconsistent dates and invalid covariates. Open queries on safety records do not disappear just because an endpoint analysis can run.

## Reproduction and limits

The default seed is 2026. `--clean` generates the same kind of trial without planted errors; `--subjects` and `--seed` allow other cohorts. Input files and the mapping specification get SHA-256 fingerprints in `manifest.json`. The report records its R and package versions in the report and `session-info.txt`.

The output is an educational SDTM subset in CSV, with Define-XML-style metadata. It is not a complete, schema-certified Define-XML package, an ADaM analysis submission, or a regulator-validated study. Event terms are fictional reported text, not licensed MedDRA coding. The local terminology lists cover this example rather than every published CDISC term. R packages are installed from CRAN; the recorded session versions help explain differences between environments.

## Tests and limits

There are 3 test source files in this copy. No test pass count is claimed here: I have not re-run the project suite as part of this move. This is a source snapshot, and running it on a new machine may need environment-specific setup.


Project checks run from this directory through the path-filtered hub workflows: `clinical-data-sdtm-pipeline-ci.yml`.
