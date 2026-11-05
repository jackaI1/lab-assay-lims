"""Endpoint assay calculations, deliberately independent of database and web UI."""

import warnings
from collections import defaultdict

import numpy as np
from scipy.optimize import OptimizeWarning, curve_fit

VERSION = "1.0"


def logistic(x, low, high, ec50, hill):
    return low + (high - low) / (1 + (np.asarray(x) / ec50) ** hill)


def predict(fit, x):
    x = np.asarray(x)
    if fit["model"] == "linear":
        return fit["parameters"]["slope"] * x + fit["parameters"]["intercept"]
    return logistic(x, **fit["parameters"])


def fit_curve(x, y, model):
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    if len(x) != len(y) or not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
        raise ValueError("Standards must contain paired finite numbers")
    if np.any(x < 0) or len(x) < 3 or np.ptp(y) < 1e-10:
        raise ValueError("Standards must span concentrations and signals")
    if model == "linear":
        if len(np.unique(x)) < 3:
            raise ValueError("Linear fit needs at least three distinct concentrations")
        slope, intercept = np.polyfit(x, y, 1)
        if abs(slope) < 1e-10:
            raise ValueError("Standard curve has no usable slope")
        parameters = dict(slope=float(slope), intercept=float(intercept))
    elif model == "4pl":
        if len(np.unique(x)) < 6:
            raise ValueError("4PL needs at least six distinct concentrations")
        order = np.argsort(x)
        best = None
        scale = max(float(np.ptp(y)), 1e-5)
        positive = x[x > 0]
        if len(positive) < 5:
            raise ValueError("4PL needs at least five positive concentrations")
        bounds = (
            [min(y) - 2 * scale, min(y) - 2 * scale, min(positive) / 100, 0.05],
            [max(y) + 2 * scale, max(y) + 2 * scale, max(x) * 100, 10],
        )
        for midpoint in np.quantile(positive, [0.25, 0.5, 0.75]):
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("error", OptimizeWarning)
                    params, _ = curve_fit(
                        logistic,
                        x,
                        y,
                        p0=[y[order[-1]], y[order[0]], midpoint, 1],
                        bounds=bounds,
                        maxfev=30000,
                    )
                error = float(np.sum((logistic(x, *params) - y) ** 2))
                if best is None or error < best[0]:
                    best = (error, params)
            except (RuntimeError, ValueError, OptimizeWarning):
                continue
        if best is None:
            raise ValueError("4PL did not converge; check the standards")
        parameters = dict(zip(["low", "high", "ec50", "hill"], map(float, best[1]), strict=True))
    else:
        raise ValueError("Model must be linear or 4pl")
    fit = dict(model=model, parameters=parameters, concentration_range=[float(min(x)), float(max(x))])
    fitted = predict(fit, x)
    ss_res = float(np.sum((fitted - y) ** 2))
    fit.update(
        r_squared=1 - ss_res / float(np.sum((y - np.mean(y)) ** 2)),
        rmse=float(np.sqrt(ss_res / len(x))),
        standards=[dict(concentration=float(a), signal=float(b)) for a, b in zip(x, y, strict=True)],
    )
    return fit


def invert(fit, signal):
    """Never extrapolate beyond the measured concentration interval."""
    limits = predict(fit, fit["concentration_range"])
    if not np.isfinite(signal) or signal < min(limits) - 1e-12 or signal > max(limits) + 1e-12:
        return None
    if fit["model"] == "linear":
        p = fit["parameters"]
        value = (signal - p["intercept"]) / p["slope"]
    else:
        p = fit["parameters"]
        if abs(signal - p["low"]) < 1e-12:
            return None
        ratio = (p["high"] - p["low"]) / (signal - p["low"]) - 1
        if ratio < 0:
            return None
        try:
            value = p["ec50"] * ratio ** (1 / p["hill"])
        except OverflowError:
            return None
    lo, hi = fit["concentration_range"]
    if not np.isfinite(value) or value < lo - 1e-8 or value > hi + 1e-8:
        return None
    return float(max(lo, min(hi, value)))


