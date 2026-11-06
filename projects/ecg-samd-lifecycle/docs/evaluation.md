# Evaluation protocol, baseline 0.1.0

## Fixed demonstration, not clinical validation

Records 100, 201 and 203, channel 0, MIT-BIH 1.0.0. Each has 650,000 samples at 360 Hz, about 30 minutes. These include mostly regular timing and more difficult irregular recordings. They are a convenience subset, not a random or held-out clinical test set. No training occurs, and thresholds are fixed in the design baseline. Selecting three records and setting regression floors does not establish intended-use performance.

The [dataset page](https://physionet.org/content/mitdb/1.0.0/) describes the recordings and annotations. These are public historical human recordings; it would be inaccurate to call them synthetic or to say no human data is used. No new patient data is collected, no private or identifiable records are used, and no dataset files are committed. The manifest stores hashes and record identifiers only. Cite Moody and Mark (2005), doi:10.13026/C2F305, and the original 2001 database paper. See the dataset's [attribution license](https://physionet.org/content/mitdb/view-license/1.0.0/).

## Heartbeat endpoint

XQRS receives only the measured signal and sample rate, never annotations. All annotated beat types are reference positives, including paced and unclassifiable beats. The explicit WFDB symbol allowlist is `N L R B A a J S V r F e j E n / f Q`. Rhythm changes (`+`), isolated artifacts (`|`), signal-quality markers (`~`), learning markers (`?`) and other nonbeat events are excluded. There is no normal-beats-only filter that would hide difficult morphology.

Sort beats chronologically. Match the earliest unmatched predicted and reference beat if within inclusive 54 samples (150 ms at 360 Hz). Otherwise advance the earlier event; each event can match once. This maximizes match count for ordered events at a fixed tolerance; timing error among equally valid pairings is not an endpoint. TP = matched pairs, FP = unmatched detections, FN = unmatched reference beats. Sensitivity = TP/(TP+FN), PPV = TP/(TP+FP). Null means denominator zero. All samples, including the final partial rhythm window, contribute to heartbeat scoring.

The engineering regression floor is >=90% sensitivity and PPV on each full selected record and >=98% on the first minute of record 100. These limits are deliberately distinct from clinical acceptance. No precision estimate or population-level confidence claim is made.

## Timing and irregularity endpoint

Use complete half-open windows `[start, end)` of 30 seconds, beginning at sample 0. A peak exactly at the end belongs to the next window. Include only intervals whose two peaks both lie inside the window; do not bridge a boundary. There are 60 windows per record; 5.555556 seconds at each end are omitted from rhythm screening and reported. This is 180 complete windows across the three records.

At least 10 RR intervals are required. Every interval must fall within inclusive 0.25 to 2.5 seconds; otherwise abstain with `insufficient_data`. This is a plausibility check, not a validated ECG signal-quality assessment. There is no ectopic-beat removal or interpolation. For valid intervals:

- Mean RR = arithmetic mean in seconds.
- CV = population standard deviation divided by mean.
- RMSSD = square root of the mean squared difference between successive RR intervals.
- Normalized RMSSD = RMSSD / mean RR.
- Irregular if CV >=0.12 AND normalized RMSSD >=0.08, otherwise regular.

## AFIB annotation proxy

MIT-BIH includes rhythm-change annotations with auxiliary labels such as `(N` and `(AFIB`. The annotation state persists until the next rhythm-change event. The initial state before the first known label is unknown. Unrecognized labels reset state to unknown. Duration is integrated in sample units, not by majority vote of beat labels. If any part of a window is unknown, exclude the whole window. With fully known rhythm, >=80% AFIB duration is a reference positive, <=20% is a negative, and everything between is mixed and excluded.

For known, unmixed windows with a usable detector result, compare irregular/regular to AFIB positive/negative. Report TP, FP, FN, TN and the same sensitivity/PPV formulas. This does **not** measure general arrhythmia sensitivity: ectopy is a false positive for AFIB but can produce real irregular timing. AFL or other rhythms can be regular. No AFIB performance acceptance threshold is claimed.

Positive and negative abstentions are outside the usable-window confusion matrix and explicitly counted. Conservative sensitivity = TP/(TP+FN+positive abstentions); this makes missed evidence visible. Null is retained for an empty denominator. Every window includes its reference state in the JSON for audit. A duration-weighted or beat-level disease classifier would be a different design requiring a new protocol.

## Reproduction and evidence

`uv sync --frozen --python 3.12` then `uv run --frozen python -m scripts.verify` regenerates all results, tests, matrix and report. The first run needs internet access to download nine public files, roughly 6 MB total. Subsequent runs can use the verified cache offline. Both corrupt existing files and corrupt downloads fail closed; delete a named corrupt file before retrying. Downloads use a timeout and a temporary file which is removed on failure.

CI uploads `benchmark.json` (full per-window results, parameters and all input hashes), `junit.xml`, `traceability.md`, `verification.json` (revision, environment and run link) and `verification-report.md`. The committed report is a local snapshot; current CI artifacts and the run summary identify the revision actually verified. Reports are not medical records.
