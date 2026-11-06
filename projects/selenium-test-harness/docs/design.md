# Instrument control and result format

I split the library into three layers so changing a web control does not require rewriting a test procedure.

| File | Responsibility |
| --- | --- |
| `src/instrument_harness/page.py` | Selenium selectors, clicks, explicit waits, raw readouts, simulator fault selection. |
| `src/instrument_harness/instrument.py` | Typed operations, configured-state checks, finite numbers, units, settings revision. |
| `src/instrument_harness/models.py` | Immutable settings, readings, limits, and instrument error classes. |
| `src/instrument_harness/runner.py` | Sweep execution, limit evaluation, output shutdown, atomic JSON reports. |
| `src/instrument_harness/simulator.py` and `web/index.html` | Packaged local page with delayed acknowledgements and controllable failures. |
| `src/instrument_harness/browser.py` | Isolated Chrome profile and guaranteed driver shutdown. |

## Measurement handshake

The simulator starts with output off. Applying settings disables controls until the simulated settling period ends, then increments `data-revision` and enables output. A measurement disables controls until a sample arrives. The sample increments `data-sequence` and stores `data-reading-revision`. The page object waits for both a new sequence and `Ready` status. The instrument then verifies the reading revision matches its applied settings.

The timeout and stale faults deliberately break different parts of that handshake: timeout stays busy forever, while stale returns to `Ready` without advancing the sequence. Neither can be mistaken for a valid sample. The output-off button cancels pending simulator work, allowing a new sweep after a failure.

The only fixed delays are inside the simulator to imitate an asynchronous device. The client uses `WebDriverWait`, with a configurable deadline and 50 ms polling, and no implicit wait. A real device needs its own page object and equivalent acknowledgement rules.

## JSON schema, version 1

The CLI writes a report to `results/sweep.json` by default. These are the main fields:

| Field | Meaning |
| --- | --- |
| `schema_version`, `run_id` | Format version and unique identifier. |
| `started_at`, `finished_at` | UTC ISO timestamps for the run. |
| `units` | Voltage in V, current in mA, resistance in ohm. |
| `planned_steps`, `steps` | Requested count and completed or attempted step records. |
| `passed` | True only if all planned steps passed and shutdown succeeded. |
| `shutdown_error` | Null on success, otherwise the shutdown error type and message. |

Each step contains `index`, `started_at`, `duration_s`, `settings`, `limits`, `reading`, `status`, `violations`, and `error`. A reading includes `voltage_v`, `current_ma`, `sequence`, and `revision`. A status is `pass`, `fail` for a limit violation, or `error` for an operation that cannot produce a valid reading. An error record stores `type` and `message`; it has no fabricated reading.

I retain failed numeric readings because they help explain an out-of-limit result. Operational errors stop the sweep before the next configuration. On every exit from a started sweep, the runner attempts output shutdown. A shutdown error is retained separately and prevents a passing run. Report-writing errors propagate to the caller after shutdown is attempted. Empty sweep plans are rejected before operating the instrument.

Each write uses a temporary file in the destination directory followed by `os.replace`. Strict JSON serialization rejects NaN and infinity. The report is replaced after every step and finalized after shutdown. If a process is forcibly terminated between steps, an earlier report remains marked incomplete (`passed: false`); Python cleanup cannot protect against forced termination or a machine losing power.

## Local resources

The simulator binds to `127.0.0.1` on an ephemeral port and serves only its packaged HTML, never the repository directory. Its context manager shuts down the server, closes its socket, and joins its serving thread. Chrome uses a temporary user-data directory and `driver.quit()` in a `finally` block. It does not connect to an existing browser profile. The optional local resource ledger records the exact driver PID, browser PID, process start, port, profile, and cleanup method for each session.

The browser test fixture owns one Chrome session and one page, resets that page for each test, disables output in test teardown, and closes the session at the end of pytest. CI retains reports as artifacts for inspection.
