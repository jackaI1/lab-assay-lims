# Model and interpretation

I use compartments as well-mixed places where drug can move. The central compartment represents circulating encapsulated drug. The other compartments are abstract exchange pools, not measured organs or a validated tumour model. Loss from central combines processes such as carrier removal and release that this concentration curve cannot distinguish.

## Equations and units

For one, two or three compartments, let A be amounts in mg, V volumes in L, CL central clearance in L/h, and Q intercompartment clearances in L/h. Rates use hours:

```
C_i = A_i / V_i
 dA_1/dt = input - CL*C_1 - sum(Q_j*(C_1-C_j))
 dA_j/dt = Q_j*(C_1-C_j), j > 1
 dE/dt = CL*C_1
```

E is cumulative eliminated mass. The simulator integrates E as an extra state, so `sum(A)+E` must equal delivered dose. Concentration mg/L is numerically identical to µg/mL. Q is bidirectional clearance; its corresponding rate constants Q/V differ when volumes differ.

A bolus puts all dose in central at t=0. A finite infusion starts with zero drug and adds dose/duration mg/h until its stop time. I split integration exactly at the infusion end so an adaptive solver cannot step across a discontinuity unnoticed. Every simulation starts at dose time t=0 even if the requested samples start later. `ode45` uses relative tolerance 1e-7 and absolute tolerance 1e-9. No absorption, nonlinear clearance, repeated dosing or distinct free-drug species is implemented.

## Published-data fit

The example uses six digitized group means from [Li et al. (2022), Figure 3A](https://doi.org/10.3389/fonc.2022.1070001). See [data provenance](../data/README.md) for extraction, units, licensing and uncertainty. The infusion is 1.5 h and dose is 50 mg per m² of body surface area. I use an effective 1 m² reference: example volumes and clearances therefore have per-m² interpretation. I do not assign the mean patient a guessed body size.

`pk_fit` minimizes `sum((log(C_pred)-log(C_obs)).^2)` with base-Octave `fminsearch`. This is least squares on log concentrations, giving relative rather than absolute differences similar influence. All fitted parameters are optimized in log space so they remain positive. Three deterministic starting points reduce dependence on one initial guess; the result includes objective values, residuals, physical-unit RMSE, and optimizer exit status. Failed integrations or extreme trials get a finite penalty. This does not prove a global optimum or provide parameter confidence intervals.

For the one-compartment example I fit CL and central volume. For the two- and three-compartment examples I also fit only CL and central volume, holding peripheral volumes and exchange clearances at the explicitly assumed values in `pk_parameters`. Six rounded mean points cannot reliably identify every exchange parameter. The resulting curves are **conditional fits**, not evidence that one architecture is biologically correct. All three fits share the same two free parameters and observations. Do not compare their error as a clinical model-selection test. The library also lets a caller fit selected Q and peripheral volumes when suitable data exist.

## Sensitivity

`pk_sensitivity` perturbs each requested positive parameter by ±1% by default and computes the central finite difference in log C divided by the difference in log parameter. This dimensionless elasticity approximates fractional concentration change per fractional parameter change. It is a local calculation, not a global ranking, and is undefined at zero concentration (returned as NaN). The plot begins after infusion starts to avoid that case.

## Monte Carlo variability

`pk_monte_carlo` makes independent lognormal draws centred at the supplied parameter **medians**, with an assumed coefficient of variation (CV, standard deviation divided by mean). Log standard deviation is `sqrt(log(1+CV^2))`. A zero CV reproduces the original model. The example varies CL and central volume at CV=20%, uses seed 2026, and runs 200 scenarios. Neither the CV nor independence is inferred from the publication. The 5th to 95th percentile band describes those assumed scenarios, not a patient prediction interval or fit confidence interval. AUC is the trapezoidal area only over the supplied grid, not extrapolated exposure to infinity.

The function restores the caller's random-number state even on failure. Percentiles use linear interpolation between ordered draws, without a statistics package.

## Validation

I check one-compartment curves against closed-form bolus and infusion solutions, two/three-compartment curves against independent matrix exponentials, and conservation of delivered mass including elimination. Fit tests recover known parameters from generated observations and reduce residual error on the cited curve. Analysis tests compare sensitivity with an analytic derivative and check seeded repeatability and zero-variability collapse. Tests use Octave `%!test` blocks because this execution environment does not supply MATLAB's `matlab.unittest` framework. The library uses MATLAB-language function syntax; it has been executed in GNU Octave, not certified against MathWorks MATLAB.

This is an educational and research exploration tool. It is not suitable for selecting treatment or predicting an individual's response.
