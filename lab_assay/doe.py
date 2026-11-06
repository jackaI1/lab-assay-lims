"""Seeded three-factor deposition experiments in coded units (-1 to +1)."""

import argparse
import itertools
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats
from statsmodels.stats.anova import anova_lm

FACTORS = ["power", "pressure", "time"]


def _order(points, replicates, seed):
    if replicates < 1:
        raise ValueError("replicates must be positive")
    return (
        pd.DataFrame(points * replicates, columns=FACTORS)
        .sample(frac=1, random_state=seed)
        .reset_index(drop=True)
    )


def factorial(replicates=1, seed=2026):
    return _order(list(itertools.product([-1.0, 1.0], repeat=3)), replicates, seed)


def fractional(replicates=1, seed=2026):
    return _order([(a, b, a * b) for a, b in itertools.product([-1.0, 1.0], repeat=2)], replicates, seed)


def central_composite(replicates=1, seed=2026, alpha=2 ** (3 / 4), centers=4):
    points = list(itertools.product([-1.0, 1.0], repeat=3))
    points += [tuple(sign * alpha if i == j else 0 for i in range(3)) for j in range(3) for sign in (-1, 1)]
    points += [(0.0, 0.0, 0.0)] * centers
    return _order(points, replicates, seed)


def simulate(design, seed=2026, noise=0.5, drift=0.02):
    d = design.copy()
    p, q, t = (d[k].to_numpy() for k in FACTORS)
    rng = np.random.default_rng(seed)
    d["thickness"] = (
        100
        + 12 * p
        - 5 * q
        + 8 * t
        + 3 * p * q
        - 2 * p * p
        - 3 * q * q
        - t * t
        + drift * np.arange(len(d))
        + rng.normal(0, noise, len(d))
    )
    d["uniformity"] = 95 - 2 * p * p - 3 * q * q - t * t + p * q + rng.normal(0, noise / 2, len(d))
    return d


def analyse(data):
    alias = []
    fraction = len(data[FACTORS].drop_duplicates()) == 4 and np.allclose(
        data.time, data.power * data.pressure
    )
    if fraction:
        alias = ["power = pressure:time", "pressure = power:time", "time = power:pressure"]
    formula = "thickness ~ power + pressure + time" if fraction else "thickness ~ power * pressure * time"
    # Quadratic terms are identifiable in a central composite design, but not a two-level design.
    if any(data[k].nunique() > 2 for k in FACTORS):
        formula = "thickness ~ (power + pressure + time)**2 + I(power**2) + I(pressure**2) + I(time**2)"
    model = smf.ols(formula, data=data).fit()
    anova = anova_lm(model, typ=2)
    groups = data.groupby(FACTORS)["thickness"]
    pure_error = float(groups.apply(lambda s: ((s - s.mean()) ** 2).sum()).sum())
    pure_df = len(data) - groups.ngroups
    lof_df = model.df_resid - pure_df
    lof_ss = max(0.0, float(model.ssr) - pure_error)
    lof_p = (
        float(stats.f.sf((lof_ss / lof_df) / (pure_error / pure_df), lof_df, pure_df))
        if lof_df > 0 and pure_df > 0 and pure_error > 0
        else None
    )
    centers = data[(data[FACTORS] == 0).all(axis=1)]["thickness"]
    corners = data[(data[FACTORS].abs() == 1).all(axis=1)]["thickness"]
    curvature_p = (
        float(stats.ttest_ind(centers, corners, equal_var=False).pvalue)
        if len(centers) > 1 and len(corners) > 1
        else None
    )
    grid = pd.DataFrame(list(itertools.product(np.linspace(-1, 1, 21), repeat=3)), columns=FACTORS)
    predictions = model.predict(grid)
    optimum = grid.iloc[int(np.argmax(predictions))].to_dict()
    optimum["predicted_thickness"] = float(max(predictions))
    return {
        "alias": alias,
        "coefficients": model.params.to_dict(),
        "anova": anova.reset_index()
        .rename(columns={"index": "term"})
        .replace({np.nan: None})
        .to_dict("records"),
        "lack_of_fit_p": lof_p,
        "curvature_p": curvature_p,
        "residuals": model.resid.tolist(),
        "fitted": model.fittedvalues.tolist(),
        "optimum": optimum,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="doe-output")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--design", choices=["full", "fractional", "composite"], default="composite")
    parser.add_argument("--replicates", type=int, default=2)
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    design = {"full": factorial, "fractional": fractional, "composite": central_composite}[args.design]
    d = simulate(design(replicates=args.replicates, seed=args.seed), seed=args.seed)
    d.to_csv(out / "run-sheet.csv", index_label="run")
    result = analyse(d)
    import json

    (out / "report.json").write_text(json.dumps(result, indent=2, allow_nan=False))
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for name in FACTORS:
        d.groupby(name).thickness.mean().plot(ax=axes[0], marker="o", label=name)
    axes[0].set(title="Mean thickness by coded factor", xlabel="Coded level", ylabel="Thickness (nm)")
    axes[0].legend()
    axes[1].scatter(result["fitted"], result["residuals"])
    axes[1].axhline(0, color="black")
    axes[1].set(xlabel="Fitted thickness", ylabel="Residual")
    fig.tight_layout()
    fig.savefig(out / "effects.png")
    plt.close(fig)


if __name__ == "__main__":
    main()
