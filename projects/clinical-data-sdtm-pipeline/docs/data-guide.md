# Data and mapping guide

## Source contract

Only the seeded generator in `clinical_pipeline/synthetic.py` supplies data for this project. It creates six CSV files and a provenance marker. The marker is an explicit declaration, not a privacy detector. Do not point this public demonstration at real clinical records. There are no names, dates of birth, contact details or external patient IDs.

The trial shuffles a balanced allocation to ACTIVE or PLACEBO using the seed, with generated ages, sex and race categories. Measurements occur at days 0, 14 and 28. Exposure is one interval of daily oral dosing for 28 days. Some subjects report a headache. A fictional exponential death time is censored at a generated last-contact time. Death is forced to occur after the measurement and dosing window. This deliberately simple trial design is not a simulator of a disease or a treatment effect.

`spec.json` is the versioned variable dictionary. `mapping_spec.csv` is its human-readable companion. Source row references include the header, so source_row=2 is the first record. Sequence numbers preserve source order within each subject. They need not be consecutive after quarantine, which preserves a stable identity for review.

Dates must be full ISO YYYY-MM-DD dates. Study day starts at 1 for the reference start date; a hypothetical pre-start date would have no day zero. This example queries pre-start observations instead of treating them as baseline visits. Partial dates and imputation are outside scope. Glucose uses the project factor 18.0182 mg/dL per mmol/L, rounded to six decimal places. The 3.9 to 6.1 mmol/L reference interval is an illustrative laboratory range, not a clinical rule for all people.

## Terminology baseline

I followed the domain and variable conventions of [SDTMIG 3.3](https://www.cdisc.org/standards/foundational/sdtmig/sdtmig-v3-3/html) with [SDTM 1.7](https://www.cdisc.org/standards/foundational/sdtm/sdtm-v1-7/html). These are a stated baseline rather than a claim to implement every rule of either standard. [NCI publishes CDISC controlled terminology](https://www.cancer.gov/about-nci/organization/cbiit/data-standards/cdisc); full terminology releases are versioned by date.

The checked-in, project-scoped vocabulary is in each field's `terms` array in `spec.json`, reviewed on 2026-11-05. Standard examples include sex M/F/U, severity MILD/MODERATE/SEVERE, yes/no Y/N, vital-sign codes SYSBP/DIABP and lab code GLUC. Arm codes A/P, treatment names ACTIVE/PLACEBO and the SITEID are study-defined. Unit lists are limited to mmHg, mg, mg/dL and mmol/L as applicable. These lists are neither a downloaded full NCI release nor a general-purpose terminology validator. Reported adverse-event terms remain uncoded text; AEDECOD is intentionally absent rather than pretending that text has been medically coded.

## Edit checks and release

| Rule | Review question raised |
| --- | --- |
| REQUIRED | Is a missing required field available? |
| CT | Is the value in this field's allowed vocabulary? |
| NUMERIC / RANGE | Is the value finite, the right type, and plausible? |
| DATE / DATE_ORDER | Are complete dates valid and in the right order? |
| DUPLICATE / IDENTITY | Does the record have an unambiguous key and correct study identity? |
| ORPHAN | Does this record belong to an enrolled subject? |
| STUDY_WINDOW | Is this observation or interval inside recorded follow-up? |
| DOSE | Is the dose nonnegative? |
| CONVERSION / TEST_NAME | Does the standardized lab result or vital-sign label agree with its source? |
| ENDPOINT | Is there exactly one disposition, and does it agree with the death/follow-up record? |

All row queries are ERROR/OPEN in this version. Duplicate keys query both rows, avoiding arbitrary selection. DM and DS queries quarantine the subject everywhere; other queries quarantine the affected record. Quarantine is conservative and does not adjudicate the true value. No blank values are replaced with invented clinical values.

To resolve a query in this demonstration, copy the synthetic source directory, make a reviewed correction there, preserve the original, and run `clinical-pipeline run --source <copy> --output <new-directory>`. Keep both query logs and manifests as the before/after record. This version has no multiuser query database, electronic signatures or database-lock function. The successful release means the implemented checks pass, not that every possible clinical inconsistency has been excluded.

## Analysis contract

R uses released DM and DS, with one row per subject in each. It requires matching identities, matching terminal dates, matching death indicators, complete dates, positive elapsed follow-up and valid covariates. Time is `(DSSTDTC - RFSTDTC)` in days, with event=1 only for DEATH; COMPLETED is administrative right censoring at last contact. No day-1 offset is added to survival durations. The output is a transparent derived analysis table, not a complete ADaM ADSL/ADTTE implementation.

The Cox formula is `Surv(time, event) ~ arm + age + sex`, with PLACEBO as arm reference and Efron handling of ties. The generator has F and M only, so the default sex reference is F. The code also accepts the SDTM unknown-sex value U as its own category. The report provides `cox.zph` diagnostics and states the independent-censoring and proportional-hazards assumptions. [The survival package documentation](https://stat.ethz.ch/R-manual/R-devel/library/survival/html/coxph.html) describes the model fitting method.
