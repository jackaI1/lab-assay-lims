# Health microsimulation: methods note

This note describes the dementia-style microsimulation in `lab_assay/microsim.py`. Inputs are in `data/microsim/config.json`, where each number is either cited or marked as an assumption. The model is for teaching and for trying planning questions. It is not a validated planning tool for any health system.

## What is simulated

A synthetic cohort of 20,000 people (default) is aged from 65 to 100, one year at a time. Each person is in one of five states:

| State | Meaning |
| --- | --- |
| healthy | no cognitive impairment |
| mci | mild cognitive impairment (MCI) |
| dementia | dementia, living in the community |
| ltc | dementia, in long-term care |
| dead | absorbing state |

Dementia prevalence is the share of living people in the `dementia` or `ltc` state, since people in long-term care also have dementia.

Each year, a person in state *s* dies with probability `q_s(age)`. Otherwise they move to another state or stay put. The annual non-death transition probabilities are:

- healthy to MCI, and healthy directly to dementia;
- MCI back to healthy, and MCI to dementia;
- dementia to long-term care.

Each rate is `base * exp(growth * (age - 65))`, capped at 0.95. Rates are in `config.json`. If the rates for a state together exceed 1, they are rescaled to sum to 1.

## Mortality

Background mortality is Gompertz: `q(age) = a0 * exp(slope * (age - 65))`. The slope (0.085) is an assumption. The intercept `a0` is solved so that remaining life expectancy at 65 is 21.0 years. That value is the average of the 2023 Statistics Canada figures for females (22.3) and males (19.7), reported in the Statistics Canada Daily of 9 January 2026. The model uses one sex-neutral table, which is a simplification.

State-specific mortality is `hazard_ratio[state] * q(age)`. The hazard ratios are 1.3 (MCI), 2.5 (dementia) and 3.0 (long-term care). These are assumptions and have not been checked against a specific Canadian source. The sensitivity analysis varies them.

## Calibration

Calibration sets two log-multipliers for the transition rates: one for healthy-to-MCI incidence and one for dementia onset (MCI-to-dementia and healthy-to-dementia). The fit uses `scipy.optimize.least_squares` on relative errors between simulated and target prevalence in two bands:

- ages 65 to 74, target 2.4%;
- ages 85 and over, target 34.5%.

Both targets come from the Canadian Study of Health and Aging (CSHA-1, 1991 data), as reported in Ebly et al., CMAJ 1994. The bounds on the log-multipliers are ±3.

The fit uses common random numbers (the same seed for every evaluation), so the residuals change smoothly. Individuals are discrete, so the optimizer's default finite-difference step did not move the fit. The code therefore computes the Jacobian itself with a step of 0.02.

The age shape of the rates (the `growth` values) was chosen by hand. It is steep enough for the two anchors to be reachable together. The calibration fits the level, not the shape.

## Validation

The 75-84 band is held out of calibration. Its target is **derived, not published**: prevalence doubles every five years (a secondary summary of the CSHA data), starting from the 65-74 anchor. That gives 2.4% × 2^((79.5 − 69.5)/5) ≈ 9.6%. The check passes if the simulated value is within 35% of the target (relative). With the default inputs the model gives about 11.2%, a relative error of +17%.

Validation is a check on the shape between the two anchors. It is not an independent published test.

## Sensitivity analysis

**One-way (tornado).** Each parameter moves between its low and high value, one at a time, on the same seed. The outcome is the mean number of years with dementia (dementia or long-term care) from age 65. The ranges are in `config.json`.

**Probabilistic.** Parameters are drawn from distributions: lognormal (SD 0.2 on the log scale) for the rate multipliers, and normal relative to the base value, with a floor of 1, for the hazard ratios. Each draw runs a separate cohort of 5,000 people. The report gives the median and the 2.5 to 97.5 percentile interval for years with dementia and for prevalence at 85 and over.

## Checks in the test suite

- Same seed gives the same population; a different seed does not.
- Every transition matrix row sums to 1 and is non-negative, including under stressed rates.
- Counts of living and dead people sum to the cohort size at every age, and death is absorbing.
- Calibration recovers known multipliers (1.5 and 0.8) when the targets come from a model run with those values.
- The validation band is excluded from the fitting targets.
- The life table matches the 21.0-year target.
- The command-line tool writes the report and three plots, and rejects a population below 100.

## Limitations

- The model has no sex, income, region or ethnicity; the life table is sex-neutral.
- The 85+ band is a band average. Simulated prevalence keeps rising past the band's average at the oldest ages, where few people are alive.
- Only the level of the rates is fitted. The age shape and the hazard ratios are assumptions.
- The validation target is derived, not measured.
- The model does not simulate costs or care capacity. It only counts people in each state.
- The CSHA figures are from 1991 data and may not reflect the current population.
