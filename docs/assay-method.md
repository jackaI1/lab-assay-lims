# Assay calculations and import contract

## Reader files

Use one endpoint measurement per well. CSV is UTF-8 (BOM allowed). XLSX must have exactly one sheet, with numeric cell values rather than formulas. Files are limited to 2 MB compressed and 10 MB expanded for XLSX.

Long format:

```csv
well,signal
A1,0.071
A2,0.072
B1,1.230
```

The two headers must be `well,signal` (case-insensitive). `A01` is normalized to `A1`, so `A01` and `A1` together are rejected as a duplicate. `NaN`, infinity, empty values, overflow labels and formulas are rejected. Negative finite reader values are permitted because some instruments export background-referenced signals.

Matrix format has a first row `,1,2,...,12`, followed by rows labelled A through H, each with twelve numeric signals. Every signal must be mapped. For a partially occupied plate, export only mapped wells in long format. Export the endpoint table from vendor software first; raw SoftMax blocks, kinetic time series and mixed metadata headers are not accepted.

The map is immutable after creation. It stores the role, sample reference, declared standard concentration and sample dilution factor. Source files are stored as bytes with a SHA-256 hash, and a duplicate file on the same plate is rejected. A failed import writes neither data nor an audit event.

## Background and fits

The background is the arithmetic mean of at least two blank wells. Subtract this mean from every reader signal. Negative corrected values are retained, not clipped.

A linear model is `y = slope * x + intercept`. It needs at least three distinct standard concentrations. A 4PL model is:

```text
y = low + (high - low) / (1 + (x / ec50)^hill)
```

Here `high` is the response at zero and `low` is the limiting response at high concentration; the names describe the usual decreasing assay and do not impose signal order. `ec50` is positive and `hill` is positive. Allowing either order of the two plateaus supports both increasing and decreasing assays. All concentrations must be nonnegative. 4PL needs at least six distinct concentrations, including at least five positive levels. All replicate standards enter an unweighted least-squares fit. Bounded fitting starts at three candidate midpoints and retains the converged fit with the smallest squared error.

R² is `1 - sum((y - fitted)^2) / sum((y - mean(y))^2)`. Constant signals and unusable standard designs are rejected. R² alone does not establish assay validity. Each standard is also flagged if its residual exceeds the larger of 20% of its predicted signal magnitude and 2% of the standard signal span. Reported standard concentrations are the assigned reference values, not sample estimates.

Unknown concentrations are obtained by inverting the fitted response. Values outside the measured concentration interval, or outside the model's response domain, are `null` with `OUT_OF_RANGE`. The interval includes zero only when it was measured as a standard. The result is multiplied by the sample's declared dilution factor. A group concentration is reported only when all its replicate wells have valid concentrations.

## Repeated wells and plate quality

CV% uses sample standard deviation (`ddof=1`) divided by absolute mean, times 100. For sample wells it uses dilution-corrected concentrations; for standards and controls it uses blank-corrected signals. It is unavailable for fewer than two values or a near-zero mean. Samples with fewer than two replicates are flagged. Standard and sample groups exceeding 20% CV are flagged.

Z-prime is `1 - 3 * (SD_positive + SD_negative) / abs(mean_positive - mean_negative)`, using sample standard deviations. At least three wells of each control type are required. Missing controls and indistinguishable means have an explicit failure flag and no Z-prime value. Z-prime below 0.5 fails.

A plate passes only if it has no plate, well or group flags. R² below 0.98, expired reagent lots (checked against analysis date), failed standard residuals, sample range failures and high replicate variation prevent a clean result. Numerical calculation failures return an explanatory validation error and do not save an analysis. These limits are fixed educational defaults, not a validated decision rule for real samples.

Each analysis is an immutable snapshot with algorithm version, thresholds, fit parameters, raw/corrected values, QC flags and the original import reference. New analyses never replace old ones. The demo also records its seed and true sample concentrations. Downloaded CSV rows include group and plate flags so an outlying result cannot lose its review context during export.

## Robot boundaries

The generated OT-2 protocols use API 2.15 and a P300 single-channel GEN2 pipette. Slots 1 and 2 hold plates or the dilution reservoir; slot 3 holds one 96-tip rack. Transfers use a fresh tip each time. Analytical plate maps are separate from physical preparation plans, and that distinction is explicit on the page.

Serial dilution with final volume `V` and factor `F` moves `T = V/(F-1)` between wells. Load the first well with `V+T` of stock and each later well with `V` diluent. Mix after each transfer and discard `T` from the last well. Every final well holds `V`, and relative concentrations are `F^-i`. The conservative working cap is 200 µL per well even though the named Corning plate has higher nominal capacity. All aspiration, dispense and mixing volumes must be within pipette bounds. Stock and diluent totals exclude reservoir dead volume, which must be added at the bench.

Plate transfers assume an initially empty destination and declared source loading. The planner tracks cumulative destination fill, source depletion and tips. It requires at least 20 µL to remain in each used source; this is a conservative planning constraint, not a measured dead volume. Up to 96 transfers fit a single tip rack.

The simulator checks API compatibility and step execution, not actual liquid presence, contamination, plate chemistry or robotic accuracy. Generated user-specific downloads require their own simulator run. CI simulates both representative generators and additional boundary plans.
