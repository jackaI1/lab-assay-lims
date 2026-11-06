"""Same-point comparisons and conditional residual-bootstrap uncertainty."""

from itertools import combinations

import numpy as np

from .models import MODELS, fit, predict


def information_criteria(sse, n, parameter_count):
    # Unknown Gaussian residual variance is an estimated parameter too.
    k = parameter_count + 1
    aic = float(n * np.log(max(sse / n, 1e-24)) + 2 * k)
    aicc = aic + 2 * k * (k + 1) / (n - k - 1) if n > k + 1 else None
    return aic, aicc


def _bootstrap(name, t, y, p, count, error, rng):
    fitted = predict(name, t, p)
    residual = y - fitted
    residual -= residual.mean()
    draws = []
    for _ in range(count):
        pseudo = fitted + rng.choice(residual, len(t)) + rng.uniform(-error, error, len(t))
        try:
            draws.append(fit(name, t, pseudo))
        except ValueError:
            pass
    minimum = max(20, int(np.ceil(0.8 * count)))
    ci = np.percentile(draws, [2.5, 97.5], axis=0).T.tolist() if len(draws) >= minimum else None
    return ci, len(draws)


def _scope(t, y, indices, names, bootstrap, error, rng, label):
    scope = dict(
        label=label,
        indices=indices.tolist(),
        train_indices=[],
        test_indices=[],
        models={},
        warnings=[],
    )
    if len(indices) < 6:
        scope["warnings"].append("Insufficient points: need at least 6 in this scope; no ranking.")
        return scope
    if np.ptp(y[indices]) <= max(2 * error, 1e-8):
        scope["warnings"].append(
            "Insufficient release variation relative to extraction precision; "
            "flat or saturated curve cannot identify rates. Parameters and intervals withheld."
        )
        return scope
    # Deterministic interleaved validation, no tuning to validation performance.
    test = indices[1::3]
    train = np.array([i for i in indices if i not in test])
    scope.update(train_indices=train.tolist(), test_indices=test.tolist())
    losses = {}
    for name in names:
        try:
            training_p = fit(name, t[train], y[train])
            heldout_residual = predict(name, t[test], training_p) - y[test]
            losses[name] = heldout_residual**2
            p = fit(name, t[indices], y[indices])
            residual = y[indices] - predict(name, t[indices], p)
            sse = float(np.sum(residual**2))
            aic, aicc = information_criteria(sse, len(indices), len(p))
            ci, success = _bootstrap(name, t[indices], y[indices], p, bootstrap, error, rng)
            warns = []
            if aicc is None:
                warns.append("AICc undefined: too few points for parameter count.")
            if ci is None:
                warns.append("Too few successful bootstrap fits; interval withheld.")
            elif success < bootstrap:
                warns.append("Some bootstrap fits failed; inspect success count.")
            if len(p) == 2 and (p[1] < 0.0501 or p[1] > 4.999):
                warns.append("Shape parameter at optimization bound [.05, 5]; fit unreliable.")
            if name == "higuchi":
                warns.append(
                    "Higuchi requires sink conditions, constant diffusivity, negligible "
                    "swelling/erosion and appropriate geometry; not established by fit."
                )
            if name == "korsmeyer_peppas":
                warns.append(
                    "Restricted to observed first 60% release; no mechanism inferred "
                    "from exponent without geometry and independent evidence."
                )
            if np.any(predict(name, t[indices], p) > 1):
                warns.append("Prediction exceeds 100% release inside fitting range; invalid there.")
            if name == "korsmeyer_peppas" and np.any(predict(name, t[indices], p) > 0.6):
                warns.append("Fitted prediction exceeds 60% at edge of early scope; invalid there.")
            scope["models"][name] = dict(
                parameters=dict(zip(MODELS[name], p.tolist())),
                ci95=ci,
                bootstrap_success=success,
                aic=aic,
                aicc=aicc,
                sse=sse,
                heldout_rmse_pp=float(np.sqrt(np.mean(losses[name])) * 100),
                train_parameters=dict(zip(MODELS[name], training_p.tolist())),
                heldout_predictions=predict(name, t[test], training_p).tolist(),
                residuals_pp=(residual * 100).tolist(),
                warnings=warns,
            )
        except ValueError as exc:
            scope["warnings"].append(f"{name}: fit unavailable ({exc}).")
    for a, b in combinations(scope["models"], 2):
        ra, rb = scope["models"][a], scope["models"][b]
        close_ic = (
            ra["aicc"] is not None and rb["aicc"] is not None and abs(ra["aicc"] - rb["aicc"]) < 2
        )
        difference = losses[a] - losses[b]
        paired = rng.choice(difference, (1000, len(test))).mean(axis=1)
        lo, hi = np.percentile(paired, [2.5, 97.5])
        close_test = lo <= 0 <= hi or max(ra["heldout_rmse_pp"], rb["heldout_rmse_pp"]) < 0.1
        if close_ic or close_test:
            reasons = []
            if close_ic:
                reasons.append("delta AICc < 2")
            if close_test:
                reasons.append("held-out errors unresolved by paired resampling or both <0.1 pp")
            scope["warnings"].append(
                f"Data cannot separate {a} and {b}: " + "; ".join(reasons) + "."
            )
    return scope


