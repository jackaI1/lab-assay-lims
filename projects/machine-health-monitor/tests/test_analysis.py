import math

import pytest

from machine_health.core import Config, Frame, Monitor


def values(**changes):
    return (
        dict(cycle_count=10, cycle_time=2.0, motor_running=True, fault_code=0, fault_count=0, **{})
        | changes
    )


def feed(monitor, at, **changes):
    return monitor.ingest(Frame(values(**changes), at), at)


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"cycle_time": None}, "missing:cycle_time"),
        ({"cycle_time": -1}, "out_of_range:cycle_time"),
        ({"cycle_time": math.nan}, "out_of_range:cycle_time"),
        ({"motor_running": 1}, "invalid_type:motor_running"),
        ({"cycle_count": 1.2}, "invalid_type:cycle_count"),
        ({"fault_code": 99}, "out_of_range:fault_code"),
    ],
)
def test_bad_values_are_saved_and_excluded(tmp_path, changes, reason):
    with Monitor(tmp_path / "log.sqlite3") as monitor:
        result = monitor.ingest(Frame(values(**changes), 100), 100)
        assert reason in result["reasons"]
        assert monitor.snapshot(100)["metrics"]["availability"] is None
        assert reason in monitor.readings()[0]["reasons"]
        assert monitor.readings()[0]["accepted"] == 0


@pytest.mark.parametrize(
    ("source", "now", "good", "reason"),
    [
        (None, 100, True, "missing:source_time"),
        (90, 100, True, "stale"),
        (110, 100, True, "future_timestamp"),
        (100, 100, False, "bad_status"),
    ],
)
def test_source_validation(tmp_path, source, now, good, reason):
    with Monitor(tmp_path / "log.sqlite3") as monitor:
        assert reason in monitor.ingest(Frame(values(), source, good), now)["reasons"]


def test_duplicate_means_replayed_timestamp_not_unchanged_machine(tmp_path):
    with Monitor(tmp_path / "log.sqlite3") as monitor:
        assert feed(monitor, 100)["accepted"]
        assert monitor.ingest(Frame(values(), 100), 101)["reasons"] == ["duplicate"]
        assert feed(monitor, 102)["accepted"]
        assert "out_of_order" in monitor.ingest(Frame(values(), 101), 102)["reasons"]


def test_metric_formulas_and_gap_coverage(tmp_path):
    with Monitor(tmp_path / "log.sqlite3", Config(window_seconds=20)) as monitor:
        feed(monitor, 100, cycle_count=0)
        feed(monitor, 102, cycle_count=1)
        feed(monitor, 104, cycle_count=2, motor_running=False, fault_count=1, fault_code=2)
        feed(monitor, 106, cycle_count=2, motor_running=True, fault_count=1)
        metrics = monitor.snapshot(106)["metrics"]
        assert metrics["availability"] == pytest.approx(2 / 3)
        assert metrics["performance"] == 1.0
        assert metrics["fault_rate_per_minute"] == 10
        assert metrics["cycle_time_drift"] == 0
        assert metrics["observed_seconds"] == 6
        feed(monitor, 130, cycle_count=3, fault_count=1)
        assert monitor.snapshot(130)["metrics"]["availability"] is None
        assert monitor.snapshot(134)["condition"] == "unknown"


def test_persistent_ack_clear_reopen_and_deduplication(tmp_path):
    path = tmp_path / "log.sqlite3"
    with Monitor(path) as monitor:
        feed(monitor, 100, cycle_time=3)
        feed(monitor, 101, cycle_time=3)
        alert = next(a for a in monitor.alerts() if a["rule"] == "cycle_drift")
        assert alert["occurrences"] == 2
        assert monitor.acknowledge(alert["id"], 101)
    with Monitor(path) as monitor:
        assert (
            next(a for a in monitor.alerts() if a["id"] == alert["id"])["state"] == "acknowledged"
        )
        # Old slow samples leave the rolling window.
        feed(monitor, 130)
        cleared = next(a for a in monitor.alerts() if a["id"] == alert["id"])
        assert cleared["state"] == "cleared"
        feed(monitor, 131, cycle_time=10)
        incidents = [a for a in monitor.alerts() if a["rule"] == "cycle_drift"]
        assert len(incidents) == 2
        assert not monitor.acknowledge(9999, 131)
        assert not monitor.acknowledge(alert["id"], 131)
        assert "duplicate" in monitor.ingest(Frame(values(), 131), 132)["reasons"]


def test_no_data_is_unknown_and_disconnect_retains_evidence(tmp_path):
    with Monitor(tmp_path / "log.sqlite3") as monitor:
        assert monitor.snapshot(100)["condition"] == "unknown"
        monitor.disconnected(100, "OPC UA connection failed")
        monitor.disconnected(101, "OPC UA connection failed")
        assert len([a for a in monitor.alerts() if a["rule"] == "connection_lost"]) == 1
        assert monitor.readings()[0]["reasons"] == ["connection_lost"]
        feed(monitor, 102)
        assert (
            next(a for a in monitor.alerts() if a["rule"] == "connection_lost")["state"]
            == "cleared"
        )


