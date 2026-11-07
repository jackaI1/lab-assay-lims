# selenium-test-harness

I built a tool that uses a web browser to test a practice power supply to learn how the underlying idea works. This is a learning project.

I use a simulated power supply and generated readings for the browser checks.

## Use the library

Selenium drives the browser by clicking controls and reading the page. A page object, `SupplyPage`, keeps the page's control names in one place. `BenchSupply` provides the instrument operations, while `SweepRunner` checks measurements and writes the report.

```python
from pathlib import Path
from instrument_harness import (
    BenchSupply, Limits, Settings, SupplyPage,
    SweepRunner, SweepStep, chrome, simulator,
)

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
