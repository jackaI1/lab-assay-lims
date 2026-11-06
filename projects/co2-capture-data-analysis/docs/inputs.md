# Input files and batch runs

I use explicit units so a file exported in milliamps cannot silently be read as amps. Convert vendor exports to these columns first. Extra columns are allowed, but required columns cannot be blank, nonnumeric or nonfinite. Column names are case sensitive. The tool does not sort rows, fill missing readings or guess a file's meaning.

## Breakthrough CSV

```csv
time_s,outlet_ppm,flow_ml_min
0,0,100
10,500,100
20,1000,100
```

This tiny file only illustrates the format; use a recording that includes the whole transition. Time must strictly increase. `flow_ml_min` is the total incoming gas volume per minute, at the temperature and pressure specified in the manifest, **not a standard-volume flow unless those reference conditions are specified**. `outlet_ppm` is CO2 mole fraction times one million. The inlet concentration is constant for one run. A varying inlet needs separate runs or a different model.

With `separate_outlet_flow: true`, also include `outlet_flow_ml_min`, at the same stated conditions. A separate flow is useful if capture changes the total flow appreciably. The tool rejects nonpositive flows. It keeps small negative concentration readings from instrument noise in the integral, flags them, and does not clip or hide them.

## Charge/discharge CSV

```csv
cycle,time_s,current_a,voltage_v,phase
1,0,0.1,0,charge
1,50,0.1,0.5,charge
1,100,0.1,1,charge
1,100,-0.09,1,discharge
1,150,-0.09,0.5,discharge
1,200,-0.09,0,discharge
```

Positive current means charging; negative means discharging. `phase` is exactly `charge`, `discharge` or `rest`. I include both endpoints of each phase. Equal times are allowed at phase boundaries to represent a current step without adding a fictitious transition charge. Otherwise times increase within a cycle. They can reset between cycles. Cycle numbers are positive integers and must appear in increasing blocks.

Each usable cycle has one contiguous charge branch followed by one contiguous discharge branch, with optional rest blocks between them. At least two readings per active branch are needed. Rest current is excluded. Repeated pulses or constant-voltage substeps must first be grouped into their continuous charge or discharge branch; the tool does not guess missing phase labels. Incorrect current signs fail the run instead of being silently flipped.

## Cyclic voltammetry CSV

```csv
cycle,time_s,current_a,voltage_v
1,0,0.1,0
1,25,0.1,0.5
1,50,0,1
1,75,-0.1,0.5
1,100,-0.1,0
```

Time is required, so the integral remains meaningful for nonuniform sweep rates. Times strictly increase within each cycle and can reset between cycles. A complete cycle sweeps from one configured voltage limit to the other and back, with one reversal. Either starting direction is accepted. The applied voltage should be the programmed, monotone sweep signal; voltage reversals from a noisy measured signal are not smoothed away. The tolerance controls endpoint comparisons, not internal reversal detection.

## Manifest

Paths resolve relative to the manifest file, regardless of the current working directory. Every run needs exactly `id`, `kind`, `file` and `options`. IDs are unique and use only letters, numbers, hyphens or underscores. Unknown calculation options produce a run error.

```json
{
  "runs": [
    {
      "id": "bed-a",
      "kind": "breakthrough",
      "file": "bed-a.csv",
      "options": {
        "inlet_ppm": 10000,
        "mass_g": 0.5,
        "temperature_k": 298.15,
        "pressure_kpa": 101.325,
        "bed_length_cm": 10,
        "median_window": 5,
        "sustain_points": 3,
        "max_gap_s": 5
      }
    },
    {
      "id": "electrode-a",
      "kind": "cycling",
      "file": "electrode-a.csv",
      "options": {
        "voltage_min_v": 0,
        "voltage_max_v": 1,
        "voltage_tolerance_v": 0.02,
        "mass_g": 0.1,
        "drift_fraction": 0.1,
        "max_gap_s": 2
      }
    }
  ]
}
```

Use `kind: "cv"` for voltage sweeps, with the same options as cycling. The voltage limits are required; set them to the experiment's intended cutoffs rather than estimating them from a possibly truncated file. `mass_g` for cycling is optional, and only enables discharge capacity per gram.

`max_gap_s` is optional. Without it, the integral spans all measured intervals without a gap flag. With it, any interval longer than the limit is flagged. It is still included in the partial integral; cycling efficiency and retention are suppressed for that cycle. Choose the limit from the acquisition schedule.

```sh
co2-analyze batch /path/to/runs/manifest.json --output results-2026-11-05
```

Exit status is 0 if every run was processed, 1 if any run failed while others continued, and 2 for invalid configuration, unreadable manifests or an existing output directory. Scientific quality flags do not mean a parsing failure: a truncated but readable run exits 0 and carries its flags in the summary.

`summary.csv` has one row per breakthrough run and one per electrochemical cycle. Columns irrelevant to a row, and results that cannot be trusted, are blank. `complete` describes whether voltage endpoints and branches were observed; inspect `flags` as well because a complete voltage path can still have a sampling gap or missing current capacity. Partial integrated charges remain visible for diagnosis. `errors.json` lists unreadable/invalid runs. `provenance.json` stores settings, versions, hashes and per-run status. PNG plots show the capture curve and flow, or voltage/current traces, integrated charge and percent trends. Red crosses identify flagged cycle capacities.

## Python use

```python
from co2_analysis import analyze_breakthrough, analyze_cycles

result, trace = analyze_breakthrough("demo-runs/adsorption.csv", inlet_ppm=10000, mass_g=0.5)
cycles, trace = analyze_cycles(
    "demo-runs/cycling.csv", kind="cycling", voltage_min_v=0, voltage_max_v=1
)
print(result["capacity_mmol_g"], cycles[0]["coulombic_efficiency_pct"])
```

These functions return ordinary metric dictionaries and NumPy trace arrays. Invalid input raises `ValueError` or `TypeError`; filesystem problems raise `OSError`. Batch processing catches these per run. Input data are loaded in memory, so I split very large campaigns into manageable batches.
