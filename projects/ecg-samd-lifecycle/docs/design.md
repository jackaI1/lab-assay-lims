# Design baseline

I want to inspect ECG beat timing and see whether my detector still works after a change, without losing the connection between a requirement, a hazard control and its test. This is an offline learning exercise, not a cleared device or a claim of conformity with IEC 62304 or ISO 14971. Public historical recordings are the only inputs. There is no patient-facing interface, upload endpoint, diagnosis or treatment recommendation.

## Approach

A Python CLI uses WFDB XQRS to find QRS complexes (the electrical peaks used to locate heartbeats) on channel 0. I chose an existing detector plus transparent RR features over a trained classifier because I can inspect its failure modes and reproduce every decision without a training pipeline. Using reference beat positions as detector inputs would make the benchmark misleading, so annotations are read only by evaluation. A custom QRS detector would expand the algorithm-validation work without helping the lifecycle exercise.

Full records 100, 201 and 203 form a deliberately small, varied demonstration, not a representative clinical validation set. The input files are downloaded from the versioned MIT-BIH 1.0.0 endpoint and checked against committed SHA-256 digests. No raw recordings are committed.

## Data flow and decisions

Verified record -> finite, nonflat single-channel signal -> XQRS peaks -> complete, non-overlapping 30-second windows -> RR mean, coefficient of variation and normalized RMSSD -> irregular / regular / insufficient_data. At least 11 peaks are required; any RR outside 0.25 to 2.5 seconds makes the window insufficient. CV >= 0.12 and normalized RMSSD >= 0.08 trigger irregular. No RR interval crossing a window boundary is included. Partial final windows are omitted and reported.

QRS is scored one-to-one within 150 ms of annotated beats. Sensitivity is TP/(TP+FN); positive predictive value is TP/(TP+FP); an empty denominator is null. Non-beat annotation events are excluded. A separate exploratory window comparison uses AFIB rhythm labels: >=80% AFIB time is positive; <=20% with fully known rhythm is negative; mixed or unknown windows are excluded. This comparison is an AFIB proxy, not accuracy for every arrhythmia. Insufficient windows are abstentions and are also counted as missed positives in a conservative sensitivity metric.

## Lifecycle controls

The machine-readable requirements and risk controls reference exact pytest node IDs. The traceability script rejects empty links, duplicates, unknown requirements, absent tests and any linked test that did not pass in the current JUnit result. It generates a Markdown matrix. A single verification command runs offline and real-data tests, the gate and benchmark, then writes a report with revision, environment, data hashes and metrics. CI uploads the evidence even on failure. Clinical release is prohibited regardless of test results.

## Boundaries and change impact

Invalid signals stop processing. Network or checksum failures stop evaluation without publishing a new successful report. Output contains aggregate timings and counts, no waveforms or subject metadata. Thresholds, lead choice, window size, reference-label rules or dependency changes require updating requirements, risks, tests and the full benchmark. False negatives and ectopy-driven false positives remain expected; no claim of medical safety is made.
