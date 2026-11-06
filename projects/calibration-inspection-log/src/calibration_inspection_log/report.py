"""Generate a dated Excel snapshot. SQLite remains the editable source of truth."""

import os
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .rules import USABLE, parse_date

EQUIPMENT_COLUMNS = [
    ("Instrument", "id"),
    ("Type", "kind"),
    ("Serial", "serial"),
    ("Unit", "unit"),
    ("Calibration date", "calibration_date"),
    ("Due date", "due_date"),
    ("Status", "status"),
    ("Days overdue", "days_overdue"),
    ("Calibration certificate", "calibration_certificate"),
]
READING_COLUMNS = [
    ("Receipt", "receipt"),
    ("Part", "part"),
    ("Drawing", "drawing"),
    ("Revision", "revision"),
    ("Lot", "lot"),
    ("Inspection date", "inspected_on"),
    ("Supplier", "supplier"),
    ("Purchase order", "purchase_order"),
    ("Supplier certificate", "supplier_certificate"),
    ("Sample", "sample"),
    ("Feature", "feature"),
    ("Instrument", "instrument"),
    ("Unit", "unit"),
    ("Lower limit", "lower_limit"),
    ("Measured", "measured"),
    ("Upper limit", "upper_limit"),
    ("Dimension result", "dimension_result"),
    ("Equipment status", "equipment_status"),
    ("Disposition", "disposition"),
    ("Defect type", "defect_type"),
    ("Calibration certificate", "calibration_certificate"),
]
DATE_FIELDS = {"calibration_date", "due_date", "inspected_on"}
NUMBER_FIELDS = {"measured", "lower_limit", "upper_limit"}


def _sheet(book, name, columns, rows, note, database, target):
    sheet = book.create_sheet(name)
    sheet.append([name])
    sheet["A1"].font = Font(name="Arial", size=18, bold=True, color="17365D")
    sheet.append([note])
    sheet["A2"].font = Font(name="Arial", size=11, color="555555")
    sheet.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(columns))
    sheet["A2"].alignment = Alignment(wrap_text=True, vertical="top")
    sheet.row_dimensions[2].height = 44
    sheet.append([])
    sheet.append([label for label, key in columns])
    for row in rows:
        sheet.append([None] * len(columns))
        for index, (_, key) in enumerate(columns, 1):
            value = row.get(key)
            cell = sheet.cell(sheet.max_row, index)
            if value is not None and key in DATE_FIELDS:
                value = parse_date(value)
                cell.number_format = "yyyy-mm-dd"
            elif value is not None and key in NUMBER_FIELDS:
                value = float(value)
                cell.number_format = "0.######"
            elif key == "share":
                cell.number_format = "0.0%"
            cell.value = value
            cell.font = Font(name="Arial", size=11)
            if isinstance(value, str):
                # Strings beginning with '=' must remain literal text in Excel.
                cell.data_type = "s"
            if value and key.endswith("certificate"):
                if urlsplit(value).scheme in ("http", "https"):
                    cell.hyperlink = value
                elif not urlsplit(value).scheme:
                    cell.hyperlink = os.path.relpath(database.parent / value, target.parent)
                if cell.hyperlink:
                    cell.font = Font(name="Arial", size=11, color="0563C1", underline="single")
            if value in ("NONCONFORMING", "HOLD", "OVERDUE", "OUT_OF_TOLERANCE", "UNCALIBRATED"):
                cell.fill = PatternFill("solid", fgColor="FCE4D6")
                cell.font = Font(name="Arial", size=11, color="9C0006")
    for cell in sheet[4]:
        cell.fill = PatternFill("solid", fgColor="17365D")
        cell.font = Font(name="Arial", size=11, color="FFFFFF", bold=True)
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    sheet.row_dimensions[4].height = 32
    for index, (label, _) in enumerate(columns, 1):
        width = max(
            len(label) + 2,
            min(
                38,
                max(
                    (
                        len(str(sheet.cell(row, index).value or ""))
                        for row in range(5, sheet.max_row + 1)
                    ),
                    default=12,
                )
                + 2,
            ),
        )
        if columns[index - 1][1] in {"status", "equipment_status", "disposition", "result"}:
            width = max(width, 26)
        sheet.column_dimensions[get_column_letter(index)].width = width + 3
    for row in sheet.iter_rows(min_row=5):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
        sheet.row_dimensions[row[0].row].height = 32
    sheet.freeze_panes = "C5" if len(columns) > 10 else "A5"
    sheet.auto_filter.ref = f"A4:{get_column_letter(len(columns))}{sheet.max_row}"
    sheet.sheet_view.showGridLines = False
    sheet.print_title_rows = "1:4"
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.page_setup.orientation = "landscape"
    sheet.page_setup.paperSize = sheet.PAPERSIZE_A3 if len(columns) > 10 else sheet.PAPERSIZE_A4
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    sheet.print_options.horizontalCentered = True
    sheet.print_area = f"A1:{get_column_letter(len(columns))}{max(5, sheet.max_row)}"
    return sheet


