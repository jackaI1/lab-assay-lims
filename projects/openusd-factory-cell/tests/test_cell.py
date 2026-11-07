"""Exercise the exported stage through the USD reader, not string matching."""

import copy
import json
import subprocess
import sys

import pytest
from pxr import Usd, UsdGeom

LAYOUT = {
    "equipment": [
        {"name": "Conveyor", "size_m": [2, 0.8, 0.6], "position_m": [1, 0, 0.3]},
        {"name": "Robot", "size_m": [0.5, 0.5, 1.2], "position_m": [0, 1, 0.6]},
    ]
}


def invoke(source, target):
    return subprocess.run(
        [sys.executable, "-m", "factory_cell", str(source), str(target)],
        text=True,
        capture_output=True,
        check=False,
    )


def test_export_reopens_with_real_dimensions(tmp_path):
    source, target = tmp_path / "layout.json", tmp_path / "cell.usda"
    source.write_text(json.dumps(LAYOUT))
    result = invoke(source, target)
    assert result.returncode == 0, result.stderr
    stage = Usd.Stage.Open(str(target))
    assert stage.GetDefaultPrim().GetPath() == "/FactoryCell"
    assert UsdGeom.GetStageMetersPerUnit(stage) == 1.0
    assert UsdGeom.GetStageUpAxis(stage) == "Z"
    assert [p.GetName() for p in stage.GetDefaultPrim().GetChildren()] == ["Conveyor", "Robot"]
    cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_])
    box = cache.ComputeWorldBound(
        stage.GetPrimAtPath("/FactoryCell/Conveyor")
    ).ComputeAlignedRange()
    assert tuple(box.GetMin()) == pytest.approx((0, -0.4, 0))
    assert tuple(box.GetMax()) == pytest.approx((2, 0.4, 0.6))


def test_invalid_layout_preserves_existing_output(tmp_path):
    source, target = tmp_path / "bad.json", tmp_path / "cell.usda"
    source.write_text('{"equipment": []}')
    target.write_text("original")
    result = invoke(source, target)
    assert result.returncode == 2
    assert "equipment" in result.stderr
    assert "Traceback" not in result.stderr
    assert target.read_text() == "original"


@pytest.mark.parametrize("value", [None, [], {}, {"equipment": "robot"}, {"equipment": [None]}])
def test_rejects_malformed_structure(value):
    from factory_cell import validate_layout

    with pytest.raises(ValueError):
        validate_layout(value)


@pytest.mark.parametrize(
    "field,value",
    [
        ("name", "bad/name"),
        ("name", ""),
        ("name", "3robot"),
        ("name", None),
        ("size_m", [0, 1, 1]),
        ("size_m", [-1, 1, 1]),
        ("size_m", [1, 2]),
        ("position_m", [1, 2, 3, 4]),
        ("size_m", [True, 1, 1]),
        ("position_m", [float("nan"), 0, 0]),
        ("size_m", [float("inf"), 1, 1]),
        ("position_m", ["1", 0, 0]),
    ],
)
def test_rejects_invalid_equipment(field, value):
    from factory_cell import validate_layout

    layout = copy.deepcopy(LAYOUT)
    layout["equipment"][0][field] = value
    with pytest.raises(ValueError):
        validate_layout(layout)


def test_duplicate_names_rejected():
    from factory_cell import validate_layout

    with pytest.raises(ValueError, match="duplicate"):
        validate_layout({"equipment": [LAYOUT["equipment"][0]] * 2})


@pytest.mark.parametrize("contents", ["{invalid", '{"equipment": [NaN]}'])
def test_cli_bad_json_is_readable(tmp_path, contents):
    source = tmp_path / "invalid.json"
    source.write_text(contents)
    result = invoke(source, tmp_path / "out.usda")
    assert result.returncode == 2
    assert "Traceback" not in result.stderr


def test_cli_missing_input_is_readable(tmp_path):
    result = invoke(tmp_path / "missing.json", tmp_path / "out.usda")
    assert result.returncode == 2
    assert "Traceback" not in result.stderr


def test_write_stage_api(tmp_path):
    from factory_cell import write_stage

    target = tmp_path / "nested" / "cell.usdc"
    write_stage(LAYOUT, target)
    assert Usd.Stage.Open(str(target)).GetDefaultPrim().GetName() == "FactoryCell"


@pytest.mark.parametrize("size", [1e40, 1e-46])
def test_scale_roundtrip_keeps_finite_positive_dimensions(tmp_path, size):
    from factory_cell import write_stage

    layout = copy.deepcopy(LAYOUT)
    layout["equipment"][0]["size_m"] = [size, 1, 1]
    target = tmp_path / "scale.usda"
    write_stage(layout, target)
    stage = Usd.Stage.Open(str(target))
    scale = stage.GetPrimAtPath("/FactoryCell/Conveyor").GetAttribute("xformOp:scale").Get()
    assert scale[0] == pytest.approx(size, rel=1e-12, abs=0)


def test_cli_huge_integer_is_readable_and_preserves_output(tmp_path):
    layout = copy.deepcopy(LAYOUT)
    layout["equipment"][0]["size_m"][0] = 10**1000
    source, target = tmp_path / "large.json", tmp_path / "cell.usda"
    source.write_text(json.dumps(layout))
    target.write_text("original")
    result = invoke(source, target)
    assert result.returncode == 2
    assert "finite" in result.stderr
    assert "Traceback" not in result.stderr
    assert target.read_text() == "original"
