# Verification report

Learning exercise only. No clinical release or conformity claim is made.

Run UTC: 2026-11-05T05:17:48.188430+00:00
Revision: `85a646a630e67e0c3b3398116ed40e363f54389d`; working tree dirty: `True`.
Execution: local baseline; CI artifacts are the authoritative CI evidence.
Python: 3.12.14; platform: Darwin.
Dependencies: `{"numpy": "2.2.6", "pandas": "2.2.3", "pytest": "8.4.2", "scipy": "1.16.3", "wfdb": "4.3.1"}`.
Lifecycle input SHA-256: `2701ea4676fd381446f69a77ce94a09f931120ed88cad31f30adec16a2a4ffcc`.
Lockfile SHA-256: `6c7af9c7b8c323a25daeca5471c8209096655c187bad721ad6d02d4d1ec43d8b`.

25 tests passed with no skips; 11 requirements and 10 risk controls have executed verification.

## Heartbeat detection

One-to-one annotated beat matching, inclusive 150 ms tolerance. Sensitivity = TP/(TP+FN); PPV = TP/(TP+FP). No pooled clinical claim.

| Record | TP | FP | FN | Sensitivity | PPV |
| --- | --- | --- | --- | --- | --- |
| 100 | 2273 | 0 | 0 | 100.00% | 100.00% |
| 201 | 1887 | 0 | 76 | 96.13% | 100.00% |
| 203 | 2915 | 18 | 65 | 97.82% | 99.39% |

## Irregular windows compared with AFIB labels

This is an exploratory AFIB proxy, not accuracy for general arrhythmia or a diagnostic test. Complete 30-second windows only. Mixed/unknown windows are excluded; abstentions are reported. Conservative sensitivity includes positive abstentions as false negatives. N/A means an empty denominator.

| Record | TP | FP | FN | TN | Sensitivity | PPV | Excluded | Abstain + / - | Conservative sensitivity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 100 | 0 | 0 | 0 | 59 | N/A | N/A | 1 | 0 / 0 | N/A |
| 201 | 17 | 35 | 0 | 4 | 100.00% | 32.69% | 4 | 0 / 0 | 100.00% |
| 203 | 44 | 8 | 0 | 0 | 100.00% | 84.62% | 2 | 4 / 2 | 91.67% |

| Record | Regular | Irregular | Insufficient | Omitted tail (s) |
| --- | --- | --- | --- | --- |
| 100 | 60 | 0 | 0 | 5.555556 |
| 201 | 4 | 54 | 2 | 5.555556 |
| 203 | 0 | 54 | 6 | 5.555556 |

## Review disposition

The heartbeat regression floor is >=90% sensitivity and PPV per selected full record, and >=98% on the first minute of record 100. These are engineering regression checks only. There is no clinical acceptance threshold for the irregular flag. Record 201 has poor AFIB-proxy PPV; record 203 has positive abstentions. Clinical use remains prohibited.

The versioned source, all nine input SHA-256 hashes, method parameters and every window feature are in `benchmark.json` in the same evidence artifact. `junit.xml`, `traceability.md` and `verification.json` accompany this report. Regenerate with `uv run python -m scripts.verify`.
