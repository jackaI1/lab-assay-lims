# titration-curve-analysis

I built a tool for analyzing laboratory measurements to learn how the underlying idea works. This is a learning project.

## Working with measurements

A titration adds a reagent of known concentration until the reaction reaches its equivalence point. Save the added volume in mL as `volume_ml` and readings as `ph` or `potential_mv` in a CSV file, with volumes strictly increasing. The endpoint can be estimated from the strongest change in the curve (first derivative), a nearby change in curvature (second derivative), or a Gran plot, which extrapolates a selected straight-line region before the endpoint. A search range helps isolate the desired endpoint when there are several changes.

```python
from mineral_assay.titration import Curve, equivalence, gran, concentration, replicate_summary

curve = Curve.csv('examples/acid_replicate_1.csv')
endpoint = equivalence(curve, method='second', search=(8, 12))
gran_endpoint = gran(curve, sample_volume_ml=20, fit_range=(4, 8), model='strong_acid')
result = concentration(endpoint, titrant_mol_l=0.1, sample_ml=20)
print(endpoint, gran_endpoint, result)  # mL, mL, mol/L
print(replicate_summary([0.049, 0.050, 0.051]))
```

For a back titration, pass `initial_reagent_mol`: the titrant measures the reagent left over, which is subtracted from the known amount initially added. `analyte_per_titrant` specifies the mole ratio. The back titrant and excess reagent are assumed to react one-to-one. Replicate uncertainty is the sample standard deviation and standard error of independently calculated concentrations; it does not include calibration, volume or model uncertainty.

## Other assay calculations

XRF measures energy peaks associated with elements. `mineral_assay.xrf.fit_spectrum` fits known Fe, Cu, Zn and Ca line positions with Gaussian peaks and a background, returning integrated peak areas. `calibrate` fits a line through measured standard areas and known concentrations. Standards should match the sample matrix; overlapping lines, detector response and matrix effects can make the estimate misleading.

Flotation separates a feed into concentrate and tailings. `mineral_assay.flotation.reconcile` adjusts measured grades and mass pull (the fraction of feed reporting to concentrate) within stated measurement uncertainties to satisfy a metal balance. It returns recovery, the fraction of feed metal in the concentrate. `grade_prediction_flags` checks for fractions outside 0 to 1 and concentrate metal exceeding feed metal.

## Design and limits

The derivative methods interpolate uneven additions onto a uniform grid, smooth with a Savitzky-Golay filter and find a peak or nearby zero crossing. Choose the smoothing window and search range based on the curve. Gran fits require pH and a user-selected linear region: the implemented strong-acid and weak-acid formulas assume acid titrated with strong base. They are not general-purpose formulas for bases, polyprotic systems or activity corrections. Synthetic acid curves include an exact charge balance and noise; the weak-acid test uses a buffer approximation. These methods should be checked against standards and real laboratory measurements before use for decisions.

## Tests and limits

There are 1 test source files in this copy. That source count does not establish an execution result. This is a source snapshot, and running it on a new machine may need environment-specific setup.



Retained project workflows: `titration-curve-analysis-test.yml`. Their commands use this folder and their triggers use its paths.
