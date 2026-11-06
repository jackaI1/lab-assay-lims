# My example receiving check

I use `inspection-log demo --output outputs/demo` to create the same small dataset every time. All instruments, supplier records and certificates are made up. The report date is November 5, 2026.

| Instrument | Expected status |
| --- | --- |
| CAL-01 | CURRENT, with two retained calibration events |
| MIC-01 | OVERDUE by one day |
| HG-01 | OUT_OF_TOLERANCE |
| DI-01 | DUE_SOON |
| CAL-02 | DUE_TODAY |
| MIC-02 | UNCALIBRATED |

The first receipt contains eight diameter readings against 9.95 to 10.05 mm limits. Two pass, three are oversize, one is undersize and two are in range but held because their instruments are unusable. The Pareto starts with three oversize readings at 75% cumulative share and ends with one undersize reading at 100%. There are six rows in Nonconformances. The second receipt is explicitly NOT_INSPECTED.

The generated folder contains:

- `inspection.db`, the SQLite records.
- `quality-report.xlsx`, the eight-sheet review report.
- `certificates/`, clearly labelled example certificate files that the report links to.
- `purchase-order.txt`, the synthetic order associated with `PO-DEMO-001`.

I can check the instruments without opening Excel:

```sh
inspection-log --db outputs/demo/inspection.db status --as-of 2026-11-05
```

Or inspect the measurements directly with Python's built-in database library:

```sh
python - <<'PY'
import sqlite3
with sqlite3.connect('outputs/demo/inspection.db') as db:
    for row in db.execute('SELECT sample, measured, dimension_result, equipment_status, disposition '
                          'FROM measurements ORDER BY id'):
        print(row)
PY
```

I can also download the `synthetic-demo` artifact from a successful GitHub Actions run. It contains the same generated files, so I can open the report and follow local certificate links after extracting the entire folder.
