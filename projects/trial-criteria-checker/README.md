# trial-criteria-checker

I built a clinical trial criteria checker to learn how the underlying idea works. This is a learning project.

## Try it

I use Python with only its standard library, so there are no packages or accounts to install. From a checkout of this repository:

```sh
python3 -m trial_criteria report --labels data/labels.json
```

Open `reports/fictional_patient.html`, or read `reports/fictional_patient.md`. To change the example, copy [examples/fictional_patient.json](examples/fictional_patient.json), edit the invented values, and supply its path with `--patient`. Keep `"fictional": true`; use fictional records only.

To download fresh recruiting studies and check the same fictional record:

```sh
python3 -m trial_criteria fetch --condition leukemia --limit 10 --output data/latest.json
python3 -m trial_criteria report --snapshot data/latest.json --output reports/latest
```

The fetch command calls the ClinicalTrials.gov API, a public service that returns study records as structured data. Recruitment status can change after downloading. If the service is unavailable, the checked-in snapshot still works offline; I do not silently substitute invented criteria.

## Public sources and sample

I downloaded the [ClinicalTrials.gov v2 API](https://clinicaltrials.gov/data-api/api) directly. [data/studies.json](data/studies.json) records the retrieval time, exact request URL, source identifiers, recruitment status and unchanged eligibility text. I retain only the fields this project needs, excluding contact details and unrelated study fields. I use no private systems or real patient records.

The saved sample comes from these public records: [NCT02560883](https://clinicaltrials.gov/study/NCT02560883), [NCT05011045](https://clinicaltrials.gov/study/NCT05011045), [NCT07807280](https://clinicaltrials.gov/study/NCT07807280), [NCT07524205](https://clinicaltrials.gov/study/NCT07524205) and [NCT07389005](https://clinicaltrials.gov/study/NCT07389005). The last record contains a hemoglobin threshold whose unit looks unusual. I keep its wording and unit literally rather than silently correcting the source.

I wrote the [reference labels](data/labels.json) by directly reading the complete criteria before scoring the parser. They include both reference rules and explicit unknown labels, with reasons. This is a small, selected development sample, not a random sample, a held-out test or an independently reviewed clinical benchmark. It contains no sex reference rules; sex and the other lab grammars have synthetic tests, so the sample does not establish their real-world accuracy. [Annotation notes](data/README.md) explain the choices. Creatinine unit conversion follows the [NIDDK conversion reference](https://www.niddk.nih.gov/research-funding/research-programs/kidney-clinical-research-epidemiology/laboratory/glomerular-filtration-rate-equations/adults).

## Tests and limits

There are 2 test source files in this copy. That source count does not establish an execution result. This is a source snapshot, and running it on a new machine may need environment-specific setup.



Generated output omitted from this copy: reports/ (generated output). Regenerate it with the project scripts.

The relocated workflow failed in GitHub Actions and was removed to keep the hub checks independent. Local test sources remain available.

No project-specific GitHub Actions workflow was retained. The local test sources remain in this folder.
