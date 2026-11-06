import json
import shutil
import subprocess
import sys

import pytest
from pxr import Gf, Usd, UsdGeom
from test_builder import PART, TOOL

import factory_cell as fc


def codes(report):
    return {issue.code for issue in report.issues}


def test_clean_bundle_has_json_validation_report(stage_path):
    report = fc.validate_stage(stage_path)
    assert report.valid
    payload = report.to_dict()
    assert payload["valid"] is True
    assert payload["issues"] == []
    assert payload["summary"]["part_samples"] == 193
    assert payload["summary"]["cycle_seconds"] == 8
    assert json.loads(json.dumps(payload)) == payload


@pytest.mark.parametrize(
    "mutation,expected",
    [
        (lambda s: UsdGeom.SetStageMetersPerUnit(s, 0.01), "UNITS"),
        (lambda s: UsdGeom.SetStageUpAxis(s, "Y"), "UP_AXIS"),
        (lambda s: s.ClearDefaultPrim(), "DEFAULT_PRIM"),
        (lambda s: s.GetPrimAtPath(PART).SetTypeName("Scope"), "HIERARCHY"),
        (lambda s: s.GetPrimAtPath(PART).SetActive(False), "HIERARCHY"),
        (lambda s: s.GetPrimAtPath(PART + "/Body").SetTypeName("Sphere"), "HIERARCHY"),
        (
            lambda s: (
                s.GetPrimAtPath("/World/Cell/Fixtures")
                .GetVariantSet("fixture")
                .BlockVariantSelection()
            ),
            "VARIANT",
        ),
        (
            lambda s: (
                s.GetPrimAtPath("/World/Cell/Fixtures")
                .GetVariantSet("fixture")
                .SetVariantSelection("broken")
            ),
            "VARIANT",
        ),
        (lambda s: s.SetEndTimeCode(0), "TIMING"),
        (lambda s: s.SetTimeCodesPerSecond(0), "TIMING"),
        (lambda s: s.SetFramesPerSecond(30), "TIMING"),
        (
            lambda s: (
                s.GetPrimAtPath(PART)
                .GetAttribute("xformOp:translate")
                .Set(Gf.Vec3d(90, 0, 0.83), 24)
            ),
            "PART_PATH",
        ),
        (
            lambda s: (
                s.GetPrimAtPath(PART)
                .GetAttribute("xformOp:translate")
                .Set(Gf.Vec3d(float("nan"), 0, 0), 24)
            ),
            "NONFINITE_MOTION",
        ),
        (
            lambda s: (
                s.GetPrimAtPath(TOOL).GetAttribute("xformOp:translate").Set(Gf.Vec3d(1.5, 0, 8), 90)
            ),
            "TOOL_TRACKING",
        ),
        (lambda s: s.GetPrimAtPath(PART).GetAttribute("xformOpOrder").Set([]), "PART_PATH"),
    ],
)
def test_reports_scene_edits_that_break_cell_contract(stage_path, mutation, expected):
    stage = Usd.Stage.Open(str(stage_path))
    # Root opinions are stronger than the generated asset/layout/motion layers.
    mutation(stage)
    report = fc.validate_stage(stage)
    assert not report.valid
    assert expected in codes(report)
    assert len(report.issues) < 30  # Group per-property problems instead of flooding the report.


def test_missing_sample_is_reported(stage_path):
    stage = Usd.Stage.Open(str(stage_path))
    layer = stage.GetLayerStack()[2]  # session, root, motion
    with Usd.EditContext(stage, layer):
        stage.GetPrimAtPath(PART).GetAttribute("xformOp:translate").ClearAtTime(60)
    assert "TIME_SAMPLES" in codes(fc.validate_stage(stage))


@pytest.mark.parametrize("missing", ["assets/part.usda", "motion.usda"])
def test_reports_missing_files_after_relocating(stage_path, tmp_path, missing):
    moved = tmp_path / "broken"
    shutil.copytree(stage_path.parent, moved)
    (moved / missing).unlink()
    report = fc.validate_stage(moved / "cell.usda")
    assert not report.valid
    assert "DEPENDENCY" in codes(report)


def test_missing_or_non_usd_file_is_a_report(tmp_path):
    assert "STAGE_OPEN" in codes(fc.validate_stage(tmp_path / "missing.usda"))
    invalid = tmp_path / "invalid.usda"
    invalid.write_text("not a USD file")
    assert "STAGE_OPEN" in codes(fc.validate_stage(invalid))


def cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "factory_cell", *map(str, args)],
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_cli_generates_validates_and_inspects_retimed_variant(tmp_path):
    path = tmp_path / "cli-cell"
    generated = cli(
        "generate", "--output", path, "--fixture", "nest", "--seconds", "12", "--fps", "30"
    )
    assert generated.returncode == 0, generated.stderr
    assert json.loads(generated.stdout)["valid"]
    result = cli("validate", path / "cell.usda")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["summary"]["cycle_seconds"] == 12
    inspected = cli("inspect", path / "cell.usda")
    assert inspected.returncode == 0, inspected.stderr
    info = json.loads(inspected.stdout)
    assert info["fixture"] == "nest"
    assert info["part_samples"] == 361
    assert PART in info["prims"]
    assert set(info["sublayers"]) == {"motion.usda", "layout.usda"}
    assert cli("generate", "--output", path).returncode != 0


def test_cli_validation_failure_is_machine_readable(tmp_path):
    result = cli("validate", tmp_path / "missing.usda")
    assert result.returncode == 1
    assert json.loads(result.stdout)["valid"] is False
    invalid = cli("generate", "--output", tmp_path / "bad", "--seconds", "nan")
    assert invalid.returncode == 1
    assert "finite" in json.loads(invalid.stdout)["error"]


def test_malformed_transform_evaluation_returns_failure_report(stage_path):
    from pxr import Sdf

    stage = Usd.Stage.Open(str(stage_path))
    prim = stage.GetPrimAtPath(PART)
    prim.CreateAttribute("xformOp:scale:bad", Sdf.ValueTypeNames.String).Set("oops")
    order = prim.GetAttribute("xformOpOrder")
    order.Set([*order.Get(), "xformOp:scale:bad"])
    report = fc.validate_stage(stage)
    assert not report.valid
    assert "TRANSFORM" in codes(report)
    assert json.loads(json.dumps(report.to_dict()))["valid"] is False
