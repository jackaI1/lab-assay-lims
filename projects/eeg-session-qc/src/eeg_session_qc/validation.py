"""Paired injection experiments on low-amplitude public EEG reference segments."""

import numpy as np

from .quality import KINDS, analyze

LEVELS = (0.6, 1.0, 1.4)


def inject(raw, kind, level=1.0, seed=42, line_hz=60):
    if kind not in KINDS:
        raise ValueError("Unknown artifact")
    out = raw.copy().load_data()
    names = [n.rstrip(".").lower() for n in raw.ch_names]
    front = [i for i, n in enumerate(names) if n in ("fp1", "fp2", "fpz")]
    temporal = [i for i, n in enumerate(names) if n in ("t7", "t8", "t9", "t10")]
    targets = front[:2] if kind == "blink" else temporal[:2] if kind == "muscle" else [0]
    if not targets:
        raise ValueError(f"Missing target sensors for {kind}")
    sfreq = float(raw.info["sfreq"])
    a, b = int(2 * sfreq), int(4 * sfreq)
    if out.n_times < b:
        raise ValueError("Injection requires at least four seconds")
    t = np.arange(b - a) / sfreq
    rng = np.random.default_rng(seed)
    for i in targets:
        if kind == "flat":
            # Level changes dropout length, not amplitude. Always at least 0.5 s.
            out._data[i, a : a + int(min(2, level) * sfreq)] = 0
        elif kind == "noisy":
            out._data[i, a:b] += rng.normal(0, level * 120e-6, b - a)
        elif kind == "line":
            out._data[i, a:b] += level * 35e-6 * np.sin(2 * np.pi * line_hz * t)
        elif kind == "blink":
            out._data[i, a:b] += level * 180e-6 * np.exp(-(((t - 1) / 0.12) ** 2))
        else:
            # Band-limited random interference, tapered to model a brief tension burst.
            noise = rng.normal(size=b - a)
            frequencies = np.fft.rfftfreq(b - a, 1 / sfreq)
            spectrum = np.fft.rfft(noise)
            spectrum[(frequencies < 30) | (frequencies > 45)] = 0
            burst = np.fft.irfft(spectrum, n=b - a)
            burst = burst / np.std(burst) * np.hanning(b - a)
            out._data[i, a:b] += level * 25e-6 * burst
    return out, [raw.ch_names[i] for i in targets]


def validate(recordings, seed=42, line_hz=60):
    trials, controls, selected = [], [], []
    candidates = rejected = 0
    reference_details = []
    for session, raw in recordings:
        eeg = raw.copy().pick("eeg", exclude=[])
        sfreq = float(eeg.info["sfreq"])
        # Fixed non-overlapping segments; independent amplitude-only reference screen.
        for start in range(0, eeg.n_times - int(8 * sfreq) + 1, int(8 * sfreq)):
            candidates += 1
            segment = eeg.copy().crop(start / sfreq, (start + int(8 * sfreq) - 1) / sfreq)
            uv = segment.get_data() * 1e6
            std = np.std(uv, axis=1)
            quiet = (std > 2) & (std < 40) & (np.ptp(uv, axis=1) < 180)
            retained = [name for name, ok in zip(segment.ch_names, quiet, strict=True) if ok]
            excluded = [name for name, ok in zip(segment.ch_names, quiet, strict=True) if not ok]
            normalized = [name.rstrip(".").lower() for name in retained]
            has_front = any(n in ("fp1", "fp2", "fpz") for n in normalized)
            has_temporal = any(n in ("t7", "t8", "t9", "t10") for n in normalized)
            if len(retained) < 4 or not has_front or not has_temporal:
                rejected += 1
                continue
            segment.pick(retained)
            control = analyze(segment, session, line_hz)
            # Controls are retained even when the artifact detector flags them.
            ref_id = f"{session}@{start / sfreq:g}s"
            selected.append(ref_id)
            reference_details.append(
                {"reference": ref_id, "channels": retained, "excluded_channels": excluded}
            )
            controls.append({"reference": ref_id, "counts": control["counts"]})
            for kind in KINDS:
                for level in LEVELS:
                    trial_seed = seed + len(trials)
                    injected, targets = inject(segment, kind, level, trial_seed, line_hz)
                    result = analyze(injected, ref_id, line_hz)

                    def target_hit(r, targets=targets, kind=kind):
                        return any(
                            set(targets) & set(w["flags"][kind])
                            for w in r["windows"]
                            if w["start"] < 4 and w["stop"] > 2
                        )

                    detected = target_hit(result)
                    preexisting = target_hit(control)
                    trials.append(
                        {
                            "reference": ref_id,
                            "kind": kind,
                            "level": level,
                            "seed": trial_seed,
                            "targets": targets,
                            "start": 2,
                            "stop": 4,
                            "detected": detected,
                            "control_target_flagged": preexisting,
                            "new_detection": detected and not preexisting,
                        }
                    )
    if not selected:
        raise ValueError("No eligible reference segments; no validation numbers produced")
    summary = {}
    for kind in KINDS:
        rows = [r for r in trials if r["kind"] == kind]
        clean_target = [r for r in rows if not r["control_target_flagged"]]
        n = sum(r["detected"] for r in rows)
        summary[kind] = {
            "trials": len(rows),
            "detected": n,
            "detection_rate": n / len(rows),
            "unflagged_control_trials": len(clean_target),
            "new_detections": sum(r["new_detection"] for r in clean_target),
            "new_detection_rate": (
                sum(r["new_detection"] for r in clean_target) / len(clean_target)
                if clean_target
                else None
            ),
            "untreated_segments_flagged": sum(bool(c["counts"][kind]) for c in controls),
            "by_level": {
                str(level): {
                    "trials": sum(r["level"] == level for r in rows),
                    "detected": sum(r["detected"] and r["level"] == level for r in rows),
                }
                for level in LEVELS
            },
        }
    return {
        "seed": seed,
        "reference_segments": len(selected),
        "candidate_segments": candidates,
        "rejected_segments": rejected,
        "references": selected,
        "reference_details": reference_details,
        "summary": summary,
        "controls": controls,
        "trials": trials,
        "method": "Non-overlapping 8 s segments: retain sensors with SD >2 and <40 uV, peak-to-peak <180 uV; require at least four including forehead and temporal sensors. "
        "Low-amplitude references, not independently certified artifact-free. Injection at 2-4 s. "
        "Detection requires correct artifact, target channel and overlapping time window. "
        "Untreated flags are background flag rates, not verified false positives. "
        "Paired new-detection rates exclude already-flagged targets. No clinical accuracy claim.",
    }
