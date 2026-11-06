from datetime import datetime
from zipfile import ZipFile

import pytest
from openpyxl import load_workbook

from calibration_inspection_log.report import export_report
from calibration_inspection_log.store import Log


def table(sheet):
    return [
        dict(zip([cell.value for cell in sheet[4]], values, strict=True))
        for values in sheet.iter_rows(min_row=5, values_only=True)
    ]


@pytest.fixture
def report_log(tmp_path):
    with Log(tmp_path / "test.db") as log:
        for identifier, due, result in [
            ("GOOD", "2027-01-01", "PASS"),
            ("LATE", "2026-04-30", "PASS"),
            ("FAIL", "2027-01-01", "OUT_OF_TOLERANCE"),
        ]:
            log.add_instrument(identifier, "caliper", f"SN-{identifier}", "mm")
            log.calibrate(identifier, "2026-01-01", due, result, f"certs/{identifier}.pdf")
        log.add_instrument("NEW", "height_gauge", "SN-NEW", "mm")
        log.receive(
            "R1",
            "Part",
            "DWG",
            "A",
            "Lot",
            "=1+1",
            "PO-1",
            "https://example.invalid/cert.pdf",
            "2026-05-01",
        )
        for sample, value, instrument, category in [
            ("1", "11", "GOOD", "Oversize"),
            ("2", "12", "GOOD", "Oversize"),
            ("3", "8", "GOOD", "Undersize"),
            ("4", "10", "LATE", None),
            ("5", "10", "GOOD", None),
        ]:
            log.measure("R1", sample, "diameter", instrument, value, "9", "10", "mm", category)
        log.receive(
            "R2",
            "Future part",
            "DWG",
            "A",
            "Lot2",
            "Future supplier",
            "PO-2",
            "certs/future.pdf",
            "2027-01-01",
        )
        yield log


def test_report_contains_overdue_and_failed_equipment_actions(report_log, tmp_path):
    target = export_report(report_log, tmp_path / "report.xlsx", "2026-05-01")
    book = load_workbook(target)
    overdue = table(book["Overdue calibrations"])
    assert [(row["Instrument"], row["Days overdue"]) for row in overdue] == [("LATE", 1)]
    assert isinstance(overdue[0]["Due date"], datetime)
    actions = table(book["Recalibration actions"])
    assert {row["Instrument"] for row in actions} == {"FAIL", "LATE", "NEW"}


def test_nonconformances_include_holds_and_traceability(report_log, tmp_path):
    book = load_workbook(export_report(report_log, tmp_path / "report.xlsx", "2026-05-01"))
    rows = table(book["Nonconformances"])
    assert len(rows) == 4
    assert [row["Disposition"] for row in rows].count("HOLD") == 1
    assert all(row["Purchase order"] == "PO-1" for row in rows)
    assert all(row["Supplier certificate"] == "https://example.invalid/cert.pdf" for row in rows)
    assert rows[0]["Measured"] == 11
    assert book["Nonconformances"]["G5"].data_type != "f"  # supplier text, never a formula
    assert rows[0]["Supplier"] == "=1+1"


def test_pareto_is_sorted_counts_only_dimension_defects_and_ends_at_100_percent(
    report_log, tmp_path
):
    path = export_report(report_log, tmp_path / "report.xlsx", "2026-05-01")
    book = load_workbook(path, data_only=True)
    rows = table(book["Defect Pareto"])
    assert [(r["Defect type"], r["Count"]) for r in rows] == [("Oversize", 2), ("Undersize", 1)]
    assert rows[0]["Cumulative share"] == pytest.approx(2 / 3)
    assert rows[1]["Cumulative share"] == 1
    with ZipFile(path) as archive:
        chart = archive.read("xl/charts/chart1.xml").decode()
        assert "barChart" in chart and "lineChart" in chart
        assert "Defect Pareto" in chart


def test_report_does_not_include_future_receipts_or_calibrations(report_log, tmp_path):
    report_log.calibrate("GOOD", "2026-06-01", "2027-06-01", "PASS", "new.pdf")
    book = load_workbook(export_report(report_log, tmp_path / "report.xlsx", "2026-05-01"))
    assert len(table(book["Receiving log"])) == 5
    assert len(table(book["Calibration history"])) == 3
    summary = dict(book["Summary"].iter_rows(min_row=5, values_only=True))
    assert summary["Receipts"] == 1
    assert summary["Dimension defects"] == 3
    assert summary["Equipment holds"] == 1


def test_empty_report_and_pending_receipts_are_explicit(tmp_path):
    with Log(tmp_path / "empty.db") as log:
        path = export_report(log, tmp_path / "empty.xlsx", "2026-05-01")
        book = load_workbook(path)
        assert book["Defect Pareto"]["A2"].value == "No dimensional defects in this snapshot."
        assert book["Defect Pareto"].max_row == 4
        assert book["Overdue calibrations"].max_row == 4
        log.receive("R", "P", "D", "A", "L", "S", "PO", "cert.pdf", "2026-05-01")
        book = load_workbook(export_report(log, tmp_path / "pending.xlsx", "2026-05-01"))
        assert table(book["Receiving log"])[0]["Disposition"] == "NOT_INSPECTED"
        summary = dict(book["Summary"].iter_rows(min_row=5, values_only=True))
        assert summary["Receipts without readings"] == 1


def test_report_refuses_overwrite_and_does_not_destroy_database(report_log, tmp_path):
    with pytest.raises(ValueError):
        export_report(report_log, report_log.path, "2026-05-01")
    output = tmp_path / "exists.xlsx"
    output.write_bytes(b"original")
    with pytest.raises(FileExistsError):
        export_report(report_log, output, "2026-05-01")
    assert output.read_bytes() == b"original"
    assert len(report_log.instruments("2026-05-01")) == 4


def test_pareto_axes_keep_counts_left_and_percentages_right(report_log, tmp_path):
    from xml.etree import ElementTree as ET

    path = export_report(report_log, tmp_path / "axes.xlsx", "2026-05-01")
    with ZipFile(path) as archive:
        root = ET.fromstring(archive.read("xl/charts/chart1.xml"))
    ns = {"c": "http://schemas.openxmlformats.org/drawingml/2006/chart"}
    axes = {axis.find("c:axId", ns).get("val"): axis for axis in root.findall(".//c:valAx", ns)}
    assert axes["100"].find("c:axPos", ns).get("val") == "l"
    assert axes["200"].find("c:axPos", ns).get("val") == "r"
    assert axes["100"].find("c:crosses", ns).get("val") == "autoZero"
    assert axes["200"].find("c:scaling/c:max", ns).get("val") == "1"
