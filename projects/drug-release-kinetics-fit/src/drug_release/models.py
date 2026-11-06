"""Fraction released, zero intercept, known total load. Time units are caller supplied."""

import numpy as np
from scipy.optimize import least_squares

MODELS = {
    "zero_order": ("k",),
    "first_order": ("k",),
    "higuchi": ("k",),
    "korsmeyer_peppas": ("k", "n"),
    "weibull": ("tau", "beta"),
}


def predict(name, time, parameters):
    t = np.asarray(time, dtype=float)
    if np.any(~np.isfinite(t)) or np.any(t < 0):
        raise ValueError("Prediction times must be finite and nonnegative")
    p = np.asarray(parameters, dtype=float)
    if name not in MODELS or len(p) != len(MODELS[name]) or np.any(p <= 0):
        raise ValueError("Unknown model or invalid positive parameters")
    if not np.all(np.isfinite(p)):
        raise ValueError("Parameters must be finite")
    if name == "zero_order":
        return p[0] * t
    if name == "first_order":
        return -np.expm1(-p[0] * t)
    if name == "higuchi":
        return p[0] * np.sqrt(t)
    if name == "korsmeyer_peppas":
        return p[0] * t ** p[1]
    return -np.expm1(-((t / p[0]) ** p[1]))


def fit(name, time, fraction):
    """Fit original fraction scale, with multistart log-parameter least squares.

    Internal unit time scaling improves stability; returned parameters use input units.
    This low-level optimizer also accepts unbounded residual-bootstrap pseudo responses.
    Range validation and Peppas masking belong to analyze().
    """
    t, y = np.asarray(time, dtype=float), np.asarray(fraction, dtype=float)
    if name not in MODELS:
        raise ValueError("Unknown model")
    if (
        t.ndim != 1
        or t.shape != y.shape
        or len(t) < len(MODELS[name]) + 1
        or np.any(t <= 0)
        or not np.all(np.isfinite(t))
        or not np.all(np.isfinite(y))
    ):
        raise ValueError("Fit needs finite paired positive times and sufficient points")
    scale = t.max()
    u = t / scale
    response_scale = max(float(np.max(np.abs(y))), 1e-12)
    starts = [[0.5]] if len(MODELS[name]) == 1 else [[0.5, b] for b in [0.5, 1.0, 2.0]]
    low = [-28.0] * len(starts[0])
    high = [28.0] * len(starts[0])
    if len(low) == 2:
        low[1], high[1] = np.log(0.05), np.log(5.0)
    candidates = []
    for start in starts:
        result = least_squares(
            lambda z: (predict(name, u, np.exp(z)) - y) / response_scale,
            np.log(start),
            bounds=(low, high),
            max_nfev=1000,
            ftol=1e-10,
            xtol=1e-10,
            gtol=1e-10,
        )
        if result.success and np.all(np.isfinite(result.x)):
            candidates.append(result)
    if not candidates:
        raise ValueError("Optimizer failed to converge")
    p = np.exp(min(candidates, key=lambda r: np.sum(r.fun**2)).x)
    if name in ("zero_order", "first_order"):
        p[0] /= scale
    elif name == "higuchi":
        p[0] /= np.sqrt(scale)
    elif name == "korsmeyer_peppas":
        p[0] /= scale ** p[1]
    else:
        p[0] *= scale
    return p
