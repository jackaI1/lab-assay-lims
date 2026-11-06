# My bug reports

I use these fields to leave enough information to reproduce a problem before changing code. They are modelled on an Azure Boards **Bug** work item. These are Markdown records, not a claim that I have a hosted Azure Board. The matching GitHub issue form is under **New issue → Bug report**.

I move a report through **New → Active → Resolved → Closed**. Resolved means the fix is in place; Closed means its reproduction and the full test suite pass. Severity describes impact; priority describes how soon I want to fix it. I use severity 1 for unusable output or data loss, 2 for incorrect results, 3 for a broken edge case and 4 for a minor nuisance.

## Reusable template

```text
ID / Title:
Work item type: Bug
State: New | Active | Resolved | Closed
Reason:
Area path: FactoryCell / Export | CLI | Build
Iteration path: FactoryCell / next change
Assigned to:
Priority: 1-4 (1 first)
Severity: 1-4 (impact, defined above)
Found in version / commit:
Environment: OS, Python, usd-core version
Preconditions / input:
Steps to reproduce: exact commands and smallest input
Expected result:
Actual result: error text or measured output
Root cause:
Fix / resolution:
Regression test:
Acceptance criteria: observable conditions for closing
Verification: commands, counts and result
Links: fix PR, test, build run
History: New -> Active -> Resolved -> Closed, with evidence at each step
```

## FC-001: valid dimensions became infinite or zero in the saved scene

| Field | Record |
| --- | --- |
| Work item type / state | Bug / Closed |
| Reason | Fixed and regression verified |
| Area / iteration | FactoryCell / Export; initial package and pipeline |
| Assigned to | Jack Lai |
| Priority / severity | 1 / 2: incorrect scene dimensions |
| Found in | First local exporter implementation, before this change was merged |
| Environment | macOS arm64, Python 3.11.16, usd-core 26.11; also verified fixed on Python 3.12 |

**Reproduce:** install the development package and run:

```bash
python -m pytest tests/test_cell.py::test_scale_roundtrip_keeps_finite_positive_dimensions -q
```

The test exports one equipment box with width `1e40`, then another with width `1e-46`, and reads each saved scale with the actual USD reader. These are boundary probes, not realistic equipment dimensions. They expose a silent conversion problem: the first implementation accepted finite Python doubles, but converted scales to 32-bit `Gf.Vec3f` values.

**Expected:** the reopened scale stays finite, positive and equal to the requested width within a relative tolerance of `1e-12`.

**Actual before the fix:** `1e40` reopened as `inf`; `1e-46` reopened as `0.0`. The ordinary conveyor bound test also found its floor at about `-1.19e-8` m instead of zero because the scale lost precision.

**Root cause and fix:** USD's default scale operation uses single precision. I now explicitly create a double-precision scale operation and pass `Gf.Vec3d` values, matching the centre-position precision.

**Regression / acceptance:** both boundary widths survive a saved-stage round trip; the conveyor bounds are `(0, -0.4, 0)` to `(2, 0.4, 0.6)` within the test tolerances. See [the regression tests](../tests/test_cell.py).

**Verification:** the two new cases failed before the fix (`inf` and `0.0`), then passed. `bash scripts/test.sh` passes the full 33-test suite on Python 3.11 and 3.12. See the repository's [CI runs](https://github.com/jackaI1/openusd-factory-cell/actions/workflows/ci.yml) for Linux results.

**History:** New: saved-scale comparison failed during initial testing. Active: isolated the `Vec3f` conversion. Resolved: changed the scale operation and values to double precision. Closed: both regressions and the complete suite passed. All transitions occurred during this implementation, on 2026-11-05.

## FC-002: an oversized JSON integer crashed validation

| Field | Record |
| --- | --- |
| Work item type / state | Bug / Closed |
| Reason | Fixed and regression verified |
| Area / iteration | FactoryCell / CLI; initial package and pipeline |
| Assigned to | Jack Lai |
| Priority / severity | 2 / 3: malformed input caused an unhandled exception |
| Found in | First local exporter implementation, before this change was merged |
| Environment | macOS arm64, Python 3.11.16, usd-core 26.11; also verified fixed on Python 3.12 |

**Reproduce:**

```bash
python -m pytest tests/test_cell.py::test_cli_huge_integer_is_readable_and_preserves_output -q
```

The test writes a JSON layout whose first dimension is `10 ** 1000`, puts an existing file at the output path, then invokes the real command-line tool. JSON accepts this integer, but a double-precision scene value cannot represent it.

**Expected:** exit code 2 with a short numeric-validation error, no traceback, and no change to the existing output.

**Actual before the fix:** exit code 1 and `OverflowError: int too large to convert to float` from `math.isfinite`. The existing file survived, but the promised validation error did not.

**Root cause and fix:** `math.isfinite` converts Python integers to a floating-point number and can raise before returning. I catch that overflow in the vector validator and report that the numbers must be finite and representable as doubles. I also convert accepted values explicitly when creating USD vectors.

**Regression / acceptance:** the subprocess returns 2, mentions finite numbers, emits no traceback, and preserves the original output bytes. See [the CLI regression](../tests/test_cell.py).

**Verification:** the regression failed with return code 1 before the fix, then passed with code 2. The complete 33-test suite passes on both supported Python versions.

**History:** New: oversized-integer probe produced a traceback. Active: traced it to numeric conversion inside `math.isfinite`. Resolved: translated overflow into the normal validation error. Closed: the subprocess regression and full suite passed. All transitions occurred during this implementation, on 2026-11-05.
