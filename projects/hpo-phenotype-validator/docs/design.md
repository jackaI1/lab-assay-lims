# Validation decisions

The tool reads one fictional subject's list, checks it against a pinned public Human Phenotype Ontology (HPO) release, and keeps a trace from every input row to its result. It runs locally with no service account or network dependency.

## Choices

A remote annotation service would need a network and could change results between runs. A language model could suggest plausible terms without reliable evidence. I chose a local label and exact-synonym index with conservative lexical suggestions: easy to reproduce, inspect and deliberately decline uncertain phrases. A similarity score describes spelling overlap, not medical confidence.

Only a single explicit `replaced_by` path can update an obsolete ID automatically. `consider` is a review suggestion, never a replacement. Alternative IDs resolve to their primary IDs. The graph uses asserted `is_a` edges, with no disease inference or extra logical reasoning.

For present terms, keep the most specific descendant. For excluded terms, keep the broadest ancestor: excluding a broad feature also excludes its descendants. A present descendant contradicts an excluded ancestor, including equality. A present ancestor and excluded descendant can coexist. Report all pairs before removing redundant entries. Never resolve a contradiction automatically. The provisional cleaned list can omit redundant rows, but every original conflict pair remains recorded and blocks export.

Export requires no unresolved rows or contradictions. A person can revise the source file after reviewing the report. The exporter creates a Phenopacket, a standard structured JSON record of a subject's features, and includes ontology version metadata and explicit exclusions. Tests parse it through the official schema bindings.

## Evaluation boundaries

The hand-labelled English phrase sample is authored for this project from public HPO labels and definitions, with no patient records. Development rows demonstrate ordinary labels and synonyms; evaluation rows include paraphrases, typos and phrases intentionally unsuitable for one term. Expected IDs are fixed before implementing the matcher. It is a small authored check, not a blinded clinical benchmark or proof of general accuracy. No patient diagnosis or treatment decision is supported.
