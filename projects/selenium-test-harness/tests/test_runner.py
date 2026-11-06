import json

import pytest

from instrument_harness import (
    BenchSupply,
    InstrumentError,
    Limits,
    Reading,
    Settings,
    SweepRunner,
    SweepStep,
)


class ShutdownFailure(BenchSupply):
    """Isolate a shutdown fault that the simulator's working off button cannot produce."""

    def __init__(self):
        self.shutdown_attempted = False

    def configure(self, settings):
        pass

    def measure(self):
        return Reading(1, 1, 1, 1)

    def output_off(self):
        self.shutdown_attempted = True
        raise InstrumentError("Output did not acknowledge shutdown")


def test_shutdown_failure_prevents_false_pass_and_is_saved(tmp_path):
    supply = ShutdownFailure()
    output = tmp_path / "shutdown.json"
    report = SweepRunner(supply).run([SweepStep(Settings(1), Limits(0.99, 1.01))], output)
    assert supply.shutdown_attempted
    assert report["steps"][0]["status"] == "pass"
    assert report["passed"] is False
    assert report["shutdown_error"] == {
        "type": "InstrumentError",
        "message": "Output did not acknowledge shutdown",
    }
    assert json.loads(output.read_text()) == report


def test_empty_sweep_is_rejected_without_touching_instrument(tmp_path):
    supply = ShutdownFailure()
    output = tmp_path / "empty.json"
    with pytest.raises(ValueError, match="at least one"):
        SweepRunner(supply).run([], output)
    assert supply.shutdown_attempted is False
    assert not output.exists()
