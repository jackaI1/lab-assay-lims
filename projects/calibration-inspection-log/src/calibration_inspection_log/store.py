"""Persistent records with calibration evidence captured at inspection entry."""

import sqlite3
from importlib.resources import files
from pathlib import Path

from .rules import USABLE, calibration_status, check_tolerance, dimension, parse_date

KINDS = ("caliper", "micrometer", "height_gauge", "dial_indicator")
UNITS = ("mm", "in")


def required(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Identifiers and traceability fields must not be blank")
    value = value.strip()
    if len(value) > 1000 or any(ord(char) < 32 for char in value):
        raise ValueError("Text must be at most 1000 characters with no control characters")
    return value


class Log:
    def __init__(self, path):
        self.path = Path(path)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        try:
            version = self.connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise ValueError(f"Unsupported database version: {version}")
            self.connection.executescript(files(__package__).joinpath("schema.sql").read_text())
        except BaseException:
            self.connection.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.connection.close()

    def _insert(self, statement, values):
        try:
            with self.connection:
                cursor = self.connection.execute(statement, values)
                return cursor.lastrowid
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"Record rejected: {exc}") from exc

    def add_instrument(self, identifier, kind, serial, unit):
        if kind not in KINDS or unit not in UNITS:
            raise ValueError(f"Instrument kind must be one of {KINDS}; unit must be mm or in")
        self._insert(
            "INSERT INTO instruments VALUES(?,?,?,?)",
            (required(identifier), kind, required(serial), unit),
        )

    def calibrate(self, instrument, calibrated, due, result, certificate):
        calibrated, due = parse_date(calibrated).isoformat(), parse_date(due).isoformat()
        if result not in ("PASS", "OUT_OF_TOLERANCE"):
            raise ValueError("Calibration result must be PASS or OUT_OF_TOLERANCE")
        calibration_status(calibrated, due, result == "OUT_OF_TOLERANCE", calibrated)
        return self._insert(
            "INSERT INTO calibrations(instrument,calibration_date,due_date,result,certificate) "
            "VALUES(?,?,?,?,?)",
            (required(instrument), calibrated, due, result, required(certificate)),
        )

    def receive(
        self,
        identifier,
        part,
        drawing,
        revision,
        lot,
        supplier,
        purchase_order,
        supplier_certificate,
        inspected_on,
    ):
        values = tuple(
            map(
                required,
                (
                    identifier,
                    part,
                    drawing,
                    revision,
                    lot,
                    supplier,
                    purchase_order,
                    supplier_certificate,
                ),
            )
        )
        self._insert(
            "INSERT INTO receipts VALUES(?,?,?,?,?,?,?,?,?)",
            (*values, parse_date(inspected_on).isoformat()),
        )

    def _instrument(self, identifier, as_of, warning_days=30):
        row = self.connection.execute(
            "SELECT i.*, c.id AS calibration_id, c.calibration_date, c.due_date, "
            "c.result AS calibration_result, c.certificate AS calibration_certificate "
            "FROM instruments i LEFT JOIN calibrations c ON c.id = "
            "(SELECT id FROM calibrations WHERE instrument=i.id AND calibration_date<=? "
            "ORDER BY calibration_date DESC LIMIT 1) WHERE i.id=?",
            (as_of, identifier),
        ).fetchone()
        if row is None:
            raise ValueError(f"Unknown instrument: {identifier}")
        row = dict(row)
        row["status"] = calibration_status(
            row["calibration_date"],
            row["due_date"],
            row["calibration_result"] == "OUT_OF_TOLERANCE",
            as_of,
            warning_days,
        )
        row["days_overdue"] = (
            max(0, (parse_date(as_of) - parse_date(row["due_date"])).days)
            if row["due_date"]
            else None
        )
        return row

    def instruments(self, as_of, warning_days=30):
        as_of = parse_date(as_of).isoformat()
        # Validate even for an empty register.
        calibration_status(None, None, False, as_of, warning_days)
        identifiers = self.connection.execute("SELECT id FROM instruments ORDER BY id").fetchall()
        return [self._instrument(row["id"], as_of, warning_days) for row in identifiers]

    def calibrations(self, as_of):
        return [
            dict(row)
            for row in self.connection.execute(
                "SELECT * FROM calibrations WHERE calibration_date<=? "
                "ORDER BY instrument,calibration_date",
                (parse_date(as_of).isoformat(),),
            )
        ]

    def measure(
        self, receipt, sample, feature, instrument, measured, lower, upper, unit, defect_type=None
    ):
        receipt, sample, feature, instrument = map(required, (receipt, sample, feature, instrument))
        header = self.connection.execute("SELECT * FROM receipts WHERE id=?", (receipt,)).fetchone()
        if header is None:
            raise ValueError(f"Unknown receipt: {receipt}")
        equipment = self._instrument(instrument, header["inspected_on"])
        if unit not in UNITS or equipment["unit"] != unit:
            raise ValueError("Measurement unit must match instrument unit; convert explicitly")
        measured, lower, upper = (str(dimension(v)) for v in (measured, lower, upper))
        result = check_tolerance(measured, lower, upper)
        if result == "PASS" and defect_type is not None:
            raise ValueError("A passing dimension cannot have a defect category")
        category = (
            required(defect_type)
            if defect_type is not None
            else {"LOW": "UNDERSIZE", "HIGH": "OVERSIZE"}.get(result)
        )
        disposition = (
            "NONCONFORMING"
            if result != "PASS"
            else "HOLD"
            if equipment["status"] not in USABLE
            else "PASS"
        )
        identifier = self._insert(
            "INSERT INTO measurements(receipt,sample,feature,instrument,measured,lower_limit,"
            "upper_limit,unit,dimension_result,equipment_status,disposition,defect_type,"
            "calibration_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                receipt,
                sample,
                feature,
                instrument,
                measured,
                lower,
                upper,
                unit,
                result,
                equipment["status"],
                disposition,
                category,
                equipment["calibration_id"],
            ),
        )
        return dict(
            self.connection.execute(
                "SELECT * FROM measurements WHERE id=?", (identifier,)
            ).fetchone()
        )

    def receiving(self, as_of):
        """One row per reading, or a NOT_INSPECTED row for a receipt with no readings."""
        rows = self.connection.execute(
            "SELECT r.*, r.id AS receipt, m.id AS measurement_id, m.sample, m.feature, "
            "m.instrument, m.measured, m.lower_limit, m.upper_limit, m.unit, "
            "m.dimension_result, m.equipment_status, "
            "COALESCE(m.disposition,'NOT_INSPECTED') AS disposition, m.defect_type, "
            "m.calibration_id, c.certificate AS calibration_certificate "
            "FROM receipts r LEFT JOIN measurements m ON m.receipt=r.id "
            "LEFT JOIN calibrations c ON c.id=m.calibration_id "
            "WHERE r.inspected_on<=? ORDER BY r.inspected_on,r.id,m.id",
            (parse_date(as_of).isoformat(),),
        )
        return [dict(row) for row in rows]

    def readings(self, as_of):
        return [row for row in self.receiving(as_of) if row["measurement_id"] is not None]
