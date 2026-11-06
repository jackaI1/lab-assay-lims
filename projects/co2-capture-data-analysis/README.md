# Carbon capture and charge measurements

I built this to learn how to turn carbon-capture and charge-storage measurements into quantities I can compare. The demo uses synthetic measurements rather than results from a real material.

From this directory, with Python 3.10 or newer:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
co2-analyze demo demo-runs
co2-analyze batch demo-runs/manifest.json --output results
```

I use a new output directory for each run. The manifest keeps the input filenames and measurement settings together. The batch code writes summary tables, headless plots and input hashes. `src/co2_analysis/breakthrough.py` handles the gas balance, `cycling.py` handles the current measurements, and `batch.py` brings the results together.

The capture calculation integrates the difference between incoming and outgoing gas. The cycle calculations integrate current over time. These are recorded-window calculations, so they do not establish equilibrium capture capacity or material lifetime. The equations and input conventions are in [the methods](docs/methods.md) and [input guide](docs/inputs.md).

I counted 30 named test functions in the Python test sources. That is a source count, rather than a passing-test count; parametrized cases can produce a different execution count. The local commands are `ruff check .` and `pytest -q`.

## Tests and limits

There are 4 test source files in this copy. No test pass count is claimed here: I have not re-run the project suite as part of this move. This is a source snapshot, and running it on a new machine may need environment-specific setup.


Project checks run from this directory through the path-filtered hub workflows: (removed workflow).

The relocated workflow did not complete successfully within the migration batch. Local test sources remain available.
