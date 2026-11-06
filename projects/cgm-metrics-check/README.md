# cgm-metrics-check

I built a glucose-data checker to learn how the underlying idea works. This is a learning project.

## What the public example shows

I downloaded one anonymized glucose series from CGMacros, kept its publisher-shifted timestamps and glucose values, and added its documented unit. I did not retain demographics, meals or photos. No substitute dataset was needed.

These rounded results come from `python scripts/reproduce.py`; JSON metric values retain ten decimal places for reproducibility across Python versions:

| Example | Accepted / expected readings | Coverage | Time in range |
| --- | --- | --- | --- |
| Published processed series | 14,730 / 20,160 | 73.07% | 99.13% |
| Deliberately damaged copy | 11,729 / 20,160 | 58.18% | Refused |

I made the damaged copy by removing a block, converting some values to a different declared unit, adding repeated rows and adding a conflicting value at an existing timestamp. It is a demonstration of the checker, not a finding about the study. The original extract stays unchanged.

## How I calculate the summary

I count expected timestamps across the requested window, including missing time before the first reading and after the last. The start is included and the end is excluded. Each timestamp counts at most once. Identical duplicate values count once; conflicting values exclude the entire timestamp. Off-grid readings are rejected instead of silently resampled. I never fill gaps.

The normal report requires at least fourteen days and the consensus minimum of 70% available readings. The explicitly named `--allow-short-window` option exists for exploratory examples; it never lowers the coverage requirement. Daily coverage and every missing run are included because an overall percentage can hide uneven collection.

The report includes these calculations:

- Time in range: 70 through 180 mg/dL, including both boundaries.
- Time below and above range, with separate low bands split at 54 mg/dL and high bands split at 250 mg/dL.
- Mean glucose, the arithmetic average of accepted readings in mg/dL.
- Glucose management indicator (GMI), an estimate calculated as `3.31 + 0.02392 × mean glucose`. It is not a laboratory A1C result.
- Coefficient of variation (CV), the population standard deviation divided by the mean, expressed as a percentage.

Time percentages describe accepted readings on the fixed sampling grid. They do not assume missing time was in range. Explicit mixed units are flagged and converted for calculation, while exports retain the source units. A mislabeled value cannot reliably be detected from its magnitude alone. The policy and formula constants are printed by `python scripts/reproduce.py`; [design notes](docs/design.md) explain the choices and limitations.

## Data and references

- Gutierrez-Osuna, Kerr, Mortazavi and Das: [CGMacros on PhysioNet](https://physionet.org/content/cgmacros/1.0.0/), [dataset DOI](https://doi.org/10.13026/3z8q-x658). The source provides processed minute-resolution values; upstream filling and original sensor outages cannot be audited from this file. Its timezone is unspecified. I attach a disclosed UTC placeholder to the shifted dates to preserve relative intervals, not to claim actual UTC collection times.
- Goldberger et al.: [PhysioBank, PhysioToolkit, and PhysioNet](https://doi.org/10.1161/01.CIR.101.23.e215), the source platform's requested citation.
- Battelino et al.: [International Consensus on Time in Range](https://pmc.ncbi.nlm.nih.gov/articles/PMC6973648/), for ranges, coverage and collection duration. I implement the general glucose bands, without setting individual clinical targets.
- Bergenstal et al.: [Glucose Management Indicator](https://pmc.ncbi.nlm.nih.gov/articles/PMC6196826/), for the GMI equation.
- HL7: [FHIR R4 Observation](https://hl7.org/fhir/R4/observation.html) and [Quantity units](https://hl7.org/fhir/R4/datatypes.html#Quantity). Exports use the core resource structure and UCUM unit codes, not a claim of clinical profile certification.

The [data notes](data/README.md) and [provenance manifest](data/provenance.json) identify the selected archive member, transformations and checksums. Code is MIT licensed. The extract and derived study reports retain [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/), including its noncommercial restriction.

To fetch the extract again, install the optional downloader and run:

```sh
python -m pip install -e '.[fetch]'
python scripts/fetch_public_data.py
python scripts/reproduce.py
```

The downloader retrieves just the selected CSV using archive byte ranges and checks its pinned hash. Report generation and tests work offline from the committed extract.

## Tests and limits

There are 3 test source files in this copy. No test pass count is claimed here: I have not re-run the project suite as part of this move. This is a source snapshot, and running it on a new machine may need environment-specific setup.


Project checks run from this directory through the path-filtered hub workflows: `cgm-metrics-check-ci.yml`.

Generated output omitted from this copy: reports/ (generated output). Regenerate it with the project scripts.
