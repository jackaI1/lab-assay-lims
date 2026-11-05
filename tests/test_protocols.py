import subprocess
from pathlib import Path

import pytest

from lab_assay.protocols import plate_transfer, serial_dilution


def test_serial_volume_balance_and_simulation(tmp_path):
    source, plan = serial_dilution(steps=8, factor=2, final_volume=80, row="B")
    assert plan["stock_ul"] == 160
    assert plan["diluent_ul"] == 560
    assert plan["final_well_volumes"] == [80] * 8
    assert plan["concentration_fractions"] == [1 / (2**i) for i in range(8)]
    simulate(tmp_path, source)


def simulate(tmp_path, source):
    protocol = tmp_path / "protocol.py"
    protocol.write_text(source)
    command = Path(__import__("sys").executable).parent / "opentrons_simulate"
    result = subprocess.run([str(command), str(protocol)], capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stderr[-4000:]
    assert "Aspirating" in result.stdout


def test_transfer_plan_tracks_depletion_and_simulates(tmp_path):
    moves = [
        {"source": "A1", "destination": "B1", "volume": 50},
        {"source": "A1", "destination": "B2", "volume": 50},
    ]
    source, plan = plate_transfer(moves, {"A1": 150})
    assert plan["source_remaining_ul"] == {"A1": 50}
    assert plan["destination_ul"] == {"B1": 50, "B2": 50}
    assert plan["tips"] == 2
    simulate(tmp_path, source)


@pytest.mark.parametrize(
    "args",
    [
        dict(steps=13),
        dict(factor=1),
        dict(final_volume=10),
        dict(final_volume=150, factor=2),
        dict(row="I"),
        dict(factor=float("nan")),
    ],
)
def test_invalid_dilutions_rejected(args):
    with pytest.raises(ValueError):
        serial_dilution(**args)


@pytest.mark.parametrize(
    "moves,stock",
    [
        ([{"source": "A1", "destination": "A1", "volume": 50}], {"A1": 40}),
        ([{"source": "I1", "destination": "A1", "volume": 50}], {"I1": 150}),
        ([{"source": "A1", "destination": "A1", "volume": 10}], {"A1": 150}),
        ([{"source": "A1", "destination": "A1", "volume": 50}], {}),
        ([{"source": "A1", "destination": "A1", "volume": 50}], {"A1": float("nan")}),
        ([{"source": "A1", "destination": "A1", "volume": float("nan")}], {"A1": 150}),
        (
            [
                {"source": "A1", "destination": "A1", "volume": 150},
                {"source": "B1", "destination": "A1", "volume": 100},
            ],
            {"A1": 200, "B1": 200},
        ),
    ],
)
def test_impossible_transfers_rejected(moves, stock):
    with pytest.raises(ValueError):
        plate_transfer(moves, stock)


@pytest.mark.parametrize("args", [dict(steps=12, final_volume=100), dict(steps=2, factor=5, final_volume=80)])
def test_boundary_serial_plans_simulate(tmp_path, args):
    source, plan = serial_dilution(**args)
    assert max(plan["final_well_volumes"]) <= 200
    simulate(tmp_path, source)
