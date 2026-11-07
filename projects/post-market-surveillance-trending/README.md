# post-market-surveillance-trending

I built a complaint tracking and trend tool to learn how the underlying idea works. This is a learning project.

## Using my own export

The complaint CSV has one row per event, using the columns in `data/complaints.csv`. Dates are ISO dates, yes/no fields accept `yes`, `no`, `1` or `0`, and IDs must be unique. Exposure has one row per family and month with positive units, including months without complaints. I use the first three months as a fixed baseline and need at least one baseline complaint and one later month. `data/hazards.csv` links each hazard ID to a hazard, harm and risk-file reference. Missing exposure or hazard links stop the report instead of silently distorting it.

I can also collect the same fields in REDCap, a research data capture system, and export them directly through its API. Create a project from `data/redcap_dictionary.csv`, add synthetic records, and enable API export for the project user. Set `REDCAP_API_URL` to the HTTPS API endpoint and `REDCAP_API_TOKEN` to that user's token in the environment, then replace `--complaints data/complaints.csv` with `--redcap` in the command above. Keep the token out of files and version control. The API user should have access to all relevant records; incomplete exports lead to misleading rates. The included test mocks the API, so no REDCap account is needed to run the tests.

## Tests and limits

There are 1 test source files in this copy. That source count does not establish an execution result. This is a source snapshot, and running it on a new machine may need environment-specific setup.



Retained project workflows: `post-market-surveillance-trending-test.yml`. Their commands use this folder and their triggers use its paths.
