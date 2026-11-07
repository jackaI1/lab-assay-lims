# selenium-test-harness

I built a tool that uses a web browser to test a practice power supply to learn how the underlying idea works. This is a learning project.

I use a simulated power supply and generated readings for the browser checks.

## Try a three-point check

I run this on macOS and Linux with Python 3.11 or newer, [uv](https://docs.astral.sh/uv/getting-started/installation/) to install the Python packages, and Google Chrome. No device, account, or running web service is needed.

```sh
uv sync --frozen --extra dev
uv run instrument-sweep --output results/sweep.json
```

This checks 1, 3, and 5 volts across a 1,000 ohm load. The expected currents are 1, 3, and 5 milliamps. A successful run prints `PASS: 3 steps -> results/sweep.json` and exits with code 0. The report contains each setting, reading, limit, and result. Add `--headed` to watch Chrome operate the controls.

I can also check the failure path:

```sh
uv run instrument-sweep --fault timeout --output results/timeout.json
```

This deliberately fails with exit code 1. It saves an `OperationTimeout` error instead of accepting a previous reading. Other fault choices are `bad-reading`, `non-finite`, `wrong-unit`, `drift`, `error`, and `stale`. The sweep turns the simulated output off before closing its browser and local server, including when a measurement fails.

## Use the library

Selenium drives the browser by clicking controls and reading the page. A page object, `SupplyPage`, keeps the page's control names in one place. `BenchSupply` provides the instrument operations, while `SweepRunner` checks measurements and writes the report.

```python
from pathlib import Path
from instrument_harness import (
    BenchSupply, Limits, Settings, SupplyPage,
    SweepRunner, SweepStep, chrome, simulator,
)

with simulator() as url, chrome() as driver:
    supply = BenchSupply(SupplyPage(driver, url, timeout=3.0))
    supply.connect()
    steps = [
        SweepStep(Settings(voltage_v=2, resistance_ohm=2000), Limits(0.99, 1.01)),
        SweepStep(Settings(voltage_v=6, resistance_ohm=2000), Limits(2.99, 3.01)),
    ]
    report = SweepRunner(supply).run(steps, Path("results/custom.json"))
    print(report["passed"])
```

| API | What I use it for |
| --- | --- |
| `Settings(voltage_v, resistance_ohm=1000)` | Validate a voltage from 0 to 12 V and resistance from 100 to 10,000 ohm. |
| `Limits(current_min_ma, current_max_ma, voltage_tolerance_v=0.01)` | Define inclusive current limits and allowed voltage error. |
| `BenchSupply.connect()` | Open the instrument page and wait for its controls. |
| `configure(settings)` | Apply settings and wait for acknowledgement. |
| `measure()` | Return a typed `Reading` with voltage, current, sequence, and settings revision. |
| `output_off()` | Disable output and require configuration before another measurement. |
| `SweepRunner.run(steps, output)` | Save a JSON report, disable output, and return the report as a dictionary. |

For individual measurements, I call `configure()` and `measure()` inside a `try` block and `output_off()` in its `finally` block. A failed operation raises `InstrumentError`, with `OperationTimeout` and `BadReading` as more specific error types. The runner catches these errors, records them, and stops; a numeric reading outside the requested limits is a `fail` and the sweep continues.

## Tests and limits

There are 5 test source files in this copy. That source count does not establish an execution result. This is a source snapshot, and running it on a new machine may need environment-specific setup.



Retained project workflows: `selenium-test-harness-tests.yml`. Their commands use this folder and their triggers use its paths.
