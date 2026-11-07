import shutil

import pytest
from pxr import Gf, Sdf, Usd, UsdGeom

import factory_cell as fc

PART = "/World/Cell/Part"
ROBOT = "/World/Cell/Robot"
TOOL = ROBOT + "/Shoulder/Elbow/Tool"


def test_builds_referenced_geometry_and_separate_motion(tmp_path):
    path = fc.build_cell(tmp_path / "cell")
    stage = Usd.Stage.Open(str(path))
    assert stage.GetDefaultPrim().GetPath() == Sdf.Path("/World")
    assert UsdGeom.GetStageMetersPerUnit(stage) == 1.0
    assert UsdGeom.GetStageUpAxis(stage) == "Z"
    assert stage.GetRootLayer().subLayerPaths == ["motion.usda", "layout.usda"]
    for name, child in [
        ("Conveyor", "Belt"),
        ("Robot", "Shoulder/Elbow/Tool"),
        ("Fixtures", "Table"),
        ("Part", "Body"),
    ]:
        prim = stage.GetPrimAtPath("/World/Cell/" + name)
        assert prim.HasAuthoredReferences()
        assert stage.GetPrimAtPath(str(prim.GetPath()) + "/" + child)
    layout = Sdf.Layer.FindOrOpen(str(path.parent / "layout.usda"))
    motion = Sdf.Layer.FindOrOpen(str(path.parent / "motion.usda"))
    assert not layout.ListTimeSamplesForPath(PART + ".xformOp:translate")
    assert len(motion.ListTimeSamplesForPath(PART + ".xformOp:translate")) == 193


@pytest.mark.parametrize(
    "variant,child,absent",
    [
        ("clamp", "LeftJaw", "Nest"),
        ("nest", "Nest", "LeftJaw"),
    ],
)
def test_fixture_variants_change_real_geometry(tmp_path, variant, child, absent):
    stage = Usd.Stage.Open(str(fc.build_cell(tmp_path / "cell", fixture=variant)))
    fixture = stage.GetPrimAtPath("/World/Cell/Fixtures")
    variants = fixture.GetVariantSet("fixture")
    assert variants.GetVariantSelection() == variant
    assert set(variants.GetVariantNames()) == {"clamp", "nest"}
    assert stage.GetPrimAtPath(str(fixture.GetPath()) + "/" + child)
    assert not stage.GetPrimAtPath(str(fixture.GetPath()) + "/" + absent)
    other = "nest" if variant == "clamp" else "clamp"
    variants.SetVariantSelection(other)
    assert stage.GetPrimAtPath(str(fixture.GetPath()) + "/" + absent)


def test_part_has_transfer_dwell_and_discharge_in_world_space(stage_path):
    stage = Usd.Stage.Open(str(stage_path))
    part = stage.GetPrimAtPath(PART)
    attr = part.GetAttribute("xformOp:translate")
    assert attr.GetTimeSamples() == list(range(193))
    assert tuple(attr.Get(0)) == pytest.approx((-1.8, 0, 0.83))
    assert tuple(attr.Get(48)) == pytest.approx((0, 0, 0.83))
    assert tuple(attr.Get(96)) == pytest.approx((0.4, 0.8, 0.88))
    assert tuple(attr.Get(108)) == pytest.approx((0.4, 0.8, 0.88))
    assert tuple(attr.Get(192)) == pytest.approx((1.8, 0, 0.83))
    assert tuple(attr.Get(24.5)) == pytest.approx((-0.88125, 0, 0.83))
    # End-effector follows the part throughout both transfers, not just at endpoints.
    for frame in range(48, 169):
        cache = UsdGeom.XformCache(Usd.TimeCode(frame))
        tool = cache.GetLocalToWorldTransform(stage.GetPrimAtPath(TOOL)).ExtractTranslation()
        center = cache.GetLocalToWorldTransform(part).ExtractTranslation()
        assert Gf.IsClose(tool, center + Gf.Vec3d(0, 0, 0.1), 1e-5)


def test_cycle_retimes_all_animation_without_changing_positions(tmp_path):
    stage = Usd.Stage.Open(str(fc.build_cell(tmp_path / "cell", seconds=12, fps=30)))
    assert stage.GetEndTimeCode() == 360
    assert stage.GetTimeCodesPerSecond() == stage.GetFramesPerSecond() == 30
    assert tuple(
        stage.GetPrimAtPath(PART).GetAttribute("xformOp:translate").Get(180)
    ) == pytest.approx((0.4, 0.8, 0.88))
    assert stage.GetPrimAtPath(TOOL).GetAttribute("xformOp:translate").GetNumTimeSamples() == 361


def test_generated_bundle_can_be_moved(stage_path, tmp_path):
    moved = tmp_path / "moved"
    shutil.copytree(stage_path.parent, moved)
    shutil.rmtree(stage_path.parent)
    stage = Usd.Stage.Open(str(moved / "cell.usda"))
    assert stage.GetPrimAtPath(PART + "/Body").IsA(UsdGeom.Cube)
    assert stage.GetPrimAtPath(TOOL)
    assert not stage.GetCompositionErrors()
    for layer in stage.GetUsedLayers():
        if not layer.anonymous:
            assert str(moved) in layer.realPath


@pytest.mark.parametrize(
    "kwargs",
    [
        {"fixture": "invalid"},
        {"seconds": 0},
        {"seconds": -1},
        {"seconds": float("nan")},
        {"seconds": float("inf")},
        {"fps": 0},
        {"fps": 2.5},
        {"fps": True},
        {"seconds": 1000000},
    ],
)
def test_bad_configuration_is_rejected_before_writing(tmp_path, kwargs):
    target = tmp_path / "cell"
    with pytest.raises(ValueError):
        fc.build_cell(target, **kwargs)
    assert not target.exists()


def test_refuses_to_overwrite_an_existing_directory(tmp_path):
    target = tmp_path / "cell"
    target.mkdir()
    original = target / "notes.txt"
    original.write_text("keep this")
    with pytest.raises(FileExistsError):
        fc.build_cell(target)
    assert original.read_text() == "keep this"
    assert list(target.iterdir()) == [original]
