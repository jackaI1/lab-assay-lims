"""Rest versus imagery with subject-level evaluation on public EEGBCI data."""

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
import mne
import numpy as np
from scipy.signal import welch
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from eeg_session_qc.data import read_edf
from eeg_session_qc.quality import analyze

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def bandpower_features(epochs, sfreq):
    """Log mean spectral power in alpha and beta for each channel and epoch."""
    freq, psd = welch(epochs, fs=sfreq, nperseg=min(320, epochs.shape[-1]), axis=-1)
    return np.concatenate(
        [
            np.log(np.maximum(psd[..., (freq >= lo) & (freq < hi)].mean(axis=-1), 1e-30))
            for lo, hi in ((8, 13), (13, 30))
        ],
        axis=1,
    )


def evaluate(x, y, subjects, n_boot=2000, seed=42):
    """Score each person equally; resample people, not correlated epochs."""
    ids = np.unique(subjects)
    if len(ids) < 3:
        raise ValueError("At least three retained subjects are required")
    scores = {"within_subject": [], "held_out": []}
    for subject in ids:
        mask = subjects == subject

        def model():
            return make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))

        pred = np.empty(mask.sum(), dtype=int)
        ys = y[mask]
        for train, test in StratifiedKFold(3, shuffle=True, random_state=seed).split(x[mask], ys):
            pred[test] = model().fit(x[mask][train], ys[train]).predict(x[mask][test])
        scores["within_subject"].append(balanced_accuracy_score(ys, pred))
        held = model().fit(x[~mask], y[~mask]).predict(x[mask])
        scores["held_out"].append(balanced_accuracy_score(ys, held))
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, len(ids), (n_boot, len(ids)))
    result = {}
    for key, values in scores.items():
        values = np.asarray(values)
        result[key] = {
            "mean": float(values.mean()),
            "ci": np.quantile(values[indices].mean(axis=1), [0.025, 0.975]).tolist(),
            "subject_accuracy": dict(zip(map(str, ids), map(float, values), strict=False)),
        }
    delta = np.asarray(scores["within_subject"]) - np.asarray(scores["held_out"])
    result["difference"] = {
        "mean": float(delta.mean()),
        "ci": np.quantile(delta[indices].mean(axis=1), [0.025, 0.975]).tolist(),
    }
    return result


def run(subjects, data_dir, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    features, labels, groups, runs = [], [], [], []
    for subject in subjects:
        for run_id in (4, 8, 12):
            path = Path(
                mne.datasets.eegbci.load_data(
                    subject, [run_id], path=str(data_dir), update_path=False, verbose=False
                )[0]
            )
            raw = read_edf(path)
            qc = analyze(raw, session=path.name)
            entry = {
                "subject": subject,
                "run": run_id,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "status": qc["status"],
                "score": qc["score"],
            }
            runs.append(entry)
            if qc["status"] == "not usable":
                continue
            raw.filter(8, 30, verbose=False)
            events, mapping = mne.events_from_annotations(raw, verbose=False)
            epochs = mne.Epochs(
                raw,
                events,
                event_id={k: mapping[k] for k in ("T0", "T1", "T2")},
                tmin=0.5,
                tmax=2.5,
                baseline=None,
                preload=True,
                verbose=False,
            )
            features.append(bandpower_features(epochs.get_data(), raw.info["sfreq"]))
            labels.extend((epochs.events[:, 2] != mapping["T0"]).astype(int))
            groups.extend([subject] * len(epochs))
    x, y, groups = np.concatenate(features), np.asarray(labels), np.asarray(groups)
    # Require both classes and enough examples for three within-person folds.
    eligible = [s for s in np.unique(groups) if min(np.bincount(y[groups == s], minlength=2)) >= 3]
    keep = np.isin(groups, eligible)
    result = evaluate(x[keep], y[keep], groups[keep])
    result.update(
        {
            "runs": runs,
            "subjects": list(map(int, eligible)),
            "epochs": int(keep.sum()),
            "class_counts": np.bincount(y[keep], minlength=2).tolist(),
            "seed": 42,
            "bootstrap_replicates": 2000,
        }
    )
    (output / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    fig, ax = plt.subplots(figsize=(6, 4))
    for i, key in enumerate(("within_subject", "held_out")):
        item = result[key]
        ax.errorbar(
            i,
            item["mean"],
            yerr=[[item["mean"] - item["ci"][0]], [item["ci"][1] - item["mean"]]],
            fmt="o",
            capsize=5,
        )
    ax.set(
        xticks=[0, 1],
        xticklabels=["Within person", "Held-out person"],
        ylabel="Balanced accuracy",
        ylim=(0, 1),
        title="95% bootstrap intervals over people",
    )
    fig.tight_layout()
    fig.savefig(output / "comparison.png", dpi=150)
    plt.close(fig)
    text = f"""# Rest and imagined movement: methods and results

I screened {len(runs)} public EEGBCI imagery runs from {len(subjects)} people using the existing recording quality rules. Runs marked not usable were excluded. The analysis retained {len(eligible)} people and {int(keep.sum())} epochs (rest: {result["class_counts"][0]}, imagery: {result["class_counts"][1]}). See results.json for each run's decision and source SHA-256.

I filtered each retained recording from 8 to 30 Hz, then extracted 0.5 to 2.5 seconds after each T0 (rest), T1 or T2 (imagery) annotation. Welch power in 8-13 and 13-30 Hz for every channel was log transformed. A standard scaler and regularized logistic regression were fitted inside each training fold. Within-person scores use three stratified folds for each person; held-out scores train on all other people. I report balanced accuracy (the average of the two class recalls), averaged equally across people. The 95% percentile intervals resample people 2,000 times with seed 42; the difference uses paired resampling.

Within-person: {result["within_subject"]["mean"]:.3f} (95% interval {result["within_subject"]["ci"][0]:.3f} to {result["within_subject"]["ci"][1]:.3f}). Held-out: {result["held_out"]["mean"]:.3f} (95% interval {result["held_out"]["ci"][0]:.3f} to {result["held_out"]["ci"][1]:.3f}). Difference: {result["difference"]["mean"]:.3f} (95% interval {result["difference"]["ci"][0]:.3f} to {result["difference"]["ci"][1]:.3f}).

The comparison changes both training population and training size, so the difference is not a pure estimate of leakage. Epochs from the same run can share noise and context. Filtering a whole run before splitting can also share information across nearby epochs. The quality rules are not expert labels; exclusion may bias the sample. These public recordings are not representative of every device or person. This is research, not a diagnostic tool.
"""
    (output / "methods-results.md").write_text(text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--subjects", type=int, nargs="+", default=list(range(1, 21)))
    parser.add_argument("--data-dir", default="data/imagery")
    parser.add_argument("--output", default="reports/imagery")
    args = parser.parse_args()
    run(args.subjects, args.data_dir, args.output)


if __name__ == "__main__":
    main()
