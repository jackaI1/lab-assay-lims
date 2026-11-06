"""Reproducible synthetic records; no real supplier or calibration claims."""

from pathlib import Path

from .report import export_report
from .store import Log

DEMO_DATE = "2026-11-05"


def create_demo(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    certificates = output / "certificates"
    certificates.mkdir()
    for name in ("supplier", "calibration", "prior-calibration"):
        (certificates / f"{name}.txt").write_text(
            f"SYNTHETIC {name} certificate for the example only.\n"
            "Not evidence of a physical calibration or supplier delivery.\n",
            encoding="utf-8",
        )
    (output / "purchase-order.txt").write_text(
        "SYNTHETIC PO-DEMO-001: two sample lots of P-DEMO, drawing D-DEMO revision A.\n",
        encoding="utf-8",
    )
    with Log(output / "inspection.db") as log:
        instruments = [
            ("CAL-01", "caliper", "2027-01-01", "PASS"),
            ("MIC-01", "micrometer", "2026-11-04", "PASS"),
            ("HG-01", "height_gauge", "2027-01-01", "OUT_OF_TOLERANCE"),
            ("DI-01", "dial_indicator", "2026-11-20", "PASS"),
            ("CAL-02", "caliper", "2026-11-05", "PASS"),
            ("MIC-02", "micrometer", None, None),
        ]
        for identifier, kind, due, result in instruments:
            log.add_instrument(identifier, kind, f"DEMO-{identifier}", "mm")
            if identifier == "CAL-01":
                log.calibrate(
                    identifier,
                    "2025-01-01",
                    "2026-01-01",
                    "PASS",
                    "certificates/prior-calibration.txt",
                )
            if due:
                log.calibrate(identifier, "2026-01-01", due, result, "certificates/calibration.txt")
        for identifier, lot in [("RCV-001", "LOT-001"), ("RCV-002", "LOT-002")]:
            log.receive(
                identifier,
                "P-DEMO",
                "D-DEMO",
                "A",
                lot,
                "Synthetic supplier",
                "PO-DEMO-001",
                "certificates/supplier.txt",
                DEMO_DATE,
            )
        for sample, measured, instrument, defect in [
            ("1", "10.05", "CAL-01", None),
            ("2", "10.08", "CAL-01", "Oversize diameter"),
            ("3", "10.09", "CAL-01", "Oversize diameter"),
            ("4", "10.06", "CAL-01", "Oversize diameter"),
            ("5", "9.93", "CAL-01", "Undersize diameter"),
            ("6", "10.00", "MIC-01", None),
            ("7", "10.00", "HG-01", None),
            ("8", "10.00", "DI-01", None),
        ]:
            log.measure(
                "RCV-001", sample, "diameter", instrument, measured, "9.95", "10.05", "mm", defect
            )
        export_report(log, output / "quality-report.xlsx", DEMO_DATE)
    return output
