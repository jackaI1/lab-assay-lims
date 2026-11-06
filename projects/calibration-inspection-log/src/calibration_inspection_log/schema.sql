PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS instruments (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK(kind IN ('caliper','micrometer','height_gauge','dial_indicator')),
    serial TEXT NOT NULL UNIQUE,
    unit TEXT NOT NULL CHECK(unit IN ('mm','in'))
);
CREATE TABLE IF NOT EXISTS calibrations (
    id INTEGER PRIMARY KEY,
    instrument TEXT NOT NULL REFERENCES instruments(id),
    calibration_date TEXT NOT NULL,
    due_date TEXT NOT NULL CHECK(due_date >= calibration_date),
    result TEXT NOT NULL CHECK(result IN ('PASS','OUT_OF_TOLERANCE')),
    certificate TEXT NOT NULL,
    UNIQUE(instrument, calibration_date)
);
CREATE TABLE IF NOT EXISTS receipts (
    id TEXT PRIMARY KEY,
    part TEXT NOT NULL,
    drawing TEXT NOT NULL,
    revision TEXT NOT NULL,
    lot TEXT NOT NULL,
    supplier TEXT NOT NULL,
    purchase_order TEXT NOT NULL,
    supplier_certificate TEXT NOT NULL,
    inspected_on TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS measurements (
    id INTEGER PRIMARY KEY,
    receipt TEXT NOT NULL REFERENCES receipts(id),
    sample TEXT NOT NULL,
    feature TEXT NOT NULL,
    instrument TEXT NOT NULL REFERENCES instruments(id),
    measured TEXT NOT NULL,
    lower_limit TEXT NOT NULL,
    upper_limit TEXT NOT NULL,
    unit TEXT NOT NULL CHECK(unit IN ('mm','in')),
    dimension_result TEXT NOT NULL CHECK(dimension_result IN ('LOW','PASS','HIGH')),
    equipment_status TEXT NOT NULL,
    disposition TEXT NOT NULL CHECK(disposition IN ('PASS','HOLD','NONCONFORMING')),
    defect_type TEXT,
    calibration_id INTEGER REFERENCES calibrations(id),
    UNIQUE(receipt, sample, feature)
);
CREATE INDEX IF NOT EXISTS calibration_lookup ON calibrations(instrument, calibration_date);
CREATE INDEX IF NOT EXISTS receipt_date ON receipts(inspected_on);
CREATE TRIGGER IF NOT EXISTS immutable_calibration_update BEFORE UPDATE ON calibrations
BEGIN SELECT RAISE(ABORT, 'Calibration history is append-only'); END;
CREATE TRIGGER IF NOT EXISTS immutable_calibration_delete BEFORE DELETE ON calibrations
BEGIN SELECT RAISE(ABORT, 'Calibration history is append-only'); END;
CREATE TRIGGER IF NOT EXISTS immutable_measurement_update BEFORE UPDATE ON measurements
BEGIN SELECT RAISE(ABORT, 'Measurement history is append-only'); END;
CREATE TRIGGER IF NOT EXISTS immutable_measurement_delete BEFORE DELETE ON measurements
BEGIN SELECT RAISE(ABORT, 'Measurement history is append-only'); END;
PRAGMA user_version = 1;
