# calibration-inspection-log

I built a calibration and receiving-inspection log to learn how the underlying idea works. This is a learning project.

## Use my own records

I keep each instrument's unit as either `mm` or `in`. Measurements must use the same unit. Document paths are relative to the database folder, or they can be web URLs. The files stay where I store them; the database records references rather than copying attachments.

```sh
inspection-log --db quality.db init
inspection-log --db quality.db instrument \
  --id CAL-01 --kind caliper --serial EXAMPLE-001 --unit mm
inspection-log --db quality.db calibrate \
  --instrument CAL-01 --date 2026-11-01 --due 2027-11-01 \
  --result PASS --certificate certificates/CAL-01.pdf
inspection-log --db quality.db receive \
  --id RCV-001 --part SPACER-10 --drawing DWG-10 --revision B \
  --lot LOT-001 --supplier 'Example supplier' --po PO-001 \
  --certificate certificates/LOT-001.pdf --date 2026-11-05
inspection-log --db quality.db measure \
  --receipt RCV-001 --sample 1 --feature diameter --instrument CAL-01 \
  --measured 10.08 --lower 9.95 --upper 10.05 --unit mm \
  --defect-type 'Oversize diameter'
inspection-log --db quality.db status --as-of 2026-11-05
inspection-log --db quality.db report \
  --as-of 2026-11-05 --output quality-2026-11-05.xlsx
```

The measurement above returns `NONCONFORMING`. Enter each additional sample or feature with another `measure` command. `receive` alone leaves the receipt marked `NOT_INSPECTED`. A sample and feature combination can only be entered once per receipt, which catches accidental duplicates. For an in-range measurement, leave out `--defect-type`.

I use `calibrate` again after recalibration; it adds an event and keeps the earlier certificate. Use `--result OUT_OF_TOLERANCE` for a failed calibration. Due dates remain valid through the day shown, with overdue status starting the following day. `status` and `report` use today's date unless I supply `--as-of`; `--warning-days 14` changes the default 30-day warning window. `inspection-log --help` lists the commands.

Reports refuse to overwrite existing files. To refresh a report, I export to a new filename. Editing Excel does not change the database. I keep real databases, certificates and reports out of this public repository.

## How I put it together

The Python command-line tool stores records in SQLite, a database held in one local file. It needs no server or account. I store measurements as decimal text and compare them with Python's decimal arithmetic so binary rounding cannot change a boundary result. Inputs support six decimal places and magnitudes below one billion; Excel receives sortable numeric measurements and real date cells.

Each reading saves the calibration event and equipment status used when I entered it. Recalibration does not silently rewrite old inspection results. The Excel exporter uses openpyxl to make eight sheets with filters, frozen headings, certificate hyperlinks, highlighted problems and a bar-and-line Pareto chart. Defect counts represent failing dimensions, not rejected parts. Equipment holds are reported separately.

[Record rules and limitations](docs/design.md) explains historical cutoffs, corrections and the database structure. [Demo walkthrough](examples/README.md) lists the expected results and how to inspect the stored records.

## Tests and limits

There are 4 test source files in this copy. No test pass count is claimed here: I have not re-run the project suite as part of this move. This is a source snapshot, and running it on a new machine may need environment-specific setup.


Project checks run from this directory through the path-filtered hub workflows: (removed workflow).

The relocated workflow did not complete successfully within the migration batch. Local test sources remain available.
