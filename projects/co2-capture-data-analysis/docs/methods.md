# Calculations, checks and limits

## Gas balance

I use the ideal-gas law to convert total volumetric flow to molar flow. With pressure `P` in kPa, temperature `T` in K, total flow `F` in mL/min and concentration `c` in ppm:

```text
CO2 rate (mmol/s) = F * c * P / (60 * 1,000,000 * R * T)
R = 8.314462618 L kPa / (mol K)
captured_mmol = integral(inlet_rate - outlet_rate) dt
capacity_mmol_g = captured_mmol / dry_sample_mass_g
```

I use the trapezoid rule on the original timestamps, including nonuniform spacing and variable flow. Inlet concentration is constant per run; outlet concentration is measured. By default I use inlet flow for both rates, a dilute-feed approximation. `separate_outlet_flow` uses an independently measured outlet flow instead. Both streams must share the configured temperature and pressure basis.

Integration uses raw readings. Smoothing or clipping an overshoot can bias capacity, so negative readings and outlet values above the inlet are retained and flagged. Negative net capture is also flagged. Inlet and outlet integrated inventories are reported independently, along with `inlet - outlet - captured`. The mass-balance tests check this residual and compare inventories with analytic answers. A small residual verifies numerical bookkeeping; it does not validate the physical measurements.

This is the apparent net CO2 inventory change during the **recorded window**. I do not extrapolate a tail, subtract gas holdup, correct a sensor's transport delay, estimate a baseline or infer water uptake. For intrinsic sorbent capacity, I need calibrated dry-gas readings, correct mass, full feed exposure including the initial period, and an appropriate blank/void-volume correction before interpreting the result. A short recording gives a partial integral even if the file parses successfully. Calibration, leak checks, uncertainty estimates and blank correction remain experimental responsibilities.

## Breakthrough and the mass-transfer zone

I divide outlet concentration by inlet concentration. Thresholds use an edge-padded running median of 5 samples by default. I linearly interpolate the first upward crossing followed by at least 3 samples at or above the threshold. Both settings are configurable; `median_window=1, sustain_points=1` gives crossings on raw data. The filter affects thresholds only, never the capacity integral. This sample-count filter depends on acquisition rate, so I use the same rate and settings when comparing experiments.

`t05_s`, `t50_s`, and `t95_s` are the measured clock times at 5%, 50% and 95%. If acquisition begins above a threshold, it is left-censored and stays blank. If a sustained crossing is not observed before acquisition stops, it also stays blank. `starts_above_t05`, `t05_unobserved` and `saturation_unobserved` make these cases visible. A configurable gap limit flags sparse acquisition.

`mtz_width_s = t95 - t05` is the temporal spread of the transition front, often called the mass-transfer zone. If I supply bed length, I also report:

```text
mtz_length_proxy_cm = bed_length_cm * (t95 - t05) / (t95 - window_start)
```

This is a constant-pattern spatial proxy, not an independently measured zone length. It assumes feed exposure begins at the first timestamp, a front travelling at approximately constant speed, comparable conditions and a meaningful saturation time. Variable-flow runs still get a temporal width, but I do not interpret the spatial proxy as a mechanistic result without those assumptions. Missing threshold times leave both metrics blank.

## Electrochemical integration

For each labelled charge/discharge branch I integrate current against time. A second of one ampere is one coulomb, and `Q_mAh = Q_coulombs / 3.6`. Branches are integrated separately, so a rest or a switch between phases does not invent charge across that gap. The input must include each branch's endpoints. I do not connect the end of one cycle to the start of the next.

For voltage sweeps I integrate positive current as charge and the absolute negative current as discharge. Current is piecewise linear between measured samples. When its sign changes between samples I split the interval at the interpolated zero before integrating the two triangles. This avoids double-counting charge at coarse sample rates. Time is mandatory; I do not assume a constant sweep rate. These CV values include capacitive, faradaic and leakage currents unless the input has already been corrected. They are integrated charge equivalents, not a separation of battery storage from background current.

