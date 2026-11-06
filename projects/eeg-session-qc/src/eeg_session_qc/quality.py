"""Conservative, explainable screening rules; not clinical artifact labels."""

from collections import Counter

import mne
import numpy as np
from scipy.signal import butter, sosfiltfilt

KINDS = ("flat", "noisy", "line", "blink", "muscle")
THRESHOLDS = {
    "window_seconds": 2,
    "flat_ptp_uv": 0.5,
    "flat_constant_seconds": 0.5,
    "flat_step_uv": 0.01,
    "noisy_sd_uv": 80,
    "noisy_relative_sd": 5,
    "noisy_ptp_uv": 500,
    "line_peak_to_flanks": 8,
    "line_power_fraction": 0.10,
    "blink_lowpass_ptp_uv": 120,
    "muscle_band_ratio": 0.7,
    "muscle_rms_uv": 8,
    "reject_bad_channel_fraction": 0.2,
    "reject_artifact_time_fraction": 0.5,
}


def _flat(x, sfreq, rules):
    constant = np.abs(np.diff(x)) < rules["flat_step_uv"]
    edges = np.diff(np.r_[False, constant, False].astype(int))
    runs = np.flatnonzero(edges == -1) - np.flatnonzero(edges == 1)
    return bool(
        np.ptp(x) < rules["flat_ptp_uv"]
        or (len(runs) and (max(runs) + 1) / sfreq >= rules["flat_constant_seconds"])
    )


