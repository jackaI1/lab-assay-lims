import sqlite3

import pytest

from calibration_inspection_log.store import Log


@pytest.fixture
def log(tmp_path):
    with Log(tmp_path / "test.db") as book:
        book.add_instrument("CAL-1", "caliper", "SN-1", "mm")
        book.calibrate("CAL-1", "2026-01-01", "2026-06-01", "PASS", "certs/cal-1.pdf")
        book.receive(
            "R-1",
            "P-10",
            "DWG-10",
            "B",
            "LOT-1",
            "Example supplier",
            "PO-10",
            "certs/lot-1.pdf",
            "2026-05-01",
        )
        yield book


def reading(log, **changes):
    fields = dict(
        receipt="R-1",
        sample="1",
        feature="diameter",
        instrument="CAL-1",
        measured="10.05",
        lower="9.95",
        upper="10.05",
        unit="mm",
        defect_type=None,
    )
    fields.update(changes)
    return log.measure(**fields)


def test_records_survive_reopen_with_traceability(log):
    reading(log)
    with Log(log.path) as reopened:
        row = reopened.readings("2026-05-01")[0]
        assert (row["part"], row["drawing"], row["revision"], row["lot"]) == (
            "P-10",
            "DWG-10",
            "B",
            "LOT-1",
        )
        assert (row["purchase_order"], row["supplier_certificate"]) == ("PO-10", "certs/lot-1.pdf")
        assert row["calibration_certificate"] == "certs/cal-1.pdf"
        assert row["measured"] == "10.05"
        assert row["disposition"] == "PASS"


def test_nonconforming_reading_keeps_defect_category(log):
    result = reading(log, measured="10.06", defect_type="Oversize bore")
    assert result["dimension_result"] == "HIGH"
    assert result["disposition"] == "NONCONFORMING"
    assert result["defect_type"] == "Oversize bore"


def test_default_defect_category_is_direction(log):
    assert reading(log, measured="9.94")["defect_type"] == "UNDERSIZE"


@pytest.mark.parametrize("result", ["PASS", "OUT_OF_TOLERANCE"])
def test_renewal_keeps_history_and_inspection_snapshot(log, result):
    reading(log)
    log.calibrate("CAL-1", "2026-05-02", "2027-05-02", result, "certs/new.pdf")
    assert len(log.calibrations("2027-01-01")) == 2
    assert log.readings("2027-01-01")[0]["calibration_certificate"] == "certs/cal-1.pdf"
    assert log.instruments("2026-05-01")[0]["calibration_date"] == "2026-01-01"
    assert log.instruments("2026-05-02")[0]["status"] == (
        "CURRENT" if result == "PASS" else "OUT_OF_TOLERANCE"
    )


@pytest.mark.parametrize(
    ("cal_date", "due", "cal_result", "expected"),
    [
        ("2026-04-01", "2026-04-30", "PASS", "OVERDUE"),
        ("2026-04-01", "2026-12-01", "OUT_OF_TOLERANCE", "OUT_OF_TOLERANCE"),
    ],
)
def test_in_range_reading_with_unusable_instrument_is_held(
    log, cal_date, due, cal_result, expected
):
    log.calibrate("CAL-1", cal_date, due, cal_result, "certs/latest.pdf")
    result = reading(log)
    assert result["dimension_result"] == "PASS"
    assert result["equipment_status"] == expected
    assert result["disposition"] == "HOLD"


def test_no_calibration_and_future_only_calibration_hold_readings(log):
    log.add_instrument("NEW", "micrometer", "SN-2", "mm")
    log.calibrate("NEW", "2026-06-01", "2027-06-01", "PASS", "certs/future.pdf")
    result = reading(log, instrument="NEW")
    assert result["disposition"] == "HOLD"
    assert result["calibration_id"] is None


def test_receipts_without_readings_remain_visible(log):
    row = log.receiving("2026-05-01")[0]
    assert row["disposition"] == "NOT_INSPECTED"
    assert row["purchase_order"] == "PO-10"


def test_historical_cutoff_excludes_future_receipts(log):
    reading(log)
    assert log.readings("2026-04-30") == []
    assert log.receiving("2026-04-30") == []


@pytest.mark.parametrize(
    "changes",
    [
        {"unit": "in"},
        {"instrument": "missing"},
        {"receipt": "missing"},
        {"sample": ""},
        {"feature": " "},
        {"measured": "NaN"},
        {"lower": "11"},
        {"defect_type": "Unneeded category"},
    ],
)
def test_invalid_reading_does_not_write_partial_record(log, changes):
    with pytest.raises(ValueError):
        reading(log, **changes)
    assert log.readings("2026-12-31") == []


def test_duplicate_sample_feature_is_rejected(log):
    reading(log)
    with pytest.raises(ValueError):
        reading(log)
    assert len(log.readings("2026-12-31")) == 1


def test_duplicate_calibration_date_is_rejected_without_changing_history(log):
    with pytest.raises(ValueError):
        log.calibrate("CAL-1", "2026-01-01", "2027-01-01", "PASS", "other.pdf")
    assert len(log.calibrations("2027-01-01")) == 1


@pytest.mark.parametrize(("kind", "unit"), [("ruler", "mm"), ("caliper", "cm")])
def test_instrument_type_and_unit_are_validated(log, kind, unit):
    with pytest.raises(ValueError):
        log.add_instrument("BAD", kind, "SN-bad", unit)


def test_missing_traceability_is_rejected(log):
    with pytest.raises(ValueError):
        log.receive("R-2", "P", "DWG", "A", "L", "Supplier", "", "cert.pdf", "2026-01-01")
    assert len(log.receiving("2026-12-31")) == 1


def test_sql_foreign_keys_are_enabled(log):
    with pytest.raises(sqlite3.IntegrityError):
        with log.connection:
            log.connection.execute(
                "INSERT INTO calibrations(instrument,calibration_date,due_date,result,certificate) "
                "VALUES(?,?,?,?,?)",
                ("missing", "2026-01-01", "2027-01-01", "PASS", "x"),
            )