def analyze(time, fraction, *, bootstrap=500, seed=2026, error=0.0):
    t, y = np.asarray(time, dtype=float), np.asarray(fraction, dtype=float)
    if (
        t.ndim != 1
        or t.shape != y.shape
        or len(t) < 3
        or not np.all(np.isfinite(t))
        or not np.all(np.isfinite(y))
        or np.any(t < 0)
        or np.any(np.diff(t) <= 0)
        or np.any((y < 0) | (y > 1))
    ):
        raise ValueError("Use paired finite increasing times and fractions in [0,1]")
    if np.any((t == 0) & (y != 0)):
        raise ValueError("Nonzero baseline needs a burst/lag model; these models start at zero")
    if not isinstance(bootstrap, int) or bootstrap < 20 or not np.isfinite(error) or error < 0:
        raise ValueError("Need bootstrap >=20 and finite nonnegative error half-width")
    rng = np.random.default_rng(seed)
    warnings = [
        "Korsmeyer-Peppas is invalid beyond first 60% release; excluded from full-curve scope.",
        "All models assume zero baseline and known releasable total; do not normalize by last point.",
        "Holdout is interleaved within one curve, not independent experimental replication.",
        "Bootstrap intervals assume exchangeable residuals; cumulative errors may be correlated. "
        "Intervals are conditional on this curve and model, not biological confidence.",
        "Do not extrapolate outside observed time range; no mechanism or clinical claims.",
    ]
    if np.any(np.diff(y) < 0):
        warnings.append(
            "Observed fractions decrease; check measurement noise and cumulative processing."
        )
    if np.any(t == 0):
        warnings.append(
            "Zero baseline excluded from scores: fixed origin is not a free observation."
        )
    positive = np.flatnonzero(t > 0)
    # Stop at the first crossing, even if noisy later data dips back below 60%.
    crossing = np.flatnonzero(y > 0.6)
    stop = crossing[0] if len(crossing) else len(y)
    early = positive[positive < stop]
    return dict(
        bootstrap=bootstrap,
        seed=seed,
        error_halfwidth_fraction=error,
        time=t.tolist(),
        fraction=y.tolist(),
        warnings=warnings,
        scopes=[
            _scope(t, y, early, list(MODELS), bootstrap, error, rng, "First 60%"),
            _scope(
                t,
                y,
                positive,
                [n for n in MODELS if n != "korsmeyer_peppas"],
                bootstrap,
                error,
                rng,
                "Full curve",
            ),
        ],
    )
