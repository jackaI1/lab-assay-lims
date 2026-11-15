"""Writes the comparison to an Excel workbook with one sheet per part of the model."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from process_model.report import Report

HEADER_FONT = Font(bold=True)


def _write_table(sheet, headers: list[str], rows: list[list[object]], formats: list[str | None]):
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = HEADER_FONT
    for row in rows:
        sheet.append(row)
    for column, number_format in enumerate(formats, start=1):
        if number_format is None:
            continue
        for row_index in range(2, len(rows) + 2):
            sheet.cell(row=row_index, column=column).number_format = number_format
    for column in range(1, len(headers) + 1):
        letters = get_column_letter(column)
        width = max(
            len(str(sheet[f"{letters}{row}"].value or "")) for row in range(1, len(rows) + 2)
        )
        sheet.column_dimensions[letters].width = min(max(12, width + 2), 40)
    sheet.freeze_panes = "A2"


def write_workbook(path: str | Path, report: Report) -> Path:
    """Save `report` as an .xlsx file at `path` and return the path."""
    path = Path(path)
    workbook = Workbook()

    summary = workbook.active
    summary.title = "Summary"
    cost_rows = [
        [
            cost.route,
            round(cost.energy_kwh_per_kg, 2),
            round(cost.energy_cost_per_kg, 3),
            round(cost.capex_cost_per_kg, 3),
            round(cost.fixed_om_cost_per_kg, 3),
            round(cost.total_cost_per_kg, 3),
            round(cost.annual_kg),
        ]
        for cost in (report.smr, report.electrolysis)
    ]
    _write_table(
        summary,
        [
            "Route",
            "Energy input (kWh per kg H2)",
            "Energy cost ($/kg)",
            "Capital ($/kg)",
            "Fixed O&M ($/kg)",
            "Total ($/kg)",
            "Annual output (kg)",
        ],
        cost_rows,
        [None, "0.00", "0.000", "0.000", "0.000", "0.000", "#,##0"],
    )
    summary.append([])
    summary.append(
        [
            "Prices and capital are example values from the Assumptions sheet, not quotes. "
            "SMR operating point: "
            f"{report.operating_point.temperature_c:.0f} C, S/C "
            f"{report.operating_point.steam_to_carbon:.1f}, "
            f"{report.operating_point.pressure_bar:.0f} bar."
        ]
    )

    sweep_sheet = workbook.create_sheet("SMR sweep")
    sweep_rows = [
        [
            point.temperature_c,
            point.steam_to_carbon,
            point.pressure_bar,
            round(point.h2_per_ch4, 4),
            round(point.ch4_conversion, 4),
            round(point.h2_mole_fraction_dry, 4),
            round(point.duty_mj_per_kg_h2, 2),
            round(point.ch4_kg_per_kg_h2, 3),
            round(cost.energy_kwh_per_kg, 2),
            round(cost.total_cost_per_kg, 3),
        ]
        for point, cost in zip(report.sweep, report.sweep_costs, strict=True)
    ]
    _write_table(
        sweep_sheet,
        [
            "Temperature (C)",
            "Steam-to-carbon",
            "Pressure (bar)",
            "H2 per CH4 (mol/mol)",
            "CH4 conversion",
            "H2 fraction, dry gas",
            "Heat duty (MJ per kg H2)",
            "CH4 fed (kg per kg H2)",
            "Energy incl. furnace fuel (kWh per kg H2)",
            "SMR cost ($/kg)",
        ],
        sweep_rows,
        [
            "0",
            "0.0",
            "0",
            "0.000",
            "0.0%",
            "0.0%",
            "0.00",
            "0.000",
            "0.00",
            "0.000",
        ],
    )

    electrolysis_sheet = workbook.create_sheet("Electrolysis")
    electrolysis_rows = [
        [
            case.efficiency_hhv,
            round(case.kwh_per_kg, 2),
            round(case.water_kg_per_kg, 3),
            round(case.oxygen_kg_per_kg, 3),
            round(case.cost.energy_cost_per_kg, 3),
            round(case.cost.capex_cost_per_kg, 3),
            round(case.cost.total_cost_per_kg, 3),
        ]
        for case in report.electrolyser_cases
    ]
    _write_table(
        electrolysis_sheet,
        [
            "Efficiency (HHV)",
            "Electricity (kWh per kg H2)",
            "Water (kg per kg H2)",
            "Oxygen (kg per kg H2)",
            "Electricity cost ($/kg)",
            "Capital ($/kg)",
            "Total ($/kg)",
        ],
        electrolysis_rows,
        ["0%", "0.00", "0.000", "0.000", "0.000", "0.000", "0.000"],
    )

    balance_sheet = workbook.create_sheet("Mass balance")
    balance_rows = [
        [
            point.temperature_c,
            point.steam_to_carbon,
            point.carbon_closure_error,
            point.hydrogen_closure_error,
            point.oxygen_closure_error,
            point.mass_closure_error,
        ]
        for point in report.sweep
    ]
    balance_rows.append(["Water in vs H2 + O2 out", "", "", "", "", report.water_balance_error])
    _write_table(
        balance_sheet,
        [
            "Temperature (C)",
            "Steam-to-carbon",
            "Carbon closure error",
            "Hydrogen closure error",
            "Oxygen closure error",
            "Mass closure error",
        ],
        balance_rows,
        [None, None, "0.0E+00", "0.0E+00", "0.0E+00", "0.0E+00"],
    )
    balance_sheet.append([])
    balance_sheet.append(
        [
            f"Largest error in this file: {report.max_closure_error:.2e} (relative; a result of "
            "rounding level, below 1e-9, means the balance closes)."
        ]
    )

    assumptions_sheet = workbook.create_sheet("Assumptions")
    _write_table(
        assumptions_sheet,
        ["Input", "Value"],
        [[name, value] for name, value in asdict(report.assumptions).items()],
        [None, None],
    )

    workbook.save(path)
    return path
