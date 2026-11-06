import os
import subprocess
import sys
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    return subprocess.run(
        [sys.executable, "-m", "calibration_inspection_log", *map(str, args)],
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        text=True,
        timeout=20,
    )


def test_demo_builds_a_real_database_and_eight_sheet_workbook(tmp_path):
    output = tmp_path / "demo"
    result = run("demo", "--output", output)
    assert result.returncode == 0, result.stderr
    assert (output / "inspection.db").exists()
    book = load_workbook(output / "quality-report.xlsx", data_only=True)
    assert len(book.sheetnames) == 8
    summary = dict(book["Summary"].iter_rows(min_row=5, values_only=True))
    assert summary["Instruments"] == 6
    assert summary["Measured dimensions"] == 8
    assert summary["Dimension defects"] == 4
    assert summary["Equipment holds"] == 2
    assert summary["Receipts without readings"] == 1
    assert (output / "certificates" / "supplier.txt").read_text().startswith("SYNTHETIC")
    assert run("demo", "--output", output).returncode == 2
    assert len(load_workbook(output / "quality-report.xlsx").sheetnames) == 8


def test_real_entry_workflow_and_recalibration(tmp_path):
    database = tmp_path / "quality.db"
    commands = [
        ("init",),
        ("instrument", "--id", "CAL1", "--kind", "caliper", "--serial", "S1", "--unit", "mm"),
        (
            "calibrate",
            "--instrument",
            "CAL1",
            "--date",
            "2026-01-01",
            "--due",
            "2026-11-04",
            "--result",
            "PASS",
            "--certificate",
            "cal.pdf",
        ),
        (
            "receive",
            "--id",
            "R1",
            "--part",
            "P1",
            "--drawing",
            "D1",
            "--revision",
            "A",
            "--lot",
            "L1",
            "--supplier",
            "Example",
            "--po",
            "PO1",
            "--certificate",
            "supplier.pdf",
            "--date",
            "2026-11-05",
        ),
        (
            "measure",
            "--receipt",
            "R1",
            "--sample",
            "1",
            "--feature",
            "diameter",
            "--instrument",
            "CAL1",
            "--measured",
            "10",
            "--lower",
            "9.95",
            "--upper",
            "10.05",
            "--unit",
            "mm",
        ),
    ]
    for command in commands:
        result = run("--db", database, *command)
        assert result.returncode == 0, result.stderr
    assert "HOLD" in result.stdout
    assert "OVERDUE" in run("--db", database, "status", "--as-of", "2026-11-05").stdout
    result = run(
        "--db",
        database,
        "calibrate",
        "--instrument",
        "CAL1",
        "--date",
        "2026-11-06",
        "--due",
        "2027-11-06",
        "--result",
        "PASS",
        "--certificate",
        "new.pdf",
    )
    assert result.returncode == 0, result.stderr
    assert "CURRENT" in run("--db", database, "status", "--as-of", "2026-11-06").stdout
    target = tmp_path / "report.xlsx"
    assert (
        run("--db", database, "report", "--as-of", "2026-11-06", "--output", target).returncode == 0
    )
    assert load_workbook(target)["Nonconformances"]["S5"].value == "HOLD"


def test_bad_input_returns_clean_error_and_does_not_create_missing_database(tmp_path):
    path = tmp_path / "missing.db"
    result = run("--db", path, "status")
    assert result.returncode == 2
    assert not path.exists()
    assert "Traceback" not in result.stderr
    assert run("--db", path, "init").returncode == 0
    result = run("--db", path, "status", "--as-of", "2026-02-30")
    assert result.returncode == 2
    assert "Traceback" not in result.stderr


def test_report_rejects_overwrite_from_cli(tmp_path):
    database = tmp_path / "quality.db"
    assert run("--db", database, "init").returncode == 0
    target = tmp_path / "report.xlsx"
    target.write_text("keep")
    result = run("--db", database, "report", "--output", target)
    assert result.returncode == 2
    assert target.read_text() == "keep"