def export_report(log, target, as_of, warning_days=30):
    """Write a new .xlsx, refusing to replace any existing file."""
    target, as_of = Path(target).resolve(), parse_date(as_of).isoformat()
    if target == log.path.resolve() or target.suffix.lower() != ".xlsx":
        raise ValueError("Report must be a new .xlsx file, separate from the database")
    if target.exists():
        raise FileExistsError(f"Report already exists: {target}")
    equipment = log.instruments(as_of, warning_days)
    receiving = log.receiving(as_of)
    readings = [row for row in receiving if row["measurement_id"] is not None]
    defects = [row for row in readings if row["dimension_result"] != "PASS"]
    nonconforming = [row for row in readings if row["disposition"] != "PASS"]
    overdue = [row for row in equipment if (row["days_overdue"] or 0) > 0]
    actions = [row for row in equipment if row["status"] != "CURRENT"]
    counts = Counter(row["defect_type"] for row in defects)
    pareto, running = [], 0
    for category, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0])):
        running += count
        pareto.append({"category": category, "count": count, "share": running / len(defects)})
    summary = [
        ("As of", as_of),
        ("Instruments", len(equipment)),
        ("Overdue calibrations", len(overdue)),
        ("Recalibration actions", len(actions)),
        ("Receipts", len({r["receipt"] for r in receiving})),
        ("Receipts without readings", sum(r["measurement_id"] is None for r in receiving)),
        ("Measured dimensions", len(readings)),
        ("Dimension defects", len(defects)),
        ("Equipment holds", sum(r["equipment_status"] not in USABLE for r in readings)),
        ("Nonconformance rows", len(nonconforming)),
    ]
    book = Workbook()
    book.properties.creator = "Jack Lai"
    book.remove(book.active)

    def add(name, columns, rows, note):
        return _sheet(book, name, columns, rows, note, log.path.resolve(), target)

    add(
        "Summary",
        [("Measure", "label"), ("Value", "value")],
        [{"label": label, "value": value} for label, value in summary],
        f"As of {as_of}. Snapshot of recorded checks, not approval to release a lot.",
    )
    add(
        "Overdue calibrations",
        EQUIPMENT_COLUMNS,
        overdue,
        f"As of {as_of}. Due dates before this date, including failed instruments.",
    )
    add(
        "Recalibration actions",
        EQUIPMENT_COLUMNS,
        actions,
        f"As of {as_of}. Due within {warning_days} days, failed or uncalibrated equipment.",
    )
    add(
        "Nonconformances",
        READING_COLUMNS,
        nonconforming,
        f"Through {as_of}. Dimensional failures and equipment holds require review.",
    )
    chart_sheet = add(
        "Defect Pareto",
        [("Defect type", "category"), ("Count", "count"), ("Cumulative share", "share")],
        pareto,
        "Counts failing dimensions, not rejected parts. Equipment holds are excluded."
        if defects
        else "No dimensional defects in this snapshot.",
    )
    if pareto:
        bars = BarChart()
        bars.title = "Defect types and cumulative share"
        bars.y_axis.title = "Failing dimensions"
        bars.x_axis.title = None
        bars.x_axis.axPos = "b"
        bars.y_axis.axPos = "l"
        bars.y_axis.scaling.min = 0
        bars.y_axis.majorUnit = 1
        bars.add_data(
            Reference(chart_sheet, min_col=2, min_row=4, max_row=4 + len(pareto)),
            titles_from_data=True,
        )
        categories = Reference(chart_sheet, min_col=1, min_row=5, max_row=4 + len(pareto))
        bars.set_categories(categories)
        bars.legend = None
        line = LineChart()
        line.add_data(
            Reference(chart_sheet, min_col=3, min_row=4, max_row=4 + len(pareto)),
            titles_from_data=True,
        )
        line.set_categories(categories)
        line.y_axis.axId = 200
        line.y_axis.axPos = "r"
        line.y_axis.crosses = "max"
        line.y_axis.majorGridlines = None
        line.y_axis.title = "Cumulative share"
        line.y_axis.scaling.min = 0
        line.y_axis.scaling.max = 1
        line.y_axis.numFmt = "0%"
        bars.y_axis.crosses = "autoZero"
        bars += line
        bars.width, bars.height = 24, 13
        chart_sheet.add_chart(bars, "E4")
        chart_sheet.print_area = f"A1:S{max(31, len(pareto) + 4)}"
    add(
        "Receiving log",
        READING_COLUMNS,
        receiving,
        f"Through {as_of}. PASS covers one dimension. NOT_INSPECTED has no readings.",
    )
    add("Instrument register", EQUIPMENT_COLUMNS, equipment, f"Calibration status as of {as_of}.")
    add(
        "Calibration history",
        [
            ("ID", "id"),
            ("Instrument", "instrument"),
            ("Calibration date", "calibration_date"),
            ("Due date", "due_date"),
            ("Result", "result"),
            ("Certificate", "certificate"),
        ],
        log.calibrations(as_of),
        f"Calibration events through {as_of}. Earlier events are retained.",
    )
    # Exclusive creation prevents accidental report or database replacement.
    with target.open("xb") as stream:
        try:
            book.save(stream)
        except BaseException:
            target.unlink(missing_ok=True)
            raise
    book.close()
    return target
