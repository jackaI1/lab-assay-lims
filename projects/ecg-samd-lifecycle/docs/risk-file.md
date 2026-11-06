# Risk management file, baseline 0.1.0

Owner and reviewer: Jack Lai. Scope: offline public-data education. There is no authorized clinical use. This is an ISO 14971 style risk record, not a completed device risk-management file.

## Plan and acceptability criteria

Identify foreseeable information hazards and the sequence from software failure to possible harm. Prioritize inherently safer behaviour (invalid-input rejection, abstention and input restriction), then verification controls, then information for the user. Severity describes hypothetical misuse, not an observed patient outcome. Clinical occurrence probabilities are unknown; I do not multiply invented scores to declare safety.

For this educational release, every hazard must have a documented control with an executed test, all results and limitations must be disclosed, and no clinical use may be authorized. No clinical residual-risk acceptance or medical benefit-risk conclusion is possible from these data. Disclaimers alone do not make a diagnostic algorithm safe.

## R-001: Incorrect timing information

Sequence: A beat is missed; RR variability is distorted; a reader interprets a regular flag as reassurance.

Potential harm: Delayed assessment if misused clinically. Severity: Serious.

Initial occurrence estimate: Unknown; not estimated from three records.

**RC-001**: Reject invalid signals. Design inputs: SWR-001.

Verifying tests: `tests/test_core.py::test_signal_rejection`.

**RC-002**: Exercise QRS regression floors on independent annotations. Design inputs: SWR-002.

Verifying tests: `tests/test_integration.py::test_public_record_qrs`, `tests/test_integration.py::test_cli_full_benchmark`.

Residual risk: 76 and 65 beats are missed on records 201 and 203 in the baseline. The flag cannot rule out disease.

Review disposition: Accepted for public offline education only. Unacceptable for clinical release; no patient use authorized.

## R-002: False alarm interpreted as disease

Sequence: Ectopy or noise increases RR variation; the irregular flag is mistaken for an AFIB diagnosis.

Potential harm: Anxiety or unnecessary intervention if misused. Severity: Moderate to serious.

Initial occurrence estimate: Observed false-positive windows; clinical probability unknown.

**RC-003**: Expose nonclinical warning and explicit learning-only output. Design inputs: SWR-009.

Verifying tests: `tests/test_integration.py::test_cli_full_benchmark`.

**RC-004**: Publish per-record false positives and AFIB-proxy limitations. Design inputs: SWR-011.

Verifying tests: `tests/test_integration.py::test_cli_full_benchmark`.

Residual risk: Record 201 has 35 false-positive AFIB-proxy windows and 32.7% proxy PPV. There is no clinical benefit-risk justification.

Review disposition: Accepted for public offline education only. Unacceptable for clinical release; no patient use authorized.

## R-003: Corrupt or unintended input

Sequence: Wrong record, modified annotation or truncated download is processed as trusted data.

Potential harm: Misleading performance claims could support an unsafe downstream change. Severity: Serious.

Initial occurrence estimate: Unknown.

**RC-005**: Restrict dataset and verify all input hashes before reading. Design inputs: SWR-008.

Verifying tests: `tests/test_data.py::test_checksum_rejects_corruption`, `tests/test_data.py::test_only_public_allowlisted_records`, `tests/test_data.py::test_download_failure_never_leaves_valid_cache`.

Residual risk: Initial trusted manifest could be wrong and upstream annotations can contain error. Hashes establish consistency, not clinical truth.

Review disposition: Accepted for public offline education only. Unacceptable for clinical release; no patient use authorized.

## R-004: Unavailable information presented as normal

Sequence: Too few or implausibly spaced beats produce a reassuring result; an abstention is excluded from sensitivity.

Potential harm: False reassurance if misused. Severity: Serious.

Initial occurrence estimate: Observed abstentions; clinical probability unknown.

**RC-006**: Abstain on insufficient or implausible RR sequences. Design inputs: SWR-004.

Verifying tests: `tests/test_core.py::test_insufficient_is_not_regular`.

**RC-007**: Count positive abstentions as misses in conservative sensitivity. Design inputs: SWR-007.

Verifying tests: `tests/test_evaluate.py::test_window_scoring_includes_abstentions`.

Residual risk: Four AFIB-positive windows in record 203 abstain. Conservative sensitivity is 91.7%; finite noise and some artifacts can still produce plausible peaks.

Review disposition: Accepted for public offline education only. Unacceptable for clinical release; no patient use authorized.

## R-005: Biased verification evidence

Sequence: Duplicate matches, nonbeat annotations or mixed/unknown rhythm spans are mislabeled, inflating accuracy.

Potential harm: Unsafe reliance on misleading benchmark results. Severity: Serious.

Initial occurrence estimate: Unknown.

**RC-008**: Enforce one-to-one beat scoring and exclude nonbeat events. Design inputs: SWR-006.

Verifying tests: `tests/test_core.py::test_one_to_one_metrics_and_tolerance`, `tests/test_core.py::test_nonbeat_events_excluded`, `tests/test_core.py::test_nonfinite_beat_indices_are_rejected`.

**RC-009**: Label by known rhythm duration and disclose exclusions. Design inputs: SWR-007.

Verifying tests: `tests/test_core.py::test_rhythm_duration_and_unknown_labels`, `tests/test_core.py::test_unrecognized_rhythm_is_unknown`, `tests/test_evaluate.py::test_window_scoring_includes_abstentions`.

Residual risk: Three selected records are not representative. AFIB proxy labels do not measure general arrhythmia sensitivity; no clinical validation exists.

Review disposition: Accepted for public offline education only. Unacceptable for clinical release; no patient use authorized.

## R-006: Unverified software change

Sequence: A requirement or risk control changes without a verifying test, but the release appears complete.

Potential harm: Undetected regressions in a downstream medical use. Severity: Serious.

Initial occurrence estimate: Unknown.

**RC-010**: Require collected and passed tests for every requirement/control. Design inputs: SWR-010.

Verifying tests: `tests/test_traceability.py::test_requirement_without_test_fails`, `tests/test_traceability.py::test_control_without_verification_fails`, `tests/test_traceability.py::test_absent_skipped_or_failed_test_fails`, `tests/test_traceability.py::test_unknown_links_and_duplicate_ids_fail`, `tests/test_traceability.py::test_matrix_contains_executed_links`, `tests/test_traceability.py::test_junit_outcomes_and_duplicates`, `tests/test_traceability.py::test_gate_cli_fails_for_uncovered_requirement`, `tests/test_traceability.py::test_omitted_unlinked_execution_fails`.

Residual risk: A passing test can have weak assertions. Human design review and broader validation remain necessary; the gate checks evidence completeness, not adequacy.

Review disposition: Accepted for public offline education only. Unacceptable for clinical release; no patient use authorized.

## Overall residual-risk review

The benchmark misses 141 annotated heartbeats across records 201 and 203 and yields substantial AFIB-proxy false positives. Input validation does not detect every noisy signal; hash checking does not establish annotation truth. Test-link coverage does not establish test quality. Remaining risks are unacceptable for diagnosis, triage or treatment. The benefit is educational inspectability and repeatable engineering evidence, not a claimed health benefit.

Decision: release public educational code with these limits, no clinical release. Reassess on any algorithm, dependency, input, labelling or intended-use change. The PR and current CI report provide change-specific verification evidence; neither substitutes for independent clinical review.
