# Screening and validation notes

I keep the report readable and put the measurement details here. This is research screening, not diagnosis or automated acceptance for a specific experiment.

## Input and windows

MNE reads EDF physical units into volts with channel-type inference enabled. Standard `EEG `, `EOG ` and `EMG ` prefixes are interpreted before EEG selection. Untyped labels are assumed to be EEG by MNE; unlabelled auxiliary sensors require corrected channel types before use. I normalize PhysioNet channel names by removing trailing dots and capitalizing labels. All EEG channels are included, even channels already marked bad; the report preserves those marks. There is no rereferencing, interpolation, notch filtering or destructive repair. Each session is one EDF.

A session needs at least two EEG channels and two seconds of finite samples. Its Nyquist frequency (half its sample rate) must exceed the selected 50 or 60 Hz mains frequency by more than 5 Hz. Unsupported bandwidth fails explicitly. Sample indices are split into `ceil(duration / 2)` near-equal windows. This covers every sample, including the final partial interval, without creating a tiny tail window. Times are seconds from the start of the recording.

## Fixed rules

All amplitudes below are microvolts. `quality.py:THRESHOLDS` and each report's `thresholds` contain the values. These are engineering defaults, not clinical criteria.

| Check | Rule in each window |
| --- | --- |
| Flat | Peak-to-peak below 0.5, or a run lasting at least 0.5 seconds with successive changes below 0.01 |
| Noisy | Standard deviation above max(80, five times the median nonflat sensor SD), or peak-to-peak above 500 |
| Line | Welch power in mains ±1 Hz exceeds 10% of total 1 Hz-to-Nyquist power, and mean density there is over eight times the mean density in flanks 2–5 Hz away |
| Blink-like | Peak-to-peak above 120 after a two-pole 5 Hz low-pass filter on Fp1, Fp2 or Fpz |
| Muscle-like | Power in 30–45 Hz divided by power in 4–25 Hz above 0.7, with 30–45 Hz RMS above 8 |

MNE's Welch estimator uses a Hamming window, one full-window FFT, no overlap and DC removal. Power sums include bin width. Zero denominators have a small numerical floor. The slow-signal filter is a forward/backward Butterworth filter on a copy of each window; it introduces edge effects. Already flat/noisy sensors are excluded from the other checks so broadband sensor failure does not automatically become a blink or muscle flag. Artifact flags are screening windows, not exact physiological event onset estimates.

The 30–45 Hz muscle proxy is deliberately below the dataset's Nyquist limit. MNE's common high-frequency muscle defaults are unsuitable for these recordings. Fast brain rhythms and other interference can trigger this proxy; slow movement and drift can trigger the blink proxy. No independent eye measurements are available to establish blink truth. The algorithm does not detect every kind of EEG artifact or guarantee an analysis-ready recording.

## Score and decision

Let B be the fraction of all sensor-seconds flagged flat or noisy. Let A be the fraction of time with any eligible line, blink-like or muscle-like flag. A time window counts once for A even when several artifact types overlap. B accounts for the number of affected sensors. Each window's actual duration is used.

`score = round(100 * (1 - B) * (1 - A), 1)`

The decision is not usable when B is at least 0.20 or A is at least 0.50. Otherwise any flag, missing forehead sensors or preexisting bad-channel mark gives usable with caveats. Only a complete supported check with no caveats gives usable. The thresholds are fixed and intentionally conservative; the score is not a probability and the categories do not have universal scientific meaning.

The JSON includes every channel's SD, peak-to-peak, line ratio/fraction, slow-signal peak-to-peak and muscle ratio/RMS for every window. The HTML summarizes long sensor lists and points to the complete JSON. Colour is supplemented by text counts and reasons. It prints as a one-page A4 summary for each saved example. The saved PDF is a browser print of the matching HTML.

## Injection study

The demo uses the first four sequential eyes-open baseline files, S001R01 through S004R01, not selected for favourable session scores. During development I inspected the first ten baselines for amplitude suitability; only the fourth had reference intervals meeting the forehead/temporal requirements below. The released reproducible study uses the first four, and its small, selected reference pool is a limitation.

I divide each recording into nonoverlapping eight-second candidates; leftover recording time is not used for validation. Within each candidate I retain only sensors with SD strictly between 2 and 40 microvolts and peak-to-peak below 180. A reference needs at least four retained sensors, including a forehead sensor (Fp1/Fp2/Fpz) and temporal sensor (T7/T8/T9/T10). The JSON lists retained and excluded sensors for every reference. This amplitude-only reference screen is separate from the artifact rules. It finds quiet signals, not independently certified clean EEG. References and detector thresholds were not optimized to maximize detection rates.

Each trial makes a new copy of the unchanged reference and injects one artifact between seconds 2 and 4. Each reference gets three levels, 0.6, 1.0 and 1.4, for each artifact. The random generator starts from the supplied seed plus trial index. The first retained sensor is targeted for flat/noisy/line; up to two forehead or temporal sensors are targeted for blink or muscle.

- Flat: replace the first `level` seconds of the injection interval with zero.
- Noisy: independent Gaussian noise with SD `120 * level` microvolts.
- Line: a sinusoid at the selected mains frequency with peak amplitude `35 * level` microvolts.
- Blink: a Gaussian pulse centred at second 3, width parameter 0.12 seconds, peak `180 * level` microvolts.
- Muscle: seeded Gaussian noise restricted by FFT to 30–45 Hz, normalized to unit SD, tapered with a Hann envelope, then scaled by `25 * level` microvolts. Its final RMS differs from the pre-taper scale.

A hit requires the correct type on at least one targeted sensor in a window overlapping the injected interval. This checks coarse localization, not exact duration or every affected sensor. Trials on the same segment are correlated. Flatness is an inserted dropout; blink and muscle signals are mathematical approximations, not actual labelled human events. The study does not test combined artifacts or a broad participant population.

I report all untreated controls, each trial, pooled counts and per-level counts. Paired new-detection rates exclude trials where that target/type/time was already flagged. Untreated flag rates are not false-positive rates because no expert truth is available. Both retained references have line flags on other sensors; their line-injection targets are unflagged at the injection time. A failed reference selection raises an error and produces no invented fallback numbers.

## Reproduction and source integrity

`uv run eeg-qc demo --output /tmp/eeg-qc-reproduced` downloads only `sources.json` entries. Each URL pins a dataset version; each EDF has a SHA-256 hash. A mismatch fails instead of accepting different data. Downloads go to a temporary file that is removed on failure. `provenance.json` records source hashes, recording metadata, library versions and seed command. No substitute is used.

`uv run python scripts/check_evidence.py /tmp/eeg-qc-reproduced` compares trial evidence and source metadata exactly, plus session categories/counts and scores with a small floating-point tolerance. CI runs on Linux; the initial reports were produced on macOS. Very small spectral differences are possible between platforms, so the checker compares decisions rather than requiring identical spectrum decimals. The standalone HTML has no external fonts, scripts, images or server requirement.
