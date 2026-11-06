# How the comparison works

I want a repeatable way to check whether a release curve actually supports a model. This tool describes cumulative fractions released from a known total load. It does not establish a mechanism, predict patient exposure or choose a formulation for clinical use.

## Equations and units

`t` is time in the unit recorded in the metadata, and `F` is released mass divided by the known releasable total. The input is a fraction, not a percentage. The total is fixed, never estimated from the last observation. Every model has zero baseline, no burst fraction and no lag parameter.

| Model | F(t) | Parameter units |
|---|---|---|
| Zero order | k t | k: time^-1 |
| First order | 1 - exp(-k t) | k: time^-1 |
| Higuchi | k sqrt(t) | k: time^-1/2 |
| Korsmeyer-Peppas | k t^n | k: time^-n; n: dimensionless |
| Weibull | 1 - exp(-(t/tau)^beta) | tau: time; beta: dimensionless |

The Weibull time scale here is `tau`, rather than the alternative coefficient `alpha` inside `t^beta / alpha`. In that convention alpha = tau^beta. A Weibull with beta = 1 is exactly first order with k = 1/tau; these cannot be distinguished by curve fitting.

Fits minimize the unweighted sum of squared errors on the original fraction scale. The optimizer divides residuals by a common response amplitude within each fit to avoid false convergence on tiny responses; this does not change the optimum or the reported scores. I do not compare R-squared values from different log transforms. Positive parameters are optimized in log space, after scaling times by the largest time. Shape parameters have numerical bounds 0.05 to 5, and the code warns if a fitted shape touches a bound. The internal scale parameter log bounds are -28 to 28. Two-parameter models use three initial shapes to reduce sensitivity to starting values. Neither these starts nor the final parameters are tuned on held-out errors.

## Validity and matching observations

There are two independent comparisons, never one combined ranking:

- **First 60%:** every model uses exactly the positive-time observations preceding the first observed fraction above 0.60. The point at 0.60 is allowed. A later noisy dip does not re-enter this scope. This is the only scope that fits Korsmeyer-Peppas. Its plot stops at a predicted fraction of 0.60 as well.
- **Full curve:** all positive-time observations, excluding Korsmeyer-Peppas. Higuchi is shown as a descriptive candidate with an explicit assumption warning, not automatically endorsed over the full range.

Each scope needs at least six observations and a fraction range larger than twice the extraction half-width (with a numerical floor of 1e-8). Flat or already saturated scopes cannot identify release rates and have their parameters and intervals withheld. Otherwise it is reported as insufficient, without numbers that look like a successful fit. A zero-time, zero-fraction baseline is retained in input but omitted from scores: every equation is fixed at the origin. Nonzero baselines, duplicate/unsorted times, nonfinite values and fractions outside [0,1] are rejected. Small decreases are allowed and flagged because noisy cumulative data can decrease.

Higuchi requires suitable geometry, sink conditions, constant diffusivity, and negligible swelling or erosion. A fit cannot verify these assumptions. Unbounded zero-order, Higuchi and Peppas predictions are not clipped to look physical. The report warns if fitted predictions exceed the physical range on observations. Plots stop at their range limit. All reports warn against extrapolation outside observed times and against interpreting a Peppas exponent without geometry and independent physical evidence.

## Held-out points and information criteria

Within each scope, observations at zero-based positions 1, 4, 7, ... are held out; the remainder train each model. I use an interleaved split to check reconstruction at untrained sampling times. It is not a future-time forecast or independent experiment. The report saves exact original-row indices, training parameters and held-out predictions in JSON. RMSE is the square root of mean squared held-out error, multiplied by 100 to give percentage points.

After this check, each model is refitted to all observations in that scope for reported parameters, intervals, residuals and information criteria. AICc is a small-sample correction of Akaike's information criterion, which penalizes extra adjustable parameters. For n observations, SSE the residual sum of squares, and K the number of model parameters **plus one residual variance parameter**:

```text
AIC = n ln(SSE/n) + 2K
AICc = AIC + 2K(K+1)/(n-K-1)
```

