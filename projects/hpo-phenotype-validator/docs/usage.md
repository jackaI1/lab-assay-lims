# Input and review workflow

Run the commands from the repository checkout. Input is one JSON object containing only `subject_id`, `fictional` and a nonempty `features` array. Choose an invented identifier and set `fictional` to the JSON boolean `true`. The flag is an acknowledgement, not a detector of private data.

Each feature contains exactly one of `id` or `text`, plus optional `excluded` as a JSON boolean. Use one finding per row. Additional keys are rejected so onset, laterality or other information cannot be silently discarded. IDs use `HP:` followed by seven digits. Strings are limited to short phrases. Unknown well-formed IDs go to review; malformed input is rejected.

```json
{
  "subject_id": "fictional-example",
  "fictional": true,
  "features": [
    {"id": "HP:0002069"},
    {"text": "Low muscle tone"},
    {"id": "HP:0001251", "excluded": true}
  ]
}
```

```sh
uv run hpo-validate validate examples/needs-review.json --out output-review
# Expected exit code 2: reports saved, export blocked.
uv run hpo-validate validate examples/accepted.json --out output-accepted
# Expected exit code 0: reports and phenopacket.json saved.
```

Output directories must be new or empty. This prevents a stale Phenopacket from a previous run appearing beside a failed review. Output contains `validation.json`, `validation.html`, and `phenopacket.json` only when every row is resolved and no contradiction remains. Invalid inputs or file errors exit with code 1. Command usage errors from the argument parser exit with code 2 before producing reports.

Open the HTML file locally. Row numbers are zero-based. Check replacement paths, candidate labels, redundancy and contradictions. Edit your original JSON to confirm an intended term, remove an unsupported finding or correct an assertion, then run into a fresh directory. The accepted example is a deliberately edited revision of the unresolved one: I removed uncertain rows rather than claiming those phrases were resolved.

An alternative ID is another ID for a current term. An obsolete term has been retired. A single `replaced_by` chain is followed, while ambiguous paths, cycles, missing targets and `consider` suggestions remain unresolved. If an obsolete stanza also appears as an alternative ID, the stanza's retirement instructions take precedence; an alias never overrides an ambiguous retirement.

The validator retains the most specific present feature and the broadest excluded feature. A present child contradicts an excluded parent, but a present parent does not contradict an excluded child. For example, a specific seizure contradicts “no seizures”; a generic seizure and exclusion of one particular seizure type can coexist. All pairs are reported before redundancy is removed.

The bundled ontology is verified against `data/manifest.json` every time. To inspect another public HPO OBO file:

```sh
uv run hpo-validate validate examples/accepted.json --ontology /path/to/public-hp.obo --out other-release
```

Custom files need a `data-version` header, valid HPO IDs and an acyclic `is_a` graph with no dangling active parents. Their computed checksum and version are recorded in the report; they are not checked against the bundled release manifest. This parser reads the identifiers, preferred names, exact synonyms, `is_a`, `alt_id`, `replaced_by`, `consider` and obsolescence tags needed here. It is not a general OBO round-trip editor or an OWL reasoner.
