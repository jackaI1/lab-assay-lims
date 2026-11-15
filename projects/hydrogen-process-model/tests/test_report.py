from pathlib import Path

import pytest
from openpyxl import load_workbook

from process_model.cli import main
from process_model.report import build_report
from process_model.workbook import write_workbook


def test_every_mass_and_atom_balance_closes(assumptions):
    report = build_report(assumptions)

    assert report.max_closure_error < 1e-9


def test_workbook_has_every_sheet_and_the_summary_adds_up(assumptions, tmp_path):
    report = build_report(assumptions)
    path = write_workbook(tmp_path / "comparison.xlsx", report)

    workbook = load_workbook(path)
    assert workbook.sheetnames == [
        "Summary",
        "SMR sweep",
        "Electrolysis",
        "Mass balance",
        "Assumptions",
    ]
    summary = workbook["Summary"]
    rows = {row[0]: row for row in summary.iter_rows(min_row=2, max_row=3, values_only=True)}
    for route, cost in (("SMR", report.smr), ("Electrolysis", report.electrolysis)):
        _, _, energy, capital, om, total, _ = rows[route]
        assert total == pytest.approx(energy + capital + om, abs=1e-3)
        assert total == pytest.approx(cost.total_cost_per_kg, rel=1e-2)
    assert workbook["SMR sweep"].max_row == len(report.sweep) + 1


def test_command_line_writes_the_workbook(tmp_path):
    data = Path(__file__).resolve().parents[1] / "data" / "assumptions.toml"

    exit_code = main(["--assumptions", str(data), "--output", str(tmp_path)])

    assert exit_code == 0
    assert (tmp_path / "hydrogen_comparison.xlsx").exists()
