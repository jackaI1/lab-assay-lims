# Software requirements, baseline 0.1.0

Controlled source: `lifecycle.json`. IDs, acceptance criteria and test links are reviewed together. The generated matrix records executed verification. These are engineering requirements for offline education, not clinical performance claims.

## SWR-001

Reject nonfinite, flat, multidimensional or shorter-than-10-second signals and sample rates outside 100 to 1000 Hz.

Rationale: Do not silently process invalid ECG input.

Verification: `tests/test_core.py::test_signal_rejection`.

## SWR-002

Detect QRS peaks from channel 0 using XQRS without annotation input; achieve QRS sensitivity and PPV >=0.90 on each full demonstration record, and >=0.98 on the first minute of record 100.

Rationale: A regression floor for this dataset subset, not a clinical acceptance criterion.

Verification: `tests/test_integration.py::test_public_record_qrs`, `tests/test_integration.py::test_cli_full_benchmark`.

## SWR-003

Compute RR mean, population CV and RMSSD; flag irregular only when CV >=0.12 and RMSSD/mean >=0.08.

Rationale: Keep decisions explainable with timing features.

Verification: `tests/test_core.py::test_regular_and_irregular_windows`, `tests/test_core.py::test_both_irregularity_conditions_are_required`.

## SWR-004

Return insufficient_data when fewer than 10 RR intervals exist or any RR is outside inclusive 0.25 to 2.5 s.

Rationale: Missing or implausible timing must not become a regular result.

Verification: `tests/test_core.py::test_insufficient_is_not_regular`.

## SWR-005

Use complete 30-second windows, exclude crossing RR intervals, and reject invalid peak indices.

Rationale: Prevent duplicate beats, partial windows and unit mistakes.

Verification: `tests/test_core.py::test_window_boundaries_and_peak_validation`.

## SWR-006

Score only annotated beats with chronological one-to-one matching at inclusive 150 ms; report TP, FP, FN, sensitivity and PPV, with null for empty denominators.

Rationale: Avoid inflated metrics from duplicate matches or rhythm events counted as beats.

Verification: `tests/test_core.py::test_one_to_one_metrics_and_tolerance`, `tests/test_core.py::test_nonbeat_events_excluded`, `tests/test_integration.py::test_cli_full_benchmark`, `tests/test_core.py::test_nonfinite_beat_indices_are_rejected`.

## SWR-007

Compare window flags with AFIB rhythm duration: positive >=80%, negative <=20%, otherwise excluded; unknown rhythm is excluded; report abstentions and conservative sensitivity counting positive abstentions as misses.

Rationale: Separate a timing flag from a disease diagnosis and show abstention bias.

Verification: `tests/test_core.py::test_rhythm_duration_and_unknown_labels`, `tests/test_core.py::test_unrecognized_rhythm_is_unknown`, `tests/test_evaluate.py::test_window_scoring_includes_abstentions`.

## SWR-008

Allow only records 100, 201 and 203 from MIT-BIH 1.0.0; verify every header, signal and annotation SHA-256 before parsing; fail closed on corrupt downloads.

Rationale: Keep the demonstration reproducible and avoid arbitrary private paths.

Verification: `tests/test_data.py::test_checksum_rejects_corruption`, `tests/test_data.py::test_only_public_allowlisted_records`, `tests/test_data.py::test_download_failure_never_leaves_valid_cache`.

## SWR-009

Label successful output as a learning exercise and not a cleared device; reject unsupported record IDs with nonzero exit and no new report.

Rationale: Reduce foreseeable misuse and prevent a failed command appearing successful.

Verification: `tests/test_integration.py::test_cli_full_benchmark`, `tests/test_integration.py::test_cli_rejects_unknown_record`.

## SWR-010

Fail traceability if a requirement or control lacks a test, names an absent test, lacks a requirement link, or its current JUnit test is not passing; generate the matrix only after validation.

Rationale: Prevent documentary links from substituting for execution evidence.

Verification: `tests/test_traceability.py::test_requirement_without_test_fails`, `tests/test_traceability.py::test_control_without_verification_fails`, `tests/test_traceability.py::test_absent_skipped_or_failed_test_fails`, `tests/test_traceability.py::test_unknown_links_and_duplicate_ids_fail`, `tests/test_traceability.py::test_matrix_contains_executed_links`, `tests/test_traceability.py::test_junit_outcomes_and_duplicates`, `tests/test_traceability.py::test_gate_cli_fails_for_uncovered_requirement`, `tests/test_traceability.py::test_omitted_unlinked_execution_fails`.

## SWR-011

Write per-record QRS and exploratory AFIB-proxy counts and rates, per-window features/status, abstentions, omitted duration, configuration and input hashes as strict JSON.

Rationale: Regenerate every result and inspect false positives rather than a pooled headline.

Verification: `tests/test_integration.py::test_cli_full_benchmark`, `tests/test_evaluate.py::test_window_scoring_includes_abstentions`.
