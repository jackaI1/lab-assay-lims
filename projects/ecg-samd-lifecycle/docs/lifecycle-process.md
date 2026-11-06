# Software lifecycle and design-control record

## Intended use and limits

Owner and developer: Jack Lai. Baseline: 0.1.0. This offline research component demonstrates how I connect user need, design inputs, software, risk controls and verification. The user need is to inspect irregular ECG timing and catch regressions while retaining understandable evidence. There is no clinical intended use, live monitoring, alarm, diagnosis or decision about a person.

This is an IEC 62304 style lifecycle and ISO 14971 style risk process, not a claim of conformity with either standard. A real device would need a manufacturer quality system, qualified independent reviews, clinical validation, usability engineering, security work and a regulatory strategy, among other work. The [TGA standards overview](https://www.tga.gov.au/products/medical-devices/software-and-artificial-intelligence-ai/overview/standards-software-based-medical-devices) distinguishes lifecycle and risk-management standards; it is background, not an assertion that this file set meets all clauses. [FDA's general software-validation guidance](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/general-principles-software-validation) is additional background. I have not reproduced paywalled standards or claimed an audit.

## Development and design inputs

- Need: detect and inspect irregular beat timing, then show both algorithm errors and evidence gaps after a change.
- Inputs: fixed public records, fixed timing definitions, per-record metrics, input validation, transparent abstentions and reproducible evidence.
- Controlled input baseline: `lifecycle.json`. Requirement IDs are stable. `requirements.md` is the readable specification; `traceability.md` is generated from the same source.
- Design output: `src/ecg_lifecycle/`, `manifest.json`, `pyproject.toml`, `uv.lock`, tests and the verification workflow.
- Software architecture and external components: `architecture-and-soup.md`.

## Safety classification rationale for the exercise

This educational component has no medical-device release classification. If someone repurposed its flag to rule out a dangerous rhythm, missed findings could contribute to serious injury or death. I therefore treat that hypothetical clinical use conservatively as potentially IEC 62304 class C for planning discussions, without claiming this implementation completes class C activities. Calling the actual project class A merely because its disclaimer says education would conceal that foreseeable misuse. Reclassification requires a real intended use, system-level risk assessment and qualified review.

## Risk and design review

`risk-file.md` records hazard sequences, potential harms, controls, verifying tests and remaining risks. Unknown probabilities remain unknown; three records do not estimate clinical risk. Controls are connected to requirements and passed tests. The overall disposition is suitable for offline education only and unacceptable for clinical release.

The engineering review checks the data boundary, separation of detector/annotations, feature definitions, metric denominators, missing-data handling, dependency changes and test-link failures. Review evidence is the GitHub PR discussion plus CI artifacts. The developer's review is not independent clinical approval. Automated verification checks the design inputs; the offline walkthrough is limited validation of the educational use, not validation of a medical intended use.

## Verification and educational-use walkthrough

1. Run `uv run --frozen python -m scripts.verify` from a clean checkout.
2. Confirm all unit and real-record integration tests pass without skips.
3. Confirm every requirement and risk control has an existing, passed test in the generated matrix.
4. Inspect `build/benchmark.json`: all three full records, every window's features and status, input hashes and method parameters.
5. Read false-positive, missed-beat and abstention results in the report. Confirm that regular output makes no health claim.
6. Confirm the CLI refuses an unsupported record ID and produces no new success result.

Steps 1-6 establish the learning workflow only. Output usefulness for clinical screening has not been validated. No usability study or clinician review was performed.

## Configuration, change and release controls

Git commits, PRs and the lockfile define configuration. `manifest.json` pins the input bytes. CI records the revision, test outcomes, environment and input hashes and retains artifacts for 30 days; the committed local report remains a historical snapshot. A new PR must rerun the full suite and keep the generated matrix current. Branch protection is not claimed; the workflow is the executable check and the PR is the review record.

Before merging, inspect changes to thresholds, window size, sample-rate handling, beat allowlist, rhythm labels, matching tolerance, dependency versions and data selection. Update affected requirements and hazards, add a regression test that reproduces the issue, regenerate evidence and document the disposition. Changing the clinical intended use is outside this release and needs a new safety case.

Release criterion: full tests pass, traceability passes, heartbeat regression floors pass, errors and residual risks remain visible, README and warnings retain the educational boundary, and PR review is complete. This releases public educational code only. The irregular flag has no clinical performance acceptance criterion and cannot pass a clinical release gate.

## Problem resolution and maintenance

Known issues at baseline:

| Issue | Evidence | Disposition |
| --- | --- | --- |
| Missed heartbeats | 76 misses on 201; 65 on 203 | Kept visible in report; no clinical reliance |
| Ectopy and other rhythms trigger false positives | 35 false-positive AFIB-proxy windows on 201 | Timing flag retained as an exploratory aid; not an AFIB classifier |
| Insufficient windows | 2 on 201; 6 on 203, including 4 AFIB-positive windows | Abstain; report conservative sensitivity |
| Small selected dataset | Three of the database's records, one lead | No population generalization or clinical validation claim |
| Missing/transition rhythm state | Unknown and mixed windows exist | Exclude from proxy scoring and disclose count |
| SciPy 1.15.3 wheel fails on macOS 27 | Native library import failure during development | Upgrade to locked 1.16.3; verify full pipeline on Mac and CI |

Future defect reports should include the commit, command, public record ID, expected behaviour and observed output. Never attach private ECGs or identifiable patient records. Reproduce with an allowed public record or synthetic unit fixture, assess affected hazards, fix through a PR, and rerun the full evidence command. A passing rerun is verification of that change, not proof that every possible defect is gone.
