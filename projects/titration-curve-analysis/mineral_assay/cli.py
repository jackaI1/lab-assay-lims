"""Generate a compact, reproducible example report."""
import argparse
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from .titration import Curve, equivalence, gran, concentration, replicate_summary, derivatives
from .xrf import fit_spectrum, calibrate
from .flotation import reconcile, grade_prediction_flags

def main():
    parser = argparse.ArgumentParser(description="Build a mineral assay example report")
    parser.add_argument("--data", default="examples", help="directory containing example CSV files")
    parser.add_argument("--output", default="report", help="output directory")
    args = parser.parse_args()
    data, out = Path(args.data), Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    curves = [Curve.csv(data / f"acid_replicate_{i}.csv") for i in range(1, 4)]
    endpoints = [equivalence(c, search=(8, 12)) for c in curves]
    concentrations = [concentration(v, 0.1, 20) for v in endpoints]
    stats = replicate_summary(concentrations)
    c = curves[0]
    v, smoothed, d1, _ = derivatives(c)
    fig, ax = plt.subplots(1, 2, figsize=(10, 4))
    ax[0].plot(c.volume, c.signal, '.', ms=2, label="readings")
    ax[0].plot(v, smoothed, label="smoothed")
    ax[0].axvline(endpoints[0], color='red', label="endpoint")
    ax[0].set(xlabel="Base added (mL)", ylabel="pH"); ax[0].legend()
    ax[1].plot(v, d1); ax[1].set(xlabel="Base added (mL)", ylabel="pH change per mL")
    fig.tight_layout(); fig.savefig(out / "titration.png", dpi=140); plt.close(fig)
    spectrum = np.genfromtxt(data / "xrf_sample.csv", delimiter=',', names=True)
    fit = fit_spectrum(spectrum['energy_kev'], spectrum['counts'], ['Fe', 'Cu'])
    fe = calibrate(fit['areas']['Fe'], [10, 30, 50], [0.02, 0.06, 0.10])
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(spectrum['energy_kev'], spectrum['counts'], label="spectrum")
    ax.plot(spectrum['energy_kev'], fit['fit'], label="peak fit")
    ax.set(xlabel="Energy (keV)", ylabel="Counts"); ax.legend(); fig.tight_layout()
    fig.savefig(out / "xrf.png", dpi=140); plt.close(fig)
    balance = reconcile(.02, .12, .008, .1, [.002, .006, .001], .01)
    flags = grade_prediction_flags(.02, .1, .25)
    text = f"""# Mineral assay example report

## Titration
Three 20 mL acid samples titrated with 0.100 mol/L base. The known synthetic concentration is 0.050 mol/L.
First derivative endpoints (mL): {', '.join(f'{x:.3f}' for x in endpoints)}.
Mean concentration: {stats['mean']:.5f} mol/L; replicate sample standard deviation: {stats['sd']:.5f} mol/L (n={stats['n']}).
First run: second derivative endpoint {equivalence(c, 'second', search=(8, 12)):.3f} mL; strong-acid Gran endpoint {gran(c, 20, (4, 8)):.3f} mL.

![Titration](titration.png)

## XRF
Gaussian fits at known Fe and Cu line energies give integrated Fe area {fit['areas']['Fe']:.2f} counts keV. Example standards estimate Fe mass fraction {fe:.4f}. These simulated standards share the sample matrix.

![XRF](xrf.png)

## Flotation
The reconciled feed, concentrate, and tailings grades are {balance['feed']:.4f}, {balance['concentrate']:.4f}, and {balance['tailings']:.4f}; mass pull is {balance['mass_pull']:.4f} and metal recovery is {balance['recovery']:.3f}. A proposed concentrate grade of 0.25 is flagged: {', '.join(flags)}.
"""
    (out / "report.md").write_text(text)
    print(f"Wrote {out / 'report.md'} and two plots")

if __name__ == "__main__":
    main()
