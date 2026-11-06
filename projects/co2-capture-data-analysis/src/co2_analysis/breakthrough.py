"""Ideal-gas CO2 inventory balance over the measured acquisition window."""

import numpy as np

from .io import integrate, positive, read_csv

R_L_KPA_MOL_K = 8.314462618


def _crossing(t, ratio, threshold, sustain):
    if ratio[0] >= threshold:
        return None
    for i in range(1, len(t) - sustain + 1):
        if ratio[i - 1] < threshold and np.all(ratio[i : i + sustain] >= threshold):
            fraction = (threshold - ratio[i - 1]) / (ratio[i] - ratio[i - 1])
            return float(t[i - 1] + fraction * (t[i] - t[i - 1]))
    return None


def analyze_breakthrough(
    path,
    *,
    inlet_ppm,
    mass_g,
    temperature_k=298.15,
    pressure_kpa=101.325,
    bed_length_cm=None,
    median_window=5,
    sustain_points=3,
    separate_outlet_flow=False,
    max_gap_s=None,
):
    positive(
        inlet_ppm=inlet_ppm, mass_g=mass_g, temperature_k=temperature_k, pressure_kpa=pressure_kpa
    )
    if inlet_ppm > 1e6:
        raise ValueError("inlet_ppm cannot exceed 1000000")
    if bed_length_cm is not None:
        positive(bed_length_cm=bed_length_cm)
    if max_gap_s is not None:
        positive(max_gap_s=max_gap_s)
    if not isinstance(median_window, int) or median_window < 1 or median_window % 2 != 1:
        raise ValueError("median_window must be a positive odd integer")
    if not isinstance(sustain_points, int) or sustain_points < 1:
        raise ValueError("sustain_points must be a positive integer")
    columns = ["time_s", "outlet_ppm", "flow_ml_min"]
    if separate_outlet_flow:
        columns.append("outlet_flow_ml_min")
    data = read_csv(path, columns)
    t, outlet, flow = (data[k] for k in columns[:3])
    if np.any(np.diff(t) <= 0):
        raise ValueError("time_s must be strictly increasing")
    if median_window > len(t) or sustain_points >= len(t):
        raise ValueError("filter and persistence must fit within the run")
    outflow = data.get("outlet_flow_ml_min", flow)
    if np.any(flow <= 0) or np.any(outflow <= 0):
        raise ValueError("flows must be positive")
    if np.any(outlet > 1e6):
        raise ValueError("outlet_ppm cannot exceed 1000000")
    ratio = outlet / inlet_ppm
    pad = median_window // 2
    smooth = np.median(
        np.lib.stride_tricks.sliding_window_view(np.pad(ratio, pad, mode="edge"), median_window),
        axis=1,
    )
    times = {
        f"t{int(level * 100):02}_s": _crossing(t, smooth, level, sustain_points)
        for level in (0.05, 0.5, 0.95)
    }
    # mL/min -> L/s; ppm -> mol/mol; mol -> mmol.
    factor = pressure_kpa / (R_L_KPA_MOL_K * temperature_k) / 60 / 1e6
    inlet_rate = flow * inlet_ppm * factor
    outlet_rate = outflow * outlet * factor
    inlet_mmol = integrate(inlet_rate, t)
    outlet_mmol = integrate(outlet_rate, t)
    captured = integrate(inlet_rate - outlet_rate, t)
    flags = []
    if times["t05_s"] is None:
        flags.append("t05_unobserved")
    if times["t95_s"] is None:
        flags.append("saturation_unobserved")
    if smooth[0] >= 0.05:
        flags.append("starts_above_t05")
    if np.any(outlet < 0):
        flags.append("negative_outlet_noise")
    if np.any(outlet > inlet_ppm):
        flags.append("outlet_above_inlet")
    if captured < 0:
        flags.append("negative_net_capture")
    if max_gap_s is not None and np.max(np.diff(t)) > max_gap_s:
        flags.append("sampling_gap")
    mtz = None
    if times["t05_s"] is not None and times["t95_s"] is not None:
        mtz = times["t95_s"] - times["t05_s"]
    length = None
    # Constant-pattern proxy, relative to start of measured feed exposure.
    if mtz is not None and bed_length_cm is not None:
        length = bed_length_cm * mtz / (times["t95_s"] - t[0])
    result = dict(
        **times,
        window_start_s=float(t[0]),
        window_end_s=float(t[-1]),
        inlet_mmol=inlet_mmol,
        outlet_mmol=outlet_mmol,
        captured_mmol=captured,
        capacity_mmol_g=captured / mass_g,
        mtz_width_s=mtz,
        mtz_length_proxy_cm=length,
        mass_balance_residual_mmol=inlet_mmol - outlet_mmol - captured,
        flags=";".join(flags),
    )
    return result, {**data, "ratio": ratio, "threshold_ratio": smooth}
