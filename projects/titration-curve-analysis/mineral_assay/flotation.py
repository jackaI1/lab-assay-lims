"""Reconcile a feed, concentrate and tailings assay with a two-product balance."""
import numpy as np
from scipy.optimize import least_squares

def reconcile(feed, concentrate, tailings, mass_pull, assay_sd, mass_pull_sd):
    """Assays and mass pull are fractions. Return weighted least-squares estimates.

    The balance is F = p*C + (1-p)*T. Standard deviations describe measurement
    uncertainty; this is a single-element, steady-state two-product model.
    """
    observed = np.array([feed, concentrate, tailings, mass_pull], float)
    sd = np.array([*assay_sd, mass_pull_sd], float)
    if sd.shape != (4,) or not np.all(np.isfinite(observed)) or not np.all(np.isfinite(sd)) or np.any(sd <= 0) or np.any((observed < 0) | (observed > 1)):
        raise ValueError("Fractions must be in [0,1] and four uncertainties positive")
    def residual(z):
        c, t, p = z
        return (np.array([p*c+(1-p)*t, c, t, p])-observed)/sd
    result = least_squares(residual, observed[1:], bounds=(0, 1))
    if not result.success:
        raise RuntimeError("Reconciliation did not converge")
    c, t, p = result.x
    f = p*c+(1-p)*t
    if f <= 0:
        raise ValueError("Recovery undefined for zero feed grade")
    return {"feed": float(f), "concentrate": float(c), "tailings": float(t), "mass_pull": float(p), "recovery": float(p*c/f), "weighted_residual": float(np.sum(result.fun**2))}

def grade_prediction_flags(feed, mass_pull, predicted_grade):
    if not 0 < mass_pull <= 1 or not 0 <= feed <= 1 or not np.isfinite(predicted_grade):
        raise ValueError("Invalid feed, mass pull or prediction")
    flags = []
    if not 0 <= predicted_grade <= 1:
        flags.append("grade outside physical fraction range")
    if mass_pull * predicted_grade > feed + 1e-12:
        flags.append("concentrate contains more metal than feed")
    return flags
