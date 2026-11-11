"""Dementia-style health microsimulation with calibration, validation and sensitivity analysis.

A synthetic cohort starts at age 65 in one of five states (healthy, mild cognitive impairment,
dementia, long-term care, dead) and is aged one year at a time. Transition rates come from
`data/microsim/config.json`, which lists each published source and each assumption.

Run it with:

    uv run python -m lab_assay.microsim --output microsim-output
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
from scipy import optimize

STATES = ("healthy", "mci", "dementia", "ltc", "dead")
H, M, D, L, X = range(5)
DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "data" / "microsim" / "config.json"


@dataclass(frozen=True)
class Params:
    """Everything the simulation needs. Multipliers scale the config rates; hazard ratios scale mortality."""

    a0: float
    slope: float
    start_age: int
    end_age: int
    init_mci: float
    init_dementia: float
    rates: dict
    mult_h_to_mci: float = 1.0
    mult_dementia_onset: float = 1.0
    mult_d_to_ltc: float = 1.0
    mult_mci_revert: float = 1.0
    hr_mci: float = 1.3
    hr_dementia: float = 2.5
    hr_ltc: float = 3.0


def load_config(path: Path | str = DEFAULT_CONFIG) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def gompertz_qx(a0: float, slope: float, ages: np.ndarray, start_age: int) -> np.ndarray:
    return np.minimum(0.999, a0 * np.exp(slope * (ages - start_age)))


def life_expectancy(a0: float, slope: float, start_age: int, end_age: int) -> float:
    """Remaining years of life at start_age from the Gompertz hazard, with deaths spread across each year."""
    ages = np.arange(start_age, end_age + 1)
    q = gompertz_qx(a0, slope, ages, start_age)
    q[-1] = 1.0
    alive_at_start = np.concatenate([[1.0], np.cumprod(1.0 - q)[:-1]])
    return float(np.sum(alive_at_start * (1.0 - 0.5 * q)))


def base_params(cfg: dict) -> Params:
    """Build the uncalibrated parameters. Solves a0 so the life table matches target_e65."""
    mort = cfg["mortality"]
    a0 = optimize.brentq(
        lambda a: life_expectancy(a, mort["slope"], cfg["start_age"], cfg["end_age"]) - mort["target_e65"],
        1e-6,
        0.5,
    )
    return Params(
        a0=a0,
        slope=mort["slope"],
        start_age=cfg["start_age"],
        end_age=cfg["end_age"],
        init_mci=cfg["initial"]["mci"],
        init_dementia=cfg["initial"]["dementia"],
        rates=cfg["rates"],
        hr_mci=mort["hazard_ratio"]["mci"],
        hr_dementia=mort["hazard_ratio"]["dementia"],
        hr_ltc=mort["hazard_ratio"]["ltc"],
    )


def annual_rates(p: Params, age: int) -> dict[str, float]:
    """Annual transition probabilities at an age, before mortality and the sum-to-one check."""
    years = age - p.start_age
    multipliers = {
        "h_to_mci": p.mult_h_to_mci,
        "mci_to_d": p.mult_dementia_onset,
        "h_to_d": p.mult_dementia_onset,
        "mci_revert": p.mult_mci_revert,
        "d_to_ltc": p.mult_d_to_ltc,
    }
    out = {}
    for name, mult in multipliers.items():
        spec = p.rates[name]
        out[name] = min(0.95, mult * spec["base"] * math.exp(spec["growth"] * years))
    return out


def transition_matrix(p: Params, age: int) -> np.ndarray:
    """Row-stochastic 5x5 matrix for one year. Each row sums to exactly 1.

    Mortality is taken first: a person in state s dies with probability q_s. The remaining
    (1 - q_s) is split between non-death transitions and staying put. If the transition rates
    together exceed 1, they are rescaled to sum to 1, so no probability is ever negative.
    """
    rr = annual_rates(p, age)
    q = min(0.999, p.a0 * math.exp(p.slope * (age - p.start_age)))
    hazard = {H: 1.0, M: p.hr_mci, D: p.hr_dementia, L: p.hr_ltc}
    moves = {
        H: {M: rr["h_to_mci"], D: rr["h_to_d"]},
        M: {H: rr["mci_revert"], D: rr["mci_to_d"]},
        D: {L: rr["d_to_ltc"]},
        L: {},
    }
    P = np.zeros((5, 5))
    for s, targets in moves.items():
        q_s = min(0.999, hazard[s] * q)
        total = sum(targets.values())
        scale = 1.0 / total if total > 1.0 else 1.0
        total = min(total, 1.0)
        P[s, X] = q_s
        for nxt, rate in targets.items():
            P[s, nxt] = (1.0 - q_s) * rate * scale
        P[s, s] = (1.0 - q_s) * (1.0 - total)
    P[X, X] = 1.0
    return P


def simulate(p: Params, n: int, seed: int) -> np.ndarray:
    """Age n people from start_age to end_age. Returns counts[t, state], one row per age."""
    rng = np.random.default_rng(seed)
    years = p.end_age - p.start_age
    u0 = rng.random(n)
    state = np.where(u0 < p.init_dementia, D, np.where(u0 < p.init_dementia + p.init_mci, M, H))
    counts = np.zeros((years + 1, 5), dtype=np.int64)
    for t in range(years + 1):
        counts[t] = np.bincount(state, minlength=5)
        if t == years:
            break
        cum = np.cumsum(transition_matrix(p, p.start_age + t), axis=1)
        cum[:, -1] = 1.0
        draw = rng.random(n)
        state = np.minimum((draw[:, None] >= cum[state]).sum(axis=1), X)
    return counts


def dementia_prevalence_by_age(counts: np.ndarray) -> np.ndarray:
    """Share of living people with dementia (dementia or long-term care) at each age."""
    alive = counts[:, :X].sum(axis=1)
    demented = counts[:, D] + counts[:, L]
    return np.divide(demented, alive, out=np.zeros(len(alive)), where=alive > 0)


def band_prevalence(counts: np.ndarray, start_age: int, lo: int, hi: int) -> float:
    """Dementia prevalence across an age band, weighting each age by the number still alive."""
    idx = [a - start_age for a in range(lo, hi + 1) if 0 <= a - start_age < len(counts)]
    alive = counts[idx, :X].sum()
    demented = (counts[idx, D] + counts[idx, L]).sum()
    return float(demented / alive) if alive else 0.0


def person_years_dementia(counts: np.ndarray, n: int) -> float:
    """Mean years lived with dementia (dementia or long-term care) per person, counted from age 65."""
    return float((counts[:, D] + counts[:, L]).sum() / n)


def _band_predictions(counts: np.ndarray, p: Params, targets: list[dict]) -> list[float]:
    return [band_prevalence(counts, p.start_age, *t["band"]) for t in targets]


def calibrate(cfg: dict, base: Params, n: int, seed: int) -> dict:
    """Least-squares fit of two rate multipliers to the calibration bands, in log space.

    The validation band is not passed to the fitter. Each evaluation reuses the same seed, so the
    residuals are a smooth function of the parameters.
    """
    targets = [t for t in cfg["targets"] if t["role"] == "calibration"]

    def residuals(log_mults: np.ndarray) -> np.ndarray:
        p = replace(
            base,
            mult_h_to_mci=float(math.exp(log_mults[0])),
            mult_dementia_onset=float(math.exp(log_mults[1])),
        )
        preds = _band_predictions(simulate(p, n, seed), p, targets)
        return np.array([(pred - t["value"]) / t["value"] for pred, t in zip(preds, targets)])

    step = 0.02

    def jacobian(log_mults: np.ndarray) -> np.ndarray:
        # Individuals are discrete, so the outcome moves in small jumps. The optimizer's own
        # finite-difference step did not move the fit, so the Jacobian is computed here with a
        # fixed 0.02 step on the same seed.
        base_res = residuals(log_mults)
        cols = [(residuals(log_mults + step * np.eye(2)[i]) - base_res) / step for i in range(2)]
        return np.column_stack(cols)

    fit = optimize.least_squares(
        residuals, x0=np.zeros(2), jac=jacobian, bounds=([-3.0, -3.0], [3.0, 3.0]), xtol=1e-6
    )
    calibrated = replace(
        base,
        mult_h_to_mci=float(math.exp(fit.x[0])),
        mult_dementia_onset=float(math.exp(fit.x[1])),
    )
    return {
        "params": calibrated,
        "log_multipliers": fit.x.tolist(),
        "success": bool(fit.success),
        "cost": float(fit.cost),
        "n_evaluations": int(fit.nfev),
        "targets": targets,
    }


def validate(cfg: dict, p: Params, n: int, seed: int) -> list[dict]:
    """Compare held-out bands with their targets, using the calibrated parameters."""
    counts = simulate(p, n, seed)
    rows = []
    for t in (t for t in cfg["targets"] if t["role"] == "validation"):
        pred = band_prevalence(counts, p.start_age, *t["band"])
        rel_error = (pred - t["value"]) / t["value"]
        rows.append(
            {
                "band": t["band"],
                "target": t["value"],
                "predicted": pred,
                "relative_error": rel_error,
                "tolerance": t["tolerance"],
                "passed": abs(rel_error) <= t["tolerance"],
            }
        )
    return rows


def _with(p: Params, name: str, value: float) -> Params:
    return replace(p, **{name: value})


def one_way_sensitivity(cfg: dict, p: Params, n: int, seed: int) -> list[dict]:
    """Move each parameter between its low and high values, one at a time (common seed)."""
    rows = []
    for spec in cfg["sensitivity"]:
        if spec["kind"] == "relative":
            base_value = getattr(p, spec["name"])
            low_value, high_value = base_value * spec["low"], base_value * spec["high"]
        else:
            low_value, high_value = spec["low"], spec["high"]
        low = person_years_dementia(simulate(_with(p, spec["name"], low_value), n, seed), n)
        high = person_years_dementia(simulate(_with(p, spec["name"], high_value), n, seed), n)
        rows.append(
            {
                "parameter": spec["name"],
                "label": spec["label"],
                "low_input": low_value,
                "high_input": high_value,
                "outcome_low": low,
                "outcome_high": high,
                "swing": abs(high - low),
            }
        )
    return sorted(rows, key=lambda r: r["swing"], reverse=True)


def _draw_psa_value(rng: np.random.Generator, spec: dict, base_value: float) -> float:
    z = rng.standard_normal()
    if spec["dist"] == "lognormal":
        return base_value * math.exp(spec["sd"] * z)
    return max(spec["min"], base_value * (1.0 + spec["sd"] * z))


def probabilistic_sensitivity(cfg: dict, p: Params, draws: int, population: int, seed: int) -> dict:
    """Sample parameter sets from their distributions and report percentile intervals for each outcome."""
    rng = np.random.default_rng(seed)
    outcomes, band_85 = [], []
    band_target = next(t for t in cfg["targets"] if t["band"][0] == 85)
    for i in range(draws):
        values = {spec["name"]: _draw_psa_value(rng, spec, getattr(p, spec["name"])) for spec in cfg["psa"]}
        draw_params = replace(p, **values)
        counts = simulate(draw_params, population, seed + 1 + i)
        outcomes.append(person_years_dementia(counts, population))
        band_85.append(band_prevalence(counts, p.start_age, *band_target["band"]))
    return {
        "draws": draws,
        "population": population,
        "person_years_dementia": _interval(outcomes),
        "prevalence_85_plus": _interval(band_85),
        "_raw": {"person_years_dementia": outcomes, "prevalence_85_plus": band_85},
    }


def _interval(values: list[float]) -> dict:
    arr = np.asarray(values, dtype=float)
    lo, med, hi = np.percentile(arr, [2.5, 50, 97.5])
    return {"median": float(med), "p2_5": float(lo), "p97_5": float(hi)}


def prevalence_table(counts: np.ndarray, start_age: int) -> list[dict]:
    prev = dementia_prevalence_by_age(counts)
    return [
        {"age": start_age + t, "alive": int(counts[t, :X].sum()), "dementia_prevalence": float(prev[t])}
        for t in range(len(counts))
    ]


def _plot(report: dict, output: Path) -> list[str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    written = []

    table = report["prevalence_by_age"]
    ages = [row["age"] for row in table]
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(ages, [100 * row["dementia_prevalence"] for row in table], color="#1f5f8b", label="Simulated")
    for band in report["validation"] + report["calibration_targets"]:
        lo, hi = band["band"]
        ax.hlines(
            100 * band["target"],
            lo,
            hi,
            colors="#b5472b" if band.get("role") == "validation" else "#2b7a3d",
            linewidth=3,
            label=band.get("label", ""),
        )
    ax.set_xlabel("Age (years)")
    ax.set_ylabel("Dementia prevalence (%)")
    ax.set_title("Calibrated prevalence vs published targets (held-out band in red)")
    handles, labels = ax.get_legend_handles_labels()
    seen = {}
    for h, lab in zip(handles, labels):
        if lab and lab not in seen:
            seen[lab] = h
    ax.legend(seen.values(), seen.keys(), fontsize=8)
    fig.tight_layout()
    path = output / "prevalence-by-age.png"
    fig.savefig(path, dpi=130)
    plt.close(fig)
    written.append(path.name)

    rows = report["one_way"]
    base = report["base_person_years_dementia"]
    fig, ax = plt.subplots(figsize=(8, 4.8))
    for i, row in enumerate(rows):
        ax.barh(i, row["outcome_low"] - base, left=base, color="#1f5f8b", height=0.6)
        ax.barh(i, row["outcome_high"] - base, left=base, color="#b5472b", height=0.6)
    ax.axvline(base, color="black", linewidth=1)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r["label"] for r in rows], fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("Mean years with dementia from age 65")
    ax.set_title("One-way sensitivity (blue = low input, red = high input)")
    fig.tight_layout()
    path = output / "tornado.png"
    fig.savefig(path, dpi=130)
    plt.close(fig)
    written.append(path.name)

    psa = report["probabilistic"]
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6))
    for ax, key, label in zip(
        axes,
        ("person_years_dementia", "prevalence_85_plus"),
        ("Years with dementia from 65", "Dementia prevalence, 85+ (share)"),
    ):
        iv = psa[key]
        ax.errorbar(
            [0],
            [iv["median"]],
            yerr=[[iv["median"] - iv["p2_5"]], [iv["p97_5"] - iv["median"]]],
            fmt="o",
            color="#1f5f8b",
            capsize=6,
        )
        ax.set_xticks([])
        ax.set_title(label, fontsize=10)
    fig.suptitle(f"Probabilistic sensitivity: median and 95% interval over {psa['draws']} draws", fontsize=10)
    fig.tight_layout()
    path = output / "psa-intervals.png"
    fig.savefig(path, dpi=130)
    plt.close(fig)
    written.append(path.name)
    return written


def run(cfg: dict, population: int, seed: int, psa_draws: int, psa_population: int, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    base = base_params(cfg)
    fit = calibrate(cfg, base, population, seed)
    p = fit["params"]
    counts = simulate(p, population, seed)
    validation = validate(cfg, p, population, seed)
    calibration_rows = []
    for t in fit["targets"]:
        pred = band_prevalence(counts, p.start_age, *t["band"])
        calibration_rows.append(
            {
                "band": t["band"],
                "target": t["value"],
                "predicted": pred,
                "relative_error": (pred - t["value"]) / t["value"],
                "role": "calibration",
                "label": "Published target (calibration)",
            }
        )
    for row in validation:
        row["label"] = "Held-out target (validation)"
        row["role"] = "validation"
    tornado = one_way_sensitivity(cfg, p, population, seed)
    psa = probabilistic_sensitivity(cfg, p, psa_draws, psa_population, seed)
    base_outcome = person_years_dementia(counts, population)

    report = {
        "seed": seed,
        "population": population,
        "life_expectancy_65_target": cfg["mortality"]["target_e65"],
        "life_expectancy_65_model": life_expectancy(base.a0, base.slope, base.start_age, base.end_age),
        "calibration": {
            "success": fit["success"],
            "n_evaluations": fit["n_evaluations"],
            "multipliers": {"mult_h_to_mci": p.mult_h_to_mci, "mult_dementia_onset": p.mult_dementia_onset},
            "calibration_bands": calibration_rows,
        },
        "validation": validation,
        "validation_passed": all(row["passed"] for row in validation),
        "base_person_years_dementia": base_outcome,
        "one_way": tornado,
        "probabilistic": {k: v for k, v in psa.items() if not k.startswith("_")},
        "prevalence_by_age": prevalence_table(counts, p.start_age),
        "calibration_targets": calibration_rows,
    }
    report["files"] = _plot(report, output)
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the dementia-style health microsimulation.")
    parser.add_argument("--output", type=Path, default=Path("microsim-output"))
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--population", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--psa-draws", type=int, default=200)
    parser.add_argument("--psa-population", type=int, default=5000)
    args = parser.parse_args(argv)
    if args.population < 100 or args.psa_population < 100 or args.psa_draws < 1:
        parser.error("population must be at least 100 and psa draws at least 1")

    report = run(
        load_config(args.config), args.population, args.seed, args.psa_draws, args.psa_population, args.output
    )
    cal = report["calibration"]["calibration_bands"]
    print(
        f"Life expectancy at 65: target {report['life_expectancy_65_target']:.2f}, "
        f"model {report['life_expectancy_65_model']:.2f}"
    )
    for row in cal:
        print(
            f"Calibration {row['band'][0]}-{row['band'][1]}: target {row['target']:.3f}, "
            f"predicted {row['predicted']:.3f}"
        )
    for row in report["validation"]:
        status = "PASS" if row["passed"] else "FAIL"
        print(
            f"Validation {row['band'][0]}-{row['band'][1]}: target {row['target']:.3f}, "
            f"predicted {row['predicted']:.3f}, error {row['relative_error']:+.1%} [{status}]"
        )
    print(f"Mean years with dementia from 65: {report['base_person_years_dementia']:.2f}")
    print(
        f"PSA 95% interval: {report['probabilistic']['person_years_dementia']['p2_5']:.2f} to "
        f"{report['probabilistic']['person_years_dementia']['p97_5']:.2f}"
    )
    print(f"Wrote {args.output / 'report.json'} and {', '.join(report['files'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
