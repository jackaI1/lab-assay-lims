# Record rules and design

I use this as a small local record tool. Its examples are synthetic and it does not replace a controlled quality-management system.

## Records

`schema.sql` defines four related tables:

| Table | What I keep |
| --- | --- |
| `instruments` | A unique asset ID and serial number, instrument type and unit |
| `calibrations` | Dated results, explicit due dates and certificate references for each instrument |
| `receipts` | Part, drawing and revision, lot, supplier, purchase order, supplier certificate and inspection date |
| `measurements` | One receipt/sample/feature reading, drawing limits, dimension result, equipment status, disposition and calibration-event reference |

Foreign keys prevent orphan readings or calibration events. Required text cannot be blank, contain control characters or exceed 1,000 characters. SQL values use bound parameters. Calibration and measurement rows are append-only, with database triggers preventing updates and deletions. This is record preservation, not tamper-proof access control: a database owner can still change the schema.

The Python files have separate responsibilities: `rules.py` compares limits and dates, `store.py` validates and saves records, `report.py` creates Excel snapshots, `cli.py` handles commands and `demo.py` creates repeatable example records. The schema has version 1; unknown schema versions are rejected.

## Dates and equipment use

Dates use `YYYY-MM-DD`, with no time zones or times of day. I enter an explicit due date rather than assuming a universal interval. The policy is:

1. Select the most recent calibration on or before the inspection or report date.
2. No eligible calibration means `UNCALIBRATED`.
3. A failed eligible calibration means `OUT_OF_TOLERANCE`, regardless of its due date.
4. A due date before the evaluation date means `OVERDUE`. The due date itself means `DUE_TODAY` and is still usable.
5. A due date within the warning window means `DUE_SOON`; otherwise it means `CURRENT`.

Same-day calibration events for one instrument are rejected because date-only records cannot determine their order. A successful later calibration restores current use, while the failed event remains in history. A failed tool with an expired due date appears in both overdue tools and recalibration actions.

For inspection, equipment status is evaluated on the receipt's inspection date and saved with the reading. Only `CURRENT`, `DUE_SOON` and `DUE_TODAY` are usable. An out-of-limit dimension is `NONCONFORMING`, even when the equipment is also unusable. An in-limit dimension with unusable equipment is `HOLD`. Both the dimension result and equipment status remain visible so one problem cannot conceal the other.

## Dimensions and defects

The operator supplies the drawing's inclusive lower and upper limits. Equal limits and negative readings are allowed, for example a signed deviation. Reversed limits, non-finite values and mixed units are rejected. There is no automatic unit conversion or rounding before comparison. Dimensions support six decimal places and absolute values below 1,000,000,000, keeping values within Excel's practical numeric precision.

An optional defect category groups out-of-limit readings. Defaults are `UNDERSIZE` and `OVERSIZE`. Passing dimensions cannot be assigned a defect category. Categories are case-sensitive, so I use consistent names.

The Pareto denominator is the number of failing dimensional readings. One part with three failing features contributes three defects. Categories sort by count descending, then alphabetically for ties. The cumulative share reaches 100%. In-range equipment holds do not enter the Pareto. Empty reports show headers and an explicit no-defects message without a misleading chart.

## Reports and documents

Excel is a snapshot, not an input form. Counts and cumulative shares are calculated in Python and saved as numbers, so they are visible without spreadsheet recalculation. The chart combines defect counts and cumulative share on separate axes. Text beginning with `=` stays text rather than becoming a formula. Certificate references are clickable HTTP/HTTPS URLs or file paths resolved relative to the database folder and made relative to the exported workbook.

`--as-of` excludes later-dated receipts and calibration events. The instrument register includes all registered assets because registration has no historical date. Inspection statuses remain the evidence captured when each reading was entered, not a reconstruction of everything known at a past timestamp. There is no separate record-entry timestamp, so a later-entered, backdated record will appear in an earlier-date report. I back up both the database and referenced documents. Links are not checked for existence or authenticity, and moving the report away from local certificates can break relative links.

## Limits and corrections

I enter calibration evidence before recording inspections. Backdated calibration entries do not recalculate existing readings. A later failed calibration also does not automatically recall earlier parts: I review earlier instrument readings and decide the affected date range myself. The log has no uncertainty budget, calibration procedure, electronic signatures, approval workflow or required-feature sampling plan.

I preserve mistaken records rather than editing their measured values. For a reinspection I create a new receipt ID, use the same part/lot and document the relationship outside this small tool. Old nonconformances stay visible; this version has no disposition closure workflow. The summary counts recorded readings, never a lot-level acceptance rate.

The intended workload is a single local operator. I avoid simultaneous writers and keep backups before changes. For a shared production system I would add controlled corrections, entry timestamps, users, required inspection plans, attachment storage and migration support before using it for release decisions.
