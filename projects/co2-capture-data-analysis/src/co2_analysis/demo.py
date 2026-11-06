"""Seeded synthetic measurements, never presented as experimental results."""

import csv
import json
from pathlib import Path

import numpy as np


def _write(path, header, rows):
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def generate_demo(folder, seed=42):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    rng = np.random.default_rng(seed)
    t = np.arange(0, 1201, 2, dtype=float)
    inlet, center, width = 10000.0, 600.0, 60.0
    ratio = 1 / (1 + np.exp(-(t - center) / width))
    outlet = inlet * ratio + rng.normal(0, 0.003 * inlet, len(t))
    flow = 100 * (1 + rng.normal(0, 0.005, len(t)))
    _write(
        folder / "adsorption.csv",
        ["time_s", "outlet_ppm", "flow_ml_min"],
        zip(t, outlet, flow, strict=True),
    )
    cc_rows, cv_rows = [], []
    for cycle, scale in [(1, 1.0), (2, 0.8), (3, 0.8)]:
        duration = 100 * scale
        charge_t = np.linspace(0, duration, 101)
        discharge_t = np.linspace(duration, 2 * duration, 101)
        for phase, times, voltages, sign in [
            ("charge", charge_t, np.linspace(0, 1, 101), 1),
            ("discharge", discharge_t, np.linspace(1, 0, 101), -1),
        ]:
            for i, (time, voltage) in enumerate(zip(times, voltages, strict=True)):
                if cycle == 3 and phase == "discharge" and i > 30:
                    break
                cc_rows.append(
                    [cycle, time, sign * 0.1 * (1 + rng.normal(0, 0.002)), voltage, phase]
                )
        cv_time = np.arange(101, dtype=float)
        voltage = 1 - np.abs(cv_time - 50) / 50
        current = np.where(cv_time < 50, 0.2, -0.2) * scale
        current[50] = 0
        current += rng.normal(0, 0.0004, len(current))
        stop = 70 if cycle == 3 else len(cv_time)
        cv_rows.extend(
            zip([cycle] * stop, cv_time[:stop], current[:stop], voltage[:stop], strict=True)
        )
    _write(folder / "cycling.csv", ["cycle", "time_s", "current_a", "voltage_v", "phase"], cc_rows)
    _write(folder / "cv.csv", ["cycle", "time_s", "current_a", "voltage_v"], cv_rows)
    runs = [
        {
            "id": "adsorption",
            "kind": "breakthrough",
            "file": "adsorption.csv",
            "options": {"inlet_ppm": inlet, "mass_g": 0.5, "bed_length_cm": 10, "max_gap_s": 5},
        },
        *[
            {
                "id": kind,
                "kind": kind,
                "file": f"{kind}.csv",
                "options": {"voltage_min_v": 0, "voltage_max_v": 1, "mass_g": 0.1, "max_gap_s": 2},
            }
            for kind in ["cycling", "cv"]
        ],
    ]
    (folder / "manifest.json").write_text(json.dumps({"runs": runs}, indent=2) + "\n")
    truth = {
        "seed": seed,
        "synthetic": True,
        "breakthrough": {
            "t05_s": center + width * np.log(0.05 / 0.95),
            "t50_s": center,
            "t95_s": center + width * np.log(0.95 / 0.05),
            "captured_mmol_noiseless": 100
            * inlet
            / 60
            / 1e6
            * 101.325
            / (8.314462618 * 298.15)
            * center,
        },
        "cycling": {
            "cycle_1_charge_mah_noiseless": 0.1 * 100 / 3.6,
            "cycle_2_retention_pct_noiseless": 80,
            "cycle_3_incomplete": True,
        },
        "noise": {
            "outlet_ppm_sd": 30,
            "flow_relative_sd": 0.005,
            "cycling_current_relative_sd": 0.002,
            "cv_current_a_sd": 0.0004,
            "distribution": "independent zero-mean Gaussian, no clipping",
        },
    }
    (folder / "truth.json").write_text(json.dumps(truth, indent=2) + "\n")
    return folder / "manifest.json"
