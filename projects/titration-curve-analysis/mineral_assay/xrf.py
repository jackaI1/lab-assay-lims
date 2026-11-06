"""Fit known X-ray fluorescence lines and calibrate their integrated areas."""
import numpy as np
from scipy.optimize import nnls

# Approximate K-alpha energies in keV, for demonstration; overlapping lines need care.
LINES_KEV = {"Fe": 6.404, "Cu": 8.048, "Zn": 8.638, "Ca": 3.692}

def fit_spectrum(energy, counts, elements, sigma_kev=0.09):
    energy, counts = np.asarray(energy, float), np.asarray(counts, float)
    if len(energy) != len(counts) or len(energy) < 5 or np.any(np.diff(energy) <= 0) or sigma_kev <= 0 or not np.all(np.isfinite(counts)) or np.any(counts < 0):
        raise ValueError("Need increasing energies, nonnegative finite counts and positive width")
    if not elements or any(e not in LINES_KEV or not energy[0] < LINES_KEV[e] < energy[-1] for e in elements) or len(set(elements)) != len(elements):
        raise ValueError("Elements must have distinct known lines within the spectrum")
    # A normalized Gaussian gives integrated area in counts*keV; constant and
    # sloping background are constrained nonnegative at both spectrum ends.
    x = (energy-energy[0])/(energy[-1]-energy[0])
    columns = [np.exp(-0.5*((energy-LINES_KEV[e])/sigma_kev)**2)/(sigma_kev*np.sqrt(2*np.pi)) for e in elements]
    design = np.column_stack(columns + [1-x, x])
    design[design < 1e-14] = 0.0
    coeff, _ = nnls(design, counts)
    return {"areas": dict(zip(elements, map(float, coeff[:len(elements)]))), "fit": design @ coeff}

def calibrate(area, standard_areas, standard_concentrations):
    x, y = np.asarray(standard_areas, float), np.asarray(standard_concentrations, float)
    if len(x) < 2 or len(x) != len(y) or not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)) or np.ptp(x) == 0:
        raise ValueError("Calibration needs at least two distinct finite standards")
    slope, intercept = np.polyfit(x, y, 1)
    if slope <= 0:
        raise ValueError("Calibration slope must be positive")
    return float(slope * area + intercept)
