import time

from fastapi.testclient import TestClient

from machine_health.core import Frame, Monitor
from machine_health.web import create_app


def test_dashboard_report_history_ack_and_local_controls(tmp_path):
    with Monitor(tmp_path / "log.sqlite3") as monitor:
        now = time.time()
        monitor.ingest(
            Frame(
                {
                    "cycle_count": 1,
                    "cycle_time": 4.0,
                    "motor_running": True,
                    "fault_code": 0,
                    "fault_count": 0,
                },
                now,
            ),
            now,
        )
        with TestClient(create_app(monitor)) as client:
            assert client.get("/").status_code == 200
            status = client.get("/api/status").json()
            assert status["condition"] == "attention"
            incident = status["alerts"][0]["id"]
            assert client.post(f"/api/alerts/{incident}/ack").status_code == 200
            assert client.post(f"/api/alerts/{incident}/ack").status_code == 409
            assert client.post("/api/alerts/9999/ack").status_code == 409
            assert "Filling line" in client.get("/api/report").text
            assert client.get("/api/readings?limit=1").json()[0]["accepted"] == 1
            assert client.get("/api/readings?limit=100001").status_code == 422
            assert client.post("/api/scenario", json={"scenario": "slow"}).status_code == 403
            assert client.get("/static/app.js").status_code == 200


def test_demo_controls_validate_scenario(tmp_path):
    from machine_health.opcua import Simulator

    with Monitor(tmp_path / "log.sqlite3") as monitor:
        simulator = Simulator("opc.tcp://127.0.0.1:4840")
        with TestClient(create_app(monitor, simulator)) as client:
            assert client.get("/api/status").json()["demo"] is True
            assert client.post("/api/scenario", json={"scenario": "bogus"}).status_code == 422
            assert client.post("/api/scenario", json={"scenario": "slow"}).status_code == 200
            assert simulator.scenario == "slow"
            assert client.post("/api/scenario", json={"scenario": "normal"}).status_code == 200


def test_cross_origin_writes_are_rejected(tmp_path):
    with Monitor(tmp_path / "log.sqlite3") as monitor:
        with TestClient(create_app(monitor)) as client:
            assert (
                client.post(
                    "/api/alerts/1/ack", headers={"origin": "https://untrusted.example"}
                ).status_code
                == 403
            )
            assert (
                client.get("/api/status", headers={"host": "untrusted.example"}).status_code == 400
            )


def test_downloaded_report_explains_metric_units(tmp_path):
    with Monitor(tmp_path / "log.sqlite3") as monitor:
        now = time.time()
        for timestamp, count in [(now - 2, 0), (now, 1)]:
            monitor.ingest(
                Frame(
                    {
                        "cycle_count": count,
                        "cycle_time": 2.0,
                        "motor_running": True,
                        "fault_code": 0,
                        "fault_count": 0,
                    },
                    timestamp,
                ),
                timestamp,
            )
        with TestClient(create_app(monitor)) as client:
            report = client.get("/api/report").text
            assert "Availability: 100.0%" in report
            assert "Performance: 100.0%" in report
            assert "Fault rate: 0.0 events per observed minute" in report
            assert "Cycle-time drift: 0.0%" in report