The constant common to models on the same observations is omitted. A variance floor of 1e-24 avoids log(0) on exact synthetic data. AICc is unavailable when n <= K+1. Its Gaussian independent-error assumption is only approximate for cumulative release data. Never compare AICc across scopes or curves.

A pair gets a conservative "cannot separate" warning if either its AICc difference is below 2, or a percentile interval of the mean paired held-out squared-error difference includes zero. That interval uses 1,000 resamples of held-out point pairs. Two held-out RMSE values below a practical tolerance of 0.1 percentage points also trigger a warning. These thresholds are declared heuristics, not proof of statistical equivalence; tiny held-out samples have very little resolving power. AICc and held-out errors may disagree, and no automatic winner is declared.

## Bootstrap uncertainty and extraction error

For every refitted model I center the fitted residuals, sample them with replacement at the original times, add independent uniform extraction/rounding jitter from [-e, e], and refit. `e` is the fraction half-width from metadata, not an invented laboratory standard deviation. The 2.5th and 97.5th parameter percentiles form a conditional 95% interval. The CLI records the random seed and draw count. It does not clip pseudo-responses, which would bias fits near zero or complete release. It reports the success count and withholds intervals below 80% successful draws or 20 draws, whichever is larger.

Residual resampling assumes exchangeable errors. Repeated cumulative sampling, unknown experimental errors, pH changes and model misspecification violate that assumption. The interval does not include uncertainty in total loading, sampling time, the choice of model or independent biological replication. Use original replicate curves and a suitable correlated-error model before making experimental claims. There are no raw replicate curves in the bundled table.

## Public source and traceability

The input is the second Table 4, the kinetics table, in [Ghosh et al., 2020](https://ijpsr.com/bft-article/formulation-and-evaluation-of-a-ph-dependent-multi-particulate-colon-targeted-drug-delivery-system-using-powder-layering-technology-of-ketoprofen/?view=fulltext). I manually copied only the time and release-percentage columns and divided percentages by 100. No point was read from a graph, so there is no graph digitization error. I allow half the displayed precision as a rounding bound: +/-0.005 percentage points. Time uncertainty and experimental error are unknown, rather than silently assigned zero. The raw input and metadata hashes are saved in the JSON output.

The kinetics table and comparative table disagree at 4 h: 16.32% versus 14.32%. The selected input preserves the kinetics table. The experiment changes medium pH, and prose and table timings also disagree. All reports expose those issues. This makes it a useful case for showing why a numerical fit cannot settle a physical mechanism. I do not reproduce the paper's transformed regressions or its model-selection claim.

Model forms follow [Zhang et al., DDSolver, 2010, Table I](https://pmc.ncbi.nlm.nih.gov/articles/PMC2895453/). The early-range restriction is also discussed in [Heredia et al., 2022](https://pmc.ncbi.nlm.nih.gov/articles/PMC8912140/), which compares published release data. These are method references, not additional bundled datasets. No synthetic curve is presented as experimental evidence. The source data and derived reports retain [CC BY-NC-SA 3.0](https://creativecommons.org/licenses/by-nc-sa/3.0/); original code is MIT licensed.

## Project design and checks

`models.py` contains the equations and optimizer; `analysis.py` owns validation, scope splitting, scores and bootstrapping; `data.py` reads provenance-bearing inputs; `report.py` writes offline HTML, Markdown, SVG and strict JSON; `cli.py` connects them. A notebook would make ad hoc inspection easier but leave more manual state. A web service would add hosting and input-upload complexity without improving this offline workflow, so I used a small command-line package.

Synthetic tests calculate each curve independently from its equation, recover known parameters, and check recovery with fixed-seed noise. Other tests verify information criteria by hand, scope masks, held-out prediction calculations, sparse data, ambiguity, repeatable intervals and CLI failures. The GitHub workflow installs from the lockfile, runs the suite and lint checks, builds a package and regenerates the public-data report as a downloadable artifact.

Reports are generated in a temporary staging directory. Existing artifact files are backed up during installation and restored after ordinary I/O errors; unrelated output files are preserved. This is not a transaction against process termination or power loss.