def test_counter_reset_does_not_invent_production_or_faults(tmp_path):
    with Monitor(tmp_path / "log.sqlite3") as monitor:
        feed(monitor, 100, cycle_count=100, fault_count=20)
        feed(monitor, 101, cycle_count=0, fault_count=0)
        assert monitor.snapshot(101)["metrics"]["performance"] is None
        assert monitor.snapshot(101)["metrics"]["fault_rate_per_minute"] is None
        assert "counter reset" in monitor.snapshot(101)["report"].lower()


@pytest.mark.parametrize(
    "changes",
    [
        dict(window_seconds=0),
        dict(stale_seconds=-1),
        dict(ideal_cycle_seconds=0),
        dict(availability_min=2),
    ],
)
def test_invalid_config_is_rejected(changes):
    with pytest.raises(ValueError):
        Config(**changes)


def test_timestamp_microsecond_rounding_does_not_hide_accepted_frame(tmp_path):
    with Monitor(tmp_path / "log.sqlite3") as monitor:
        assert monitor.ingest(Frame(values(), 100.0000002), 100)["accepted"]
        assert monitor.snapshot(100)["metrics"]["cycle_time_drift"] == 0


def test_frozen_sample_keeps_both_duplicate_and_stale_reasons(tmp_path):
    with Monitor(tmp_path / "log.sqlite3") as monitor:
        feed(monitor, 100)
        reasons = monitor.ingest(Frame(values(), 100), 110)["reasons"]
        assert "duplicate" in reasons and "stale" in reasons


def test_long_open_incident_stays_visible_after_many_cleared_incidents(tmp_path):
    with Monitor(tmp_path / "log.sqlite3") as monitor:
        feed(monitor, 100, cycle_time=4)
        for step in range(1, 106):
            # Alternate invalid and valid frames without clearing the slow-cycle incident.
            monitor.ingest(Frame(values(cycle_time=None), 100 + step * 2), 100 + step * 2)
            feed(monitor, 101 + step * 2, cycle_time=4)
        assert any(a["rule"] == "cycle_drift" and a["state"] == "active" for a in monitor.alerts())


def test_one_sample_without_an_interval_is_unknown(tmp_path):
    with Monitor(tmp_path / "log.sqlite3") as monitor:
        feed(monitor, 100)
        assert monitor.snapshot(100)["condition"] == "unknown"


def test_current_machine_fault_has_an_immediate_incident(tmp_path):
    with Monitor(tmp_path / "log.sqlite3") as monitor:
        feed(monitor, 100, fault_code=3, motor_running=False)
        alert = next(a for a in monitor.alerts() if a["rule"] == "machine_fault")
        assert "Guard open" in alert["message"]
        feed(monitor, 101)
        assert next(a for a in monitor.alerts() if a["id"] == alert["id"])["state"] == "cleared"


def test_unknown_intervals_do_not_clear_an_availability_incident(tmp_path):
    with Monitor(tmp_path / "log.sqlite3") as monitor:
        feed(monitor, 100, motor_running=False)
        feed(monitor, 101, motor_running=False)
        feed(monitor, 130)
        assert next(a for a in monitor.alerts() if a["rule"] == "availability")["state"] == "active"


def test_rejection_between_delayed_source_frames_excludes_interval(tmp_path):
    with Monitor(tmp_path / "log.sqlite3") as monitor:
        monitor.ingest(Frame(values(cycle_count=0), 100), 102)
        monitor.ingest(Frame(values(cycle_time=None), 101), 103)
        monitor.ingest(Frame(values(cycle_count=1), 102), 104)
        metrics = monitor.snapshot(104)["metrics"]
        assert metrics["observed_seconds"] == 0
        assert metrics["availability"] is None
        assert metrics["performance"] is None


def test_changed_fault_updates_message_and_keeps_acknowledgement(tmp_path):
    with Monitor(tmp_path / "log.sqlite3") as monitor:
        feed(monitor, 100, fault_code=3)
        incident = next(a for a in monitor.alerts() if a["rule"] == "machine_fault")
        monitor.acknowledge(incident["id"], 100)
        feed(monitor, 101, fault_code=4)
        updated = next(a for a in monitor.alerts() if a["id"] == incident["id"])
        assert "Emergency stop" in updated["message"]
        assert updated["state"] == "acknowledged"


@pytest.mark.parametrize("value", [b"bad sensor payload", object()])
def test_non_json_machine_values_are_retained_as_rejections(tmp_path, value):
    with Monitor(tmp_path / "log.sqlite3") as monitor:
        result = monitor.ingest(Frame(values(cycle_time=value), 100), 100)
        assert result["reasons"] == ["invalid_type:cycle_time"]
        retained = monitor.readings()[0]["raw"]["cycle_time"]
        assert retained["type"] == type(value).__name__
        assert retained["representation"]
        assert feed(monitor, 101)["accepted"]
