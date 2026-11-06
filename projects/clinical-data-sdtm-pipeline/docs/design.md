# Pipeline design

I use a generated two-arm trial instead of patient records so that anyone can reproduce the example and inspect every deliberate error. No external clinical dataset, names, dates of birth or patient identifiers are needed. The study identifier is SYNTH01 and subject identifiers are fabricated counters.

The pipeline has four boundaries:

1. A seeded generator writes subject, vital-sign, laboratory, adverse-event, exposure and disposition CSV files. Five known errors exercise the review workflow. Source files remain untouched.
2. A versioned mapping specification turns each source field into an SDTM-style variable. Validation runs before release. Queries retain the source row, variable, value, rule, severity, status and a review question. Invalid child rows are quarantined; an invalid demographic record quarantines that subject across every domain. No values are guessed or silently corrected.
3. One metadata specification also drives a REDCap data dictionary, numeric choice coding, repeat-instrument records and a local CSV export/import round trip. It generates Define-XML-style variable, origin and code-list metadata. These are educational subsets, not certified submission files.
4. R consumes only released DM and DS records. Time to death starts at randomization, ends at death or last contact and uses right censoring. A subject needs exactly one terminal disposition. Analysis fails on missing, duplicate or inconsistent endpoints. The report shows exclusions, demographics, Kaplan-Meier curves, an age/sex-adjusted Cox model and proportional-hazards diagnostics.

Alternatives considered were downloading a public pilot study or converting a generic electronic-health-record dataset. The former adds redistribution and availability concerns; the latter needs assumptions about randomization and censoring that an EHR does not supply. A generated trial makes those assumptions explicit. The generator is not a physiological simulator and its treatment difference is programmed, not clinical evidence.

The implementation sequence is Python mapping and validation with adversarial tests, metadata and round-trip tests, then R endpoint/model/report tests and one CI command covering the complete workflow. Structural failures stop the run; row errors produce queries and quarantines. Tests cover units, duplicate keys, invalid dates, terminology, orphan records, negative doses, malformed REDCap values and endpoint integrity.
