import json

import pytest
from selenium.webdriver.common.by import By

from instrument_harness import (
    BadReading,
    InstrumentError,
    Limits,
    OperationTimeout,
    Settings,
    SweepRunner,
    SweepStep,
)

pytestmark = pytest.mark.browser


def step(voltage=5.0):
    return SweepStep(Settings(voltage), Limits(voltage - 0.01, voltage + 0.01))


def assert_output_off(supply):
    device = supply.page.driver.find_element(By.ID, "device")
    assert device.get_attribute("data-output") == "off"


def test_sweep_applies_settings_and_logs_fresh_readings(supply, tmp_path):
    path = tmp_path / "nested" / "sweep.json"
    report = SweepRunner(supply).run([step(1), step(3), step(5)], path)
    assert json.loads(path.read_text()) == report
    assert report["passed"] is True
    assert report["planned_steps"] == 3
    assert [result["reading"]["current_ma"] for result in report["steps"]] == [1, 3, 5]
    assert [result["reading"]["sequence"] for result in report["steps"]] == [1, 2, 3]
    assert [result["reading"]["revision"] for result in report["steps"]] == [1, 2, 3]
    assert report["units"]["current"] == "mA"
    assert report["finished_at"] >= report["started_at"]
    assert all(result["duration_s"] > 0 for result in report["steps"])
    assert_output_off(supply)


def test_measurement_uses_applied_load_and_requires_configuration(supply):
    with pytest.raises(InstrumentError, match="Configure"):
        supply.measure()
    supply.configure(Settings(6, 2000))
    first = supply.measure()
    second = supply.measure()
    assert first.voltage_v == 6
    assert first.current_ma == 3
    assert second.sequence == first.sequence + 1
    supply.output_off()
    with pytest.raises(InstrumentError, match="Configure"):
        supply.measure()


@pytest.mark.parametrize("fault", ["bad-reading", "non-finite", "wrong-unit"])
def test_bad_readings_are_errors_and_report_is_strict_json(supply, tmp_path, fault):
    supply.page.select_fault(fault)
    path = tmp_path / "bad.json"
    report = SweepRunner(supply).run([step(), step(3)], path)
    assert report["passed"] is False
    assert len(report["steps"]) == 1
    assert report["steps"][0]["error"]["type"] == BadReading.__name__
    assert report["steps"][0]["reading"] is None
    json.loads(path.read_text(), parse_constant=lambda value: pytest.fail(value))
    assert_output_off(supply)


@pytest.mark.parametrize("fault", ["timeout", "stale"])
def test_no_fresh_reading_times_out_without_reusing_a_sample(supply, tmp_path, fault):
    supply.configure(Settings(5))
    assert supply.measure().current_ma == 5  # A valid old reading already exists.
    supply.page.select_fault(fault)
    path = tmp_path / "timeout.json"
    report = SweepRunner(supply).run([step(), step(3)], path)
    result = report["steps"][0]
    assert report["passed"] is False
    assert result["error"]["type"] == OperationTimeout.__name__
    assert result["reading"] is None
    assert len(report["steps"]) == 1
    assert json.loads(path.read_text())["steps"][0]["status"] == "error"
    assert_output_off(supply)


def test_numeric_drift_fails_limits_but_keeps_measured_values(supply, tmp_path):
    supply.page.select_fault("drift")
    report = SweepRunner(supply).run([step(2), step(4)], tmp_path / "drift.json")
    assert report["passed"] is False
    assert len(report["steps"]) == 2
    assert [result["reading"]["current_ma"] for result in report["steps"]] == [3, 6]
    assert all(result["status"] == "fail" for result in report["steps"])
    assert report["steps"][0]["violations"] == ["current outside limits"]
    assert_output_off(supply)


def test_device_error_is_logged_and_next_run_recovers(supply, tmp_path):
    supply.page.select_fault("error")
    failed = SweepRunner(supply).run([step()], tmp_path / "error.json")
    assert failed["passed"] is False
    assert failed["steps"][0]["error"]["type"] == "InstrumentError"
    assert "Sensor disconnected" in failed["steps"][0]["error"]["message"]
    assert_output_off(supply)
    supply.page.select_fault("normal")
    recovered = SweepRunner(supply).run([step()], tmp_path / "recovered.json")
    assert recovered["passed"] is True


def test_failure_to_write_report_still_turns_output_off(supply, tmp_path):
    with pytest.raises(OSError):
        SweepRunner(supply).run([step()], tmp_path)  # Destination is a directory.
    assert_output_off(supply)
