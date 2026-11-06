# Lab exercises

These exercises use invented inputs. They are not qualified methods, sterile manufacturing procedures, or evidence of physical instrument use.

## Instruments

`lab_assay/instruments.yaml` describes a fixed oscilloscope waveform and optical spectrum for PyVISA-sim. The capture sets start and stop wavelength and resolution, starts a sweep, reads both arrays, finds local maxima and compares the two largest peaks. The CSV contains the settings and summary; the JSON also retains the arrays and individual checks. Timeouts are retried twice; other VISA errors and instrument error-queue responses fail the run. The fixed simulated trace is not a model of changing resolution or wavelength settings. The REST route returns the same capture in JSON, without writing files.

`python -m lab_assay.scpi_server` starts an ephemeral loopback socket server, sweeps voltage, writes a CSV, and shuts it down. The server models a supply, a meter and a waveform query, with an error queue. The test uses PyVISA-py TCP/IP sockets and exercises an invalid command. Real instruments require device-specific commands and limits. A GPIB instrument would use a resource such as `GPIB0::5::INSTR` with a suitable VISA backend instead of the TCP resource, plus any vendor-specific configuration.

## Experiments

The design functions generate full two-level factorial, half-fraction with `time = power * pressure` (so each main effect is aliased with a two-factor interaction), and rotatable central composite designs. Runs are seeded, shuffled and replicated. Inputs are coded factors: -1 and +1 are the chosen low and high settings, and axial points extend beyond those settings. They are not actual equipment units.

The synthetic thickness model in nanometres is `100 + 12P - 5Q + 8T + 3PQ - 2P² - 3Q² - T²`, with independent normal noise of 0.5 nm and a drift of 0.02 nm per run. Uniformity is a separate synthetic response with normal noise of 0.25 percentage points. The CLI fits thickness with a quadratic response surface using statsmodels, reports type II ANOVA, a pure-error lack-of-fit test, a center-versus-corner curvature check, fitted values and residuals. The predicted maximum is a grid search within coded -1 to +1; it is not a guarantee outside this region. The effect and residual plots and raw run sheet are saved alongside the JSON. Replication is needed for pure-error testing. Fractional designs cannot separately identify aliased effects.

## Counts and monitoring

Each synthetic CSV row has a sample, the actual dilution fraction, plated volume in mL, two counts, medium and incubation. The result is the mean count divided by dilution and plated volume; for CFU/g the dilution must already represent grams of original sample per mL. Both plates must fall within 25–250 and differ by no more than 20% of their mean. An invalid result is not assigned a concentration. The explicit `--limit` is compared inclusively. The report retains source fields, criteria and a timestamped calculation event; it is a generated report, not an immutable audit database.

Monitoring records are evaluated in CSV order, by room grade and location. Counts at or above the configured alert or action level are flagged, and two consecutive flagged records at the same location trigger the repeat flag. Normal counts reset that location. The example limits are invented and are not specified USP or ISO thresholds. Medium preparation multiplies plates by volume and overage and records the supplied lot identifier. USP <61>, <62>, <1111>, <1116> and ISO 14644 have detailed scope and sampling requirements that this exercise does not implement; use approved local procedures for actual decisions.