```text
coulombic_efficiency_pct = 100 * discharge_mAh / charge_mAh
retention_pct = 100 * discharge_mAh / first_usable_cycle_discharge_mAh
```

I do not cap efficiency at 100%. That value can be meaningful or indicate calibration, baseline or side-reaction problems. On CV files it is a signed-current charge-balance ratio, not proof of battery cycling reversibility. The same voltage range, rate and mass basis are needed for meaningful comparisons.

A complete charge/discharge cycle has both contiguous branches in order and reaches the configured voltage cutoffs at both ends, within the default 0.02 V tolerance. A complete voltage sweep starts at a configured limit, visits the other limit, and returns to its starting limit with one monotone branch each way. Excursions beyond the limits flag an incomplete cycle. Missing branches, nonclosing sweeps, multiple reversals, or single-point branches also flag it. Cycles with no positive charge or no negative charge have `missing_capacity`. I leave their partial charge values visible but suppress efficiency and retention for incomplete cycles, gaps or missing capacity.

The first complete, non-gapped cycle with positive charge and discharge sets the retention baseline. `capacity_drift` means the usable discharge capacity differs from that baseline by more than the configured fraction (default 10%), in either direction. This is a screening rule, not a statistical diagnosis or an instrument-offset correction. Missing cycle numbers get a separate flag and do not establish a baseline. Instrument drift, material fading and changed test conditions require further investigation.

## Synthetic measurements

`co2-analyze demo` writes original synthetic CSVs with `numpy.random.default_rng(42)` by default. `truth.json` records the seed, ideal reference values and noise parameters. No experimental or personal records are used.

| Signal | Ideal model | Added independent Gaussian noise |
| --- | --- | --- |
| Outlet CO2 | `inlet / (1 + exp(-(t - 600)/60))`, 10,000 ppm inlet, 0 to 1,200 s every 2 s | 30 ppm standard deviation |
| Inlet flow | 100 mL/min | 0.5% relative standard deviation |
| Charge/discharge | +0.1 A then -0.1 A; linear 0 to 1 to 0 V | 0.2% relative current standard deviation |
| CV | Triangular 0 to 1 to 0 V over 100 s, +/-0.2 A, zero at turnaround | 0.0004 A standard deviation |

Noise has zero mean. There is no clipping, correlated noise, voltage noise, baseline correction or injected missing row. Cycle 2 has 20% lower charge: the charge/discharge duration is reduced, while CV current amplitude is reduced. Cycle 3 stops partway through its return branch. These are deliberate known faults. The symmetric noiseless breakthrough integral equals the inlet molar rate times 600 seconds; thresholds are `600 + 60 * log(p / (1-p))`. The tests compare against these independent reference values and against simpler exact cases.

## Validation and references

`tests/test_breakthrough.py` checks analytic linear uptake, variable and separate stream flows, mass conservation, thresholds, raw-noise integration and invalid measurements. `tests/test_cycling.py` checks known constant-current capacities, first-valid-cycle retention, exact zero crossings, two CV directions, gaps and incomplete cycles. `tests/test_batch.py` invokes the real CLI, checks seeded accuracy, validates manifests, handles one bad run, protects existing outputs and forces plot-write failures to verify figures close.

I used [Micromeritics' breakthrough-analysis explanation](https://micromeritics.com/resources/sample-preparation-for-breakthrough-analysis/) for the experimental context and [Shao et al.'s adsorption study](https://advanced.onlinelibrary.wiley.com/doi/10.1002/advs.76487) for the 5%, 50% and 95% descriptors. [BioLogic's measurement overview](https://www.biologic.net/topics/data-of-interest-getting-the-most-out-of-your-blue-box/) describes capacity and efficiency tracking; [Rodrigues' discussion of coulombic efficiency](https://arxiv.org/abs/2209.07291) explains why efficiency and retention alone do not establish cell lifetime. The equations and tests above state the exact conventions used here.