def cv(values):
    if len(values) < 2 or abs(np.mean(values)) < 1e-12:
        return None
    return float(100 * np.std(values, ddof=1) / abs(np.mean(values)))


def analyse(mapping, signals, model="4pl"):
    if set(signals) != {w["well"] for w in mapping}:
        raise ValueError("Imported wells must exactly match the saved plate map")
    by_role = defaultdict(list)
    for w in mapping:
        by_role[w["role"]].append(signals[w["well"]])
    if len(by_role["blank"]) < 2:
        raise ValueError("At least two blank wells are required")
    blank = float(np.mean(by_role["blank"]))
    standards = [w for w in mapping if w["role"] == "standard"]
    fit = fit_curve(
        [w["concentration"] for w in standards], [signals[w["well"]] - blank for w in standards], model
    )
    flags = []
    if fit["r_squared"] < 0.98:
        flags.append("POOR_CURVE_FIT")
    z = None
    if len(by_role["positive"]) < 3 or len(by_role["negative"]) < 3:
        flags.append("INSUFFICIENT_CONTROLS")
    else:
        pos, neg = by_role["positive"], by_role["negative"]
        gap = abs(np.mean(pos) - np.mean(neg))
        if gap < 1e-12:
            flags.append("INDISTINGUISHABLE_CONTROLS")
        else:
            z = float(1 - 3 * (np.std(pos, ddof=1) + np.std(neg, ddof=1)) / gap)
            if z < 0.5:
                flags.append("Z_PRIME_FAIL")
    wells = {}
    buckets = defaultdict(list)
    for w in mapping:
        address = w["well"]
        corrected = signals[address] - blank
        concentration = None
        well_flags = []
        if w["role"] == "standard":
            concentration = w["concentration"]
            expected = float(predict(fit, [concentration])[0])
            span = max(s["signal"] for s in fit["standards"]) - min(s["signal"] for s in fit["standards"])
            if abs(corrected - expected) > max(0.02 * span, 0.2 * abs(expected)):
                well_flags.append("STANDARD_RESIDUAL_FAIL")
        elif w["role"] == "sample":
            concentration = invert(fit, corrected)
            if concentration is None:
                well_flags.append("OUT_OF_RANGE")
            else:
                concentration *= w.get("dilution_factor", 1)
        if w["role"] == "standard":
            key = f"standard:{w['concentration']:g}"
        elif w["role"] == "sample":
            key = f"sample:{w['sample_id']}"
        else:
            key = w["role"]
        wells[address] = dict(
            raw=signals[address], corrected=float(corrected), concentration=concentration, flags=well_flags
        )
        buckets[key].append(address)
    groups = []
    for key, addresses in buckets.items():
        values = [wells[a]["corrected"] for a in addresses]
        concentrations = [wells[a]["concentration"] for a in addresses]
        # Concentration CV for samples, signal CV for standards and controls.
        if key.startswith("sample:"):
            variation = cv(concentrations) if all(c is not None for c in concentrations) else None
        else:
            variation = cv(values)
        group_flags = []
        if key.startswith("sample:") and len(addresses) < 2:
            group_flags.append("INSUFFICIENT_REPLICATES")
        if key.startswith(("sample:", "standard:")) and variation is not None and variation > 20:
            group_flags.append("HIGH_CV")
        groups.append(
            dict(
                key=key,
                wells=addresses,
                n=len(addresses),
                cv_percent=variation,
                concentration=float(np.mean(concentrations))
                if all(c is not None for c in concentrations)
                else None,
                flags=group_flags,
            )
        )
    any_fail = flags or any(w["flags"] for w in wells.values()) or any(g["flags"] for g in groups)
    return dict(
        version=VERSION,
        model=model,
        blank_mean=blank,
        fit=fit,
        z_prime=z,
        flags=flags,
        groups=groups,
        wells=wells,
        passed=not bool(any_fail),
        thresholds=dict(min_r_squared=0.98, max_cv_percent=20, min_z_prime=0.5),
    )
