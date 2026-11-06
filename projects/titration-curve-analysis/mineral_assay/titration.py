"""Equivalence point estimation and stoichiometric concentration calculations."""
from dataclasses import dataclass
import csv
import numpy as np
from scipy.signal import savgol_filter
from scipy.optimize import brentq

@dataclass
class Curve:
    volume: np.ndarray  # mL titrant added
    signal: np.ndarray  # pH or potential in mV
    kind: str = "ph"

    def __post_init__(self):
        self.volume = np.asarray(self.volume, dtype=float)
        self.signal = np.asarray(self.signal, dtype=float)
        if (self.kind not in ("ph", "potential") or len(self.volume) != len(self.signal)
                or len(self.volume) < 7 or not np.all(np.isfinite(self.volume))
                or not np.all(np.isfinite(self.signal)) or np.any(np.diff(self.volume) <= 0)
                or self.volume[0] < 0):
            raise ValueError("Need at least seven finite readings at strictly increasing non-negative volumes and kind ph or potential")

    @classmethod
    def csv(cls, path, kind="ph"):
        with open(path, newline="") as f:
            rows = list(csv.DictReader(f))
        key = "ph" if kind == "ph" else "potential_mv"
        return cls([float(r["volume_ml"]) for r in rows], [float(r[key]) for r in rows], kind)


def derivatives(curve, window=11, polyorder=3):
    if window % 2 != 1 or window > len(curve.volume) or window <= polyorder or polyorder < 2:
        raise ValueError("window must be odd, fit the data, and exceed polyorder >= 2")
    # Interpolate onto a uniform grid before smoothing, so unevenly spaced additions work.
    v = np.linspace(curve.volume[0], curve.volume[-1], len(curve.volume))
    smooth = savgol_filter(np.interp(v, curve.volume, curve.signal), window, polyorder)
    first = np.gradient(smooth, v)
    second = np.gradient(first, v)
    return v, smooth, first, second


def equivalence(curve, method="first", window=11, search=None):
    v, _, d1, d2 = derivatives(curve, window)
    # Exclude smoothing boundaries and optionally restrict the expected endpoint region.
    mask = np.zeros(len(v), dtype=bool)
    mask[window // 2:len(v)-window // 2] = True
    if search is not None:
        mask &= (v >= search[0]) & (v <= search[1])
    candidates = np.flatnonzero(mask)
    if not len(candidates):
        raise ValueError("No interior points in endpoint search range")
    peak = candidates[np.argmax(np.abs(d1[candidates]))]
    if method == "first":
        return float(v[peak])
    if method != "second":
        raise ValueError("method must be first or second")
    crossings = []
    for i in candidates[:-1]:
        if mask[i+1] and d2[i] * d2[i+1] <= 0 and d2[i] != d2[i+1]:
            x = v[i] - d2[i] * (v[i+1]-v[i]) / (d2[i+1]-d2[i])
            crossings.append(x)
    if not crossings:
        raise ValueError("No second derivative zero crossing in search range")
    return float(min(crossings, key=lambda x: abs(x-v[peak])))


def gran(curve, sample_volume_ml, fit_range, model="strong_acid"):
    """Pre-equivalence Gran extrapolation for acid titrated with strong base.

    fit_range is chosen by the user in the approximately linear pre-endpoint region.
    For a weak acid use V*10^-pH; for a strong acid use (V0+V)*10^-pH.
    """
    if curve.kind != "ph" or sample_volume_ml <= 0 or model not in ("strong_acid", "weak_acid"):
        raise ValueError("Gran requires pH, positive sample volume and a supported acid model")
    v = curve.volume
    mask = (v >= fit_range[0]) & (v <= fit_range[1])
    if mask.sum() < 3:
        raise ValueError("Gran fit range needs at least three points")
    y = (sample_volume_ml + v if model == "strong_acid" else v) * 10 ** (-curve.signal)
    slope, intercept = np.polyfit(v[mask], y[mask], 1)
    if slope >= 0:
        raise ValueError("Gran line must have a negative slope")
    endpoint = -intercept / slope
    if endpoint <= v[mask].max():
        raise ValueError("Gran intercept must lie beyond the fitted range")
    return float(endpoint)


def concentration(endpoint_ml, titrant_mol_l, sample_ml, analyte_per_titrant=1.0,
                  initial_reagent_mol=None):
    """Direct titration, or back titration if initial reagent moles are supplied.

    analyte_per_titrant is the mole ratio of analyte to reacted reagent; back
    titrant and excess reagent are assumed to react 1:1.
    """
    if min(endpoint_ml, titrant_mol_l, sample_ml, analyte_per_titrant) <= 0:
        raise ValueError("Volumes, concentration and mole ratio must be positive")
    measured = endpoint_ml * titrant_mol_l / 1000
    reacted = measured if initial_reagent_mol is None else initial_reagent_mol - measured
    if reacted <= 0:
        raise ValueError("Back titration exceeds the initial reagent amount")
    return reacted * analyte_per_titrant / (sample_ml / 1000)


def replicate_summary(values):
    a = np.asarray(values, dtype=float)
    if len(a) < 2 or not np.all(np.isfinite(a)):
        raise ValueError("At least two finite replicate results are required")
    sd = float(np.std(a, ddof=1))
    return {"n": len(a), "mean": float(np.mean(a)), "sd": sd, "standard_error": sd / np.sqrt(len(a))}
