# eeg-session-qc

I built an EEG recording quality checker to learn how the underlying idea works. This is a learning project.

## Try it

I use [uv](https://docs.astral.sh/uv/getting-started/installation/) to install Python and the locked dependencies:

```sh
uv sync --locked --python 3.12
uv run eeg-qc demo
```

The demo downloads public PhysioNet recordings, saves the reports in `reports/`, and runs the injection study. Open `reports/S004R01.html` in a browser. I do not need an account or any private recordings.

To check a different public EDF file (a common recording format):

```sh
uv run eeg-qc report path/to/public-recording.edf --output reports/my-session
# For a recording collected where mains electricity is 50 Hz:
uv run eeg-qc report path/to/public-recording.edf --line-hz 50 --output reports/my-session
```

The command writes both `.html` and `.json`. For other EDFs, I check that auxiliary sensors have standard type prefixes such as `EOG` or `EMG` followed by a space; MNE excludes those sensors. Untyped channels are assumed to be EEG, so an EDF with unlabelled auxiliary sensors needs its channel types corrected before use. It rejects recordings that are too short, contain invalid values or cannot resolve the electrical frequency being checked. Missing forehead sensors produce an explicit caveat because blink screening cannot run.

## Compare rest with imagined movement

I also use the quality checks before comparing quiet rest with imagined movement. The analysis looks at how much signal is present in two frequency ranges, then trains a classifier (a model that chooses between two labels). I compare tests on recordings from the same person with tests on a person the model has never seen. The latter is a more useful check of whether it generalizes to another person.

```sh
uv run python -m eeg_session_qc.imagery
```

## How the code is arranged

I use MNE-Python to read EDF signals in volts and estimate their frequency content. I inspect short time windows for nearly constant sensors, unusually large signals, mains-frequency peaks, slow forehead changes and excess fast activity. The last two checks are proxies for blinks and muscle activity because these recordings do not include dedicated eye or muscle sensors.

- `src/eeg_session_qc/quality.py` measures the signals and explains the score.
- `src/eeg_session_qc/report.py` builds a self-contained, printable summary.
- `src/eeg_session_qc/validation.py` runs paired artifact injections and untreated controls.
- `src/eeg_session_qc/data.py` downloads only pinned public files and checks their SHA-256 fingerprints.
- `src/eeg_session_qc/sources.json` lists each exact public download URL.

The score combines unflagged sensor-time with time free of electrical, blink-like and muscle-like flags. The decision also uses explicit rejection thresholds. It is a rule-based triage score, not a learned probability. Thresholds live in the JSON report; I have not tuned them against expert labels.

## Sources and reuse

I used public data only. The EDF downloads remain in the ignored `data/` folder; saved reports contain public sensor measurements and public recording IDs. The code is MIT licensed; the dataset retains its own attribution licence.

- Schalk, G. [EEG Motor Movement/Imagery Dataset, PhysioNet](https://physionet.org/content/eegmmidb/1.0.0/) ([dataset DOI](https://doi.org/10.13026/C28G6P)). The dataset page describes collection and the Open Data Commons Attribution licence. Every file used is linked in `sources.json`.
- Schalk and colleagues, [BCI2000: A General-Purpose Brain-Computer Interface System](https://doi.org/10.1109/TBME.2004.827072), the original recording-system publication requested by the dataset.
- Pollard and colleagues, [PhysioNet as a global platform for biomedical research](https://doi.org/10.1038/s44360-026-00096-z), the platform citation requested by the dataset page.
- [MNE-Python EDF import documentation](https://mne.tools/stable/auto_tutorials/io/20_reading_eeg_data.html) and [Welch spectrum documentation](https://mne.tools/stable/generated/mne.time_frequency.psd_array_welch.html). My screening thresholds and injection rules are project choices, not published diagnostic criteria.

## Tests and limits

There are 4 test source files in this copy. No test pass count is claimed here: I have not re-run the project suite as part of this move. This is a source snapshot, and running it on a new machine may need environment-specific setup.


Project checks run from this directory through the path-filtered hub workflows: `eeg-session-qc-ci.yml`.

Generated output omitted from this copy: reports/ (generated output). Regenerate it with the project scripts.
