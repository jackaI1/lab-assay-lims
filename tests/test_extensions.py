import numpy as np
import pytest

from lab_assay.doe import analyse, factorial, fractional, simulate
from lab_assay.instrument import parse_values, retry, within
from lab_assay.microbiology import environmental_flags, media_volume, plate_result


def test_trace_and_limits():
    assert parse_values("1, 2,3") == [1, 2, 3]
    assert within(2, 1, 2) and not within(3, 1, 2)
    with pytest.raises(ValueError):
        parse_values("1,nan")


def test_timeout_retry():
    attempts = []

    def operation():
        attempts.append(1)
        if len(attempts) < 3:
            raise TimeoutError()
        return 42

    assert retry(operation, 2) == 42
    assert len(attempts) == 3


def test_design_and_recovery():
    d = factorial(2, seed=2)
    x = d[["power", "pressure", "time"]].to_numpy()
    assert np.allclose(x.T @ x, np.eye(3) * len(x))
    f = fractional(seed=2)
    assert np.allclose(f.time, f.power * f.pressure)
    data = simulate(d, seed=42, noise=0, drift=0)
    fit = analyse(data)
    assert fit["coefficients"]["power"] == pytest.approx(12, abs=0.01)


def test_plate_and_environment():
    r = plate_result([100, 110], dilution=0.01, volume_ml=1, limit=11000)
    assert r["cfu"] == 10500 and r["status"] == "pass"
    assert plate_result([10, 12], 1, 1, 100)["status"] == "invalid"
    assert environmental_flags(
        [{"room": "A", "location": "L", "count": 6}, {"room": "A", "location": "L", "count": 6}],
        {"A": {"alert": 5, "action": 10}},
    )[1]["repeat_location"]
    assert media_volume(20, 15, 10) == pytest.approx(330)


def test_simulated_capture_and_socket(tmp_path):
    import pyvisa

    from lab_assay.instrument import PowerSupply, run_capture
    from lab_assay.scpi_server import characterize, start_server

    result = run_capture(2, tmp_path)
    assert all(row["pass"] for row in result["captures"])
    assert len(list(tmp_path.glob("capture-*.csv"))) == 1
    server, thread = start_server()
    manager = pyvisa.ResourceManager("@py")
    try:
        port = server.server_address[1]
        with manager.open_resource(f"TCPIP::127.0.0.1::{port}::SOCKET") as resource:
            rows = characterize(resource, [0, 1, 2], -0.01, 0.01, tmp_path / "sweep.csv")
            assert all(row["pass"] for row in rows)
            driver = PowerSupply(resource)
            driver.write("BAD")
            with pytest.raises(RuntimeError):
                driver.check_errors()
    finally:
        manager.close()
        server.shutdown()
        server.server_close()
        thread.join()


def test_central_composite_and_lack_of_fit():
    from lab_assay.doe import central_composite

    d = simulate(central_composite(replicates=2), noise=0.1, drift=0)
    fit = analyse(d)
    assert fit["coefficients"]["power"] == pytest.approx(12, abs=0.2)
    assert fit["coefficients"]["I(pressure ** 2)"] == pytest.approx(-3, abs=0.2)
    assert fit["lack_of_fit_p"] is not None


def test_fraction_alias_and_count_failures():
    f = fractional()
    assert np.allclose(f.power, f.pressure * f.time)
    assert plate_result([100, 200], 0.1, 1, 10000)["reason"] == "plate agreement"
    assert plate_result([100, 110], 0.1, 1, 100)["status"] == "fail"
    with pytest.raises(ValueError):
        plate_result([100], 0, 1, 10)


def test_capture_api():
    from fastapi.testclient import TestClient

    from lab_assay.app import create_app

    with TestClient(create_app(":memory:")) as client:
        response = client.post("/api/instruments/capture?repeats=1")
        assert response.status_code == 200
        assert response.json()["captures"][0]["pass"]
        assert client.post("/api/instruments/capture?repeats=101").status_code == 422


def test_anova_hand_worked_factorial():
    from lab_assay.doe import factorial

    design = factorial(replicates=2, seed=4)
    design["thickness"] = (
        10 + 2 * design.power + design.groupby(["power", "pressure", "time"]).cumcount().map({0: -1, 1: 1})
    )
    result = analyse(design)
    power = next(row for row in result["anova"] if row["term"] == "power")
    # 16 observations, coefficient 2: SS = 16 * 2**2 = 64; pure error SS = 16, df = 8.
    assert power["sum_sq"] == pytest.approx(64)
    assert power["F"] == pytest.approx(32)


def test_timeout_exhaustion_and_non_timeout():
    def fail():
        raise TimeoutError("offline")

    with pytest.raises(TimeoutError):
        retry(fail, 1)

    def invalid():
        raise ValueError("invalid")

    with pytest.raises(ValueError):
        retry(invalid, 2)


def test_fraction_analysis_reports_alias():
    data = simulate(fractional(replicates=3), noise=0.1, drift=0)
    result = analyse(data)
    assert "power = pressure:time" in result["alias"]
    assert set(result["coefficients"]) == {"Intercept", "power", "pressure", "time"}


def test_socket_meter_and_scope():
    import pyvisa

    from lab_assay.instrument import OpticalPowerMeter, Oscilloscope
    from lab_assay.scpi_server import start_server

    server, thread = start_server()
    manager = pyvisa.ResourceManager("@py")
    try:
        with manager.open_resource(f"TCPIP::127.0.0.1::{server.server_address[1]}::SOCKET") as resource:
            assert OpticalPowerMeter(resource).measure() == pytest.approx(0.001)
            assert Oscilloscope(resource).waveform() == [0, 0.5, 1, 0.5, 0]
    finally:
        manager.close()
        server.shutdown()
        server.server_close()
        thread.join()