def analyze(raw, session="session", line_hz=60):
    """Return JSON-safe window/channel evidence without filtering or changing raw."""
    rules = THRESHOLDS.copy()
    if line_hz not in (50, 60):
        raise ValueError("line_hz must be 50 or 60")
    eeg = raw.copy().pick("eeg", exclude=[])
    sfreq = float(eeg.info["sfreq"])
    if sfreq / 2 <= line_hz + 5:
        raise ValueError("Sampling rate must resolve mains frequency plus 5 Hz of flanks")
    data = eeg.get_data() * 1e6
    if len(data) < 2 or data.shape[1] / sfreq < 2:
        raise ValueError("Need at least two EEG channels and two seconds")
    if not np.isfinite(data).all():
        raise ValueError("EEG must contain only finite samples")
    names = eeg.ch_names
    front = [i for i, n in enumerate(names) if n.rstrip(".").lower() in ("fp1", "fp2", "fpz")]
    windows = []
    channel_hits = Counter()
    bad_cells = artifact_seconds = 0.0
    chunks = np.array_split(
        np.arange(data.shape[1]), int(np.ceil(data.shape[1] / (rules["window_seconds"] * sfreq)))
    )
    for indices in chunks:
        x = data[:, indices]
        seconds = len(indices) / sfreq
        sd = np.std(x, axis=1)
        flags = {kind: [] for kind in KINDS}
        flat = np.array([_flat(row, sfreq, rules) for row in x])
        normal = sd[~flat]
        reference = float(np.median(normal)) if len(normal) else 0
        noisy = (~flat) & (
            (sd > max(rules["noisy_sd_uv"], rules["noisy_relative_sd"] * reference))
            | (np.ptp(x, axis=1) > rules["noisy_ptp_uv"])
        )
        flags["flat"] = [names[i] for i in np.flatnonzero(flat)]
        flags["noisy"] = [names[i] for i in np.flatnonzero(noisy)]
        eligible = ~(flat | noisy)
        psd, freq = mne.time_frequency.psd_array_welch(
            x, sfreq, n_fft=len(indices), n_per_seg=len(indices), n_overlap=0, verbose=False
        )

        def power(lo, hi, psd=psd, freq=freq):
            return psd[:, (freq >= lo) & (freq <= hi)].sum(axis=1) * (freq[1] - freq[0])

        total = power(1, sfreq / 2)
        mains = power(line_hz - 1, line_hz + 1)
        flank_mask = ((freq >= line_hz - 5) & (freq <= line_hz - 2)) | (
            (freq >= line_hz + 2) & (freq <= line_hz + 5)
        )
        peak_mask = (freq >= line_hz - 1) & (freq <= line_hz + 1)
        line_ratio = psd[:, peak_mask].mean(axis=1) / np.maximum(
            psd[:, flank_mask].mean(axis=1), 1e-20
        )
        line_fraction = mains / np.maximum(total, 1e-20)
        line = (
            eligible
            & (line_ratio > rules["line_peak_to_flanks"])
            & (line_fraction > rules["line_power_fraction"])
        )
        flags["line"] = [names[i] for i in np.flatnonzero(line)]
        muscle_rms = np.sqrt(power(30, 45))
        muscle_ratio = power(30, 45) / np.maximum(power(4, 25), 1e-20)
        muscle = (
            eligible
            & (muscle_ratio > rules["muscle_band_ratio"])
            & (muscle_rms > rules["muscle_rms_uv"])
        )
        flags["muscle"] = [names[i] for i in np.flatnonzero(muscle)]
        slow = sosfiltfilt(butter(2, 5, fs=sfreq, output="sos"), x, axis=1)
        slow_ptp = np.ptp(slow, axis=1)
        flags["blink"] = [
            names[i] for i in front if eligible[i] and slow_ptp[i] > rules["blink_lowpass_ptp_uv"]
        ]
        channel_hits.update(set(flags["flat"] + flags["noisy"]))
        bad_cells += seconds * int((flat | noisy).sum())
        if any(flags[k] for k in ("line", "blink", "muscle")):
            artifact_seconds += seconds
        windows.append(
            {
                "start": float(indices[0] / sfreq),
                "stop": float((indices[-1] + 1) / sfreq),
                "flags": flags,
                "metrics": {
                    name: {
                        "sd_uv": float(sd[i]),
                        "ptp_uv": float(np.ptp(x[i])),
                        "line_ratio": float(line_ratio[i]),
                        "line_fraction": float(line_fraction[i]),
                        "slow_ptp_uv": float(slow_ptp[i]),
                        "muscle_ratio": float(muscle_ratio[i]),
                        "muscle_rms_uv": float(muscle_rms[i]),
                    }
                    for i, name in enumerate(names)
                },
            }
        )
    duration = data.shape[1] / sfreq
    bad_fraction = bad_cells / (duration * len(names))
    artifact_fraction = artifact_seconds / duration
    counts = {k: sum(bool(w["flags"][k]) for w in windows) for k in KINDS}
    reasons = [
        f"{k}: flagged in {v} of {len(windows)} time windows" for k, v in counts.items() if v
    ]
    if not front:
        reasons.append("Blink screening not assessed: no Fp1, Fp2 or Fpz channel")
    if eeg.info["bads"]:
        reasons.append(
            "Previously marked bad channels included in screening: " + ", ".join(eeg.info["bads"])
        )
    status = "usable with caveats" if reasons else "usable"
    if (
        bad_fraction >= rules["reject_bad_channel_fraction"]
        or artifact_fraction >= rules["reject_artifact_time_fraction"]
    ):
        status = "not usable"
        reasons.append(
            f"At least {rules['reject_bad_channel_fraction']:.0%} of channel-time is flat/noisy "
            f"or {rules['reject_artifact_time_fraction']:.0%} of time has artifact flags"
        )
    return {
        "schema_version": 1,
        "session": session,
        "status": status,
        "score": round(100 * (1 - bad_fraction) * (1 - artifact_fraction), 1),
        "duration_seconds": duration,
        "sfreq": sfreq,
        "channels": names,
        "line_hz": line_hz,
        "counts": counts,
        "windows": windows,
        "bad_channel_time_fraction": bad_fraction,
        "artifact_time_fraction": artifact_fraction,
        "flagged_channels": dict(channel_hits),
        "preexisting_bads": list(eeg.info["bads"]),
        "thresholds": rules,
        "reasons": reasons or ["No screening thresholds crossed"],
        "disclaimer": "Research screening only. Not a diagnostic tool. A usable label is not a guarantee.",
    }
