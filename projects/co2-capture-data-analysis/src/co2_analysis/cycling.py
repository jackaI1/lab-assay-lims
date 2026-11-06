"""Charge/discharge and CV metrics with visible cycle-quality decisions."""

import numpy as np

from .io import integrate, positive, read_csv, signed_charge


def analyze_cycles(
    path,
    *,
    kind,
    voltage_min_v,
    voltage_max_v,
    mass_g=None,
    voltage_tolerance_v=0.02,
    drift_fraction=0.1,
    max_gap_s=None,
):
    if kind not in ("cycling", "cv"):
        raise ValueError("kind must be cycling or cv")
    if not np.isfinite([voltage_min_v, voltage_max_v]).all() or voltage_max_v <= voltage_min_v:
        raise ValueError("voltage_max_v must exceed voltage_min_v; both must be finite")
    positive(voltage_tolerance_v=voltage_tolerance_v, drift_fraction=drift_fraction)
    if mass_g is not None:
        positive(mass_g=mass_g)
    if max_gap_s is not None:
        positive(max_gap_s=max_gap_s)
    columns = ["cycle", "time_s", "current_a", "voltage_v"]
    if kind == "cycling":
        columns.append("phase")
    data = read_csv(path, columns, text_columns=("phase",))
    cycles = data["cycle"]
    if np.any(cycles < 1) or np.any(cycles != np.floor(cycles)) or np.any(np.diff(cycles) < 0):
        raise ValueError("cycle numbers must be positive integers in ascending contiguous blocks")
    if kind == "cycling" and not np.isin(data["phase"], ["charge", "discharge", "rest"]).all():
        raise ValueError("phase must be charge, discharge or rest")
    records = []
    baseline = None
    previous = None
    span = voltage_max_v - voltage_min_v
    for cycle in np.unique(cycles):
        mask = cycles == cycle
        t, current, voltage = (data[k][mask] for k in columns[1:4])
        flags = []
        dt = np.diff(t)
        if np.any(dt < 0):
            raise ValueError(f"cycle {int(cycle)}: time must increase")
        if kind == "cv" and np.any(dt <= 0):
            raise ValueError("CV time must be strictly increasing within each cycle")
        if max_gap_s is not None and len(dt) and max(dt) > max_gap_s:
            flags.append("sampling_gap")
        if previous is not None and cycle != previous + 1:
            flags.append("cycle_number_gap")
        previous = cycle
        complete = True
        if kind == "cycling":
            phases = data["phase"][mask]
            if np.any((dt == 0) & (phases[1:] == phases[:-1])):
                raise ValueError("duplicate times are allowed only at phase boundaries")
            blocks = phases[np.r_[True, phases[1:] != phases[:-1]]]
            active_blocks = blocks[blocks != "rest"].tolist()
            if active_blocks != ["charge", "discharge"]:
                complete = False
            q = {}
            for phase, sign, start, end in [
                ("charge", 1, voltage_min_v, voltage_max_v),
                ("discharge", -1, voltage_max_v, voltage_min_v),
            ]:
                indices = np.flatnonzero(phases == phase)
                q[phase] = None
                if len(indices) < 2 or np.any(np.diff(indices) != 1):
                    complete = False
                    continue
                if np.any(sign * current[indices] < 0):
                    raise ValueError(f"{phase} current has wrong sign in cycle {int(cycle)}")
                q[phase] = sign * integrate(current[indices], t[indices]) / 3.6
                if (
                    abs(voltage[indices[0]] - start) > voltage_tolerance_v
                    or abs(voltage[indices[-1]] - end) > voltage_tolerance_v
                ):
                    complete = False
            charge, discharge = q["charge"], q["discharge"]
        else:
            charge, discharge = signed_charge(t, current)
            # Support a low-high-low or high-low-high sweep, and reject extra reversals.
            low_start = abs(voltage[0] - voltage_min_v) <= voltage_tolerance_v
            high_start = abs(voltage[0] - voltage_max_v) <= voltage_tolerance_v
            turning = int(np.argmax(voltage) if low_start else np.argmin(voltage))
            direction = 1 if low_start else -1
            complete = (
                len(t) >= 3
                and (low_start or high_start)
                and 0 < turning < len(t) - 1
                and abs(voltage[-1] - voltage[0]) <= voltage_tolerance_v
                and abs(np.min(voltage) - voltage_min_v) <= voltage_tolerance_v
                and abs(np.max(voltage) - voltage_max_v) <= voltage_tolerance_v
                and np.all(direction * np.diff(voltage[: turning + 1]) >= 0)
                and np.all(direction * np.diff(voltage[turning:]) <= 0)
            )
        if (
            np.min(voltage) < voltage_min_v - voltage_tolerance_v
            or np.max(voltage) > voltage_max_v + voltage_tolerance_v
        ):
            complete = False
            flags.append("voltage_out_of_range")
        if not complete:
            flags.append("incomplete_cycle")
        valid = complete and not any(f in flags for f in ("sampling_gap", "cycle_number_gap"))
        if charge is None or discharge is None or charge <= 0 or discharge <= 0:
            valid = False
            flags.append("missing_capacity")
        if valid and baseline is None:
            baseline = discharge
        retention = discharge / baseline * 100 if valid and baseline else None
        if retention is not None and abs(retention / 100 - 1) > drift_fraction:
            flags.append("capacity_drift")
        records.append(
            {
                "cycle": int(cycle),
                "charge_mah": charge,
                "discharge_mah": discharge,
                "discharge_mah_g": discharge / mass_g if discharge is not None and mass_g else None,
                "coulombic_efficiency_pct": 100 * discharge / charge if valid else None,
                "retention_pct": retention,
                "complete": bool(complete),
                "voltage_span_v": float(np.ptp(voltage)),
                "voltage_span_fraction": float(np.ptp(voltage) / span),
                "flags": ";".join(flags),
            }
        )
    return records, data
