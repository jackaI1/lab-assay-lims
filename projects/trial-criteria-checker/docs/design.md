# How I check criteria

I use a small deterministic parser so I can see why each decision was made. An unconstrained language model could cover more wording but would add a service dependency and make abstention harder to audit. Keyword searches alone would incorrectly drop conditions such as “unless” or “within the last month.”

The command downloads recruiting records from the public ClinicalTrials.gov v2 API and saves the response with retrieval time and request URLs. Offline commands reuse that snapshot. Recruitment status describes the saved record, not a promise that a study is recruiting now.

I keep inclusion and exclusion sections, exact text offsets, list nesting and complete criterion context. Only complete, simple criteria in a known section become rules. Complex, nested or multi-sentence criteria stay unknown, including any simple-looking fragments inside them. Every source sentence remains visible. An unrecognized subheading keeps the following scope unknown until the next recognized inclusion/exclusion heading. Nested qualifiers also block their parent rule. A rule stores its field, operator, value, unit and inclusion/exclusion section.

Age uses years. Sex uses the source's wording. Diagnosis comparisons use explicitly supplied terms, without guessing synonyms; an absent diagnosis is unknown unless the fictional record explicitly says its list is complete. Labs require matching known units or a documented exact scale conversion. Missing, invalid and incompatible values stay unknown. Exclusions reverse whether a matched condition is acceptable. The tool never issues an overall eligibility decision.

A small published sample contains complete criteria text from selected downloaded studies, with reference rules written by direct reading before scoring. Exact rule matching counts wrong values, operators, units or sections as errors. This is a development sample, not an independently reviewed clinical benchmark. The saved report includes every unsupported sentence, the fictional input and benchmark results. This is a programming demonstration, not medical advice or a screening service.

## Input and units

The fictional JSON object uses `age` (a nonnegative number in years), `sex` (`male` or `female`), `diagnoses` (explicit strings), and `diagnoses_complete` (only boolean `true` establishes absence). Missing fields are allowed and yield unknown. Lab entries under `labs` have `value` and `unit`. HbA1c sources specifying `at screening/baseline` require that exact `timepoint` on the observation.

Hemoglobin accepts `g/dL` and `g/L`. Platelets and absolute neutrophil count (`anc`) accept `cells/uL` and `10^9/L`. Creatinine accepts `mg/dL` and `umol/L`; HbA1c accepts `%`. Source parsing also normalizes micro-symbol spellings and multiplication notation. Patient input uses these canonical unit strings. Unsupported units, including a mass unit on a cell count, yield unknown. The conversion factors are explicit in `trial_criteria/evaluate.py`; creatinine follows the NIDDK reference linked in the README. Comparisons do not round values or invent a missing laboratory reference range.

The parser accepts only a small diagnosis term vocabulary, defined in `parser.py`. This avoids turning arbitrary medical prose, negation or suspected conditions into diagnoses. It deliberately does not map abbreviations or broaden a subtype to a parent disease. Separate inclusion bullets are reported individually; the tool does not assume a trial-wide AND/OR structure or combine them into an eligibility verdict.

API requests have bounded download sizes, timeouts and retries for temporary network/server failures. Access-denied responses fail immediately. A repeated pagination token fails rather than looping indefinitely. Offline reproduction never calls the network. A report with absent criteria text displays an explicit unknown notice rather than a successful check.
