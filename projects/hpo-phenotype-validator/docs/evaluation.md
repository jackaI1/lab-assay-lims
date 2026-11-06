# What the phrase sample measures

I authored the labels in `examples/phrases.csv` before running the mapper. I used the preferred labels, exact synonyms and definitions in the bundled public HPO release. The CSV records an expected primary ID, or an empty ID when one phrase should not be mapped automatically, plus a rationale. These are fictional phrases, not extracted patient notes. I did the labelling as the project author; this is not a clinician-labelled or independently adjudicated dataset.

`dev` rows describe ordinary use cases. `eval` rows add exact synonyms, spelling mistakes, plain-language paraphrases, negation, uncertainty, multiple findings, administrative text and ambiguous descriptions. The split is fixed. Nothing is trained, and no score cutoff was tuned to the evaluation rows. The same author designed the matcher, so this split is not a blinded independent assessment. Exact names and synonyms intentionally test the dictionary itself; this does not measure understanding of unseen clinical language.

The mapping policy was chosen before evaluation: only a unique preferred label or exact synonym, after case and whitespace normalization, is accepted. Spelling suggestions never become accepted features automatically, even if the score is high. Context such as negation or uncertainty remains in review. For example, `no seizure` is not converted into an exclusion: a person must explicitly use `excluded: true` after review. A broad synonym is not treated as equivalent to an exact synonym.

Every prediction, accepted ID, candidate, score, gold ID and correctness flag is in `reports/mapping.json`. `reports/README.md` shows the aggregate table and individual decisions. `scripts/build_reports.py --check` recomputes the artifacts from the source files and compares their bytes, including the ontology checksum.

## Counts and denominators

- Precision: correct accepted IDs divided by all accepted IDs. Undefined precision is JSON null when no phrase maps.
- Coverage: accepted phrases divided by all phrases, including intentionally unmappable ones.
- Mapping recall: correct accepted IDs divided by phrases with a gold ID.
- Exact decision accuracy: correct IDs plus correct abstentions for empty gold IDs, divided by all phrases. An abstention on a mappable phrase counts as incorrect here.
- Top-3 recall: gold IDs found among the first three suggestions divided by phrases with a gold ID. A suggestion counts here even though it remains unmapped for export.

The score is a deterministic spelling similarity in the range zero to one. A unique dictionary match gets one. Fuzzy candidates are shortlisted by shared character trigrams, then ranked by Python's `SequenceMatcher` character similarity. A shared exact synonym can also score one and still remain ambiguous. This is not a calibrated probability, semantic confidence or medical confidence.

The saved example export uses the actual initial creation timestamp stored in `examples/report-config.json` for byte-for-byte regeneration. Ordinary CLI exports use their current creation time. No patient dates are supplied or inferred.

## Limits

This small, authored English sample cannot estimate clinical performance. Lexical ranking can miss paraphrases, confuse closely related findings and return poor candidates for irrelevant text. The tool does not interpret full notes, diagnose a condition, verify a subject's fictional status, infer onset or reconcile findings recorded at different times. Its contradiction checks use asserted `is_a` ancestry and explicit exclusions, not all HPO logical axioms or disease knowledge. Use fictional data only.
