# ecg-samd-lifecycle

I built a heart-rhythm screening tool to learn how the underlying idea works. This is a learning project.

## Try it

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), a Python environment manager, then run:

```sh
uv sync --frozen --python 3.12
uv run ecg-lifecycle evaluate
```

The first run downloads about 6 MB from PhysioNet. It reads three complete recordings and writes `build/benchmark.json`. Each 30-second window includes its beat-spacing measurements and a `regular`, `irregular` or `insufficient_data` result. A regular result only means the timing thresholds were not crossed; it says nothing about whether a heart is healthy.

To inspect one recording, run `uv run ecg-lifecycle evaluate --records 201 --output build/201.json`. The command accepts only the three public demonstration records. It has no patient upload feature.

## How the detector works

WFDB reads the [MIT-BIH Arrhythmia Database, version 1.0.0](https://physionet.org/content/mitdb/1.0.0/). Its XQRS detector finds the main electrical peaks of heartbeats on the first ECG channel. The detector never receives the reference annotations.

An RR interval is the time from one detected heartbeat to the next. For each complete 30-second window, I calculate the average interval, its coefficient of variation (spread divided by average), and RMSSD (how much neighbouring intervals differ). I flag the window when the coefficient of variation is at least 0.12 and RMSSD divided by the average interval is at least 0.08. Too few intervals or an interval outside 0.25 to 2.5 seconds produces `insufficient_data`.

These simple thresholds do not identify a particular disease. Extra beats, missed beats and noise can all look irregular. I separately compare the flags with AFIB annotations, which mark atrial fibrillation, to make those limitations visible. Mixed or unknown windows are excluded, and abstentions are counted separately. [The evaluation protocol](docs/evaluation.md) explains every denominator.

## Reproduce the evidence

```sh
# Unit tests, real-data integration tests, traceability gate and full benchmark
uv run --frozen python -m scripts.verify

# Fast offline tests, after installing the environment
uv run pytest -m 'not integration'

# Refresh the saved local report and generated matrix after reviewing a change
uv run --frozen python -m scripts.verify --update-docs
```

`build/` contains the report, test results, matrix, environment details, input hashes and every window's features. Raw recordings stay in the ignored `.cache/mitdb/` directory. Set `ECG_DATA_DIR` to reuse a verified cache elsewhere. Every input file is checked against a committed SHA-256 digest before it is read. A corrupt cache stops the command; remove the named file to download it again.

## Tests and limits

There are 5 test source files in this copy. No test pass count is claimed here: I have not re-run the project suite as part of this move. This is a source snapshot, and running it on a new machine may need environment-specific setup.


Project checks run from this directory through the path-filtered hub workflows: `ecg-samd-lifecycle-verify.yml`.
