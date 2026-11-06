"""Author a portable cell bundle; no renderer or Kit runtime required."""

from __future__ import annotations

import math
import tempfile
from pathlib import Path

from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux

CELL = "/World/Cell"
PART = CELL + "/Part"
ROBOT = CELL + "/Robot"
TOOL = ROBOT + "/Shoulder/Elbow/Tool"
FIXTURES = ("clamp", "nest")
# Normalized time, then position in metres. A dwell occupies 50%-62.5% of a cycle.
WAYPOINTS = (
    (0.0, (-1.8, 0.0, 0.83)),
    (0.25, (0.0, 0.0, 0.83)),
    (0.3125, (0.0, 0.0, 1.25)),
    (0.4375, (0.4, 0.8, 1.25)),
    (0.5, (0.4, 0.8, 0.88)),
    (0.625, (0.4, 0.8, 0.88)),
    (0.6875, (0.4, 0.8, 1.25)),
    (0.8125, (1.8, 0.0, 1.25)),
    (0.875, (1.8, 0.0, 0.83)),
    (1.0, (1.8, 0.0, 0.83)),
)


def part_position(phase: float) -> Gf.Vec3d:
    """Piecewise-linear part target, from infeed to fixture to outfeed."""
    for (a, p), (b, q) in zip(WAYPOINTS, WAYPOINTS[1:], strict=False):
        if phase <= b:
            alpha = max(0.0, (phase - a) / (b - a))
            return Gf.Vec3d(*p) * (1 - alpha) + Gf.Vec3d(*q) * alpha
    return Gf.Vec3d(*WAYPOINTS[-1][1])


def _stage(path: Path, root: str) -> Usd.Stage:
    stage = Usd.Stage.CreateNew(str(path))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    prim = UsdGeom.Xform.Define(stage, root).GetPrim()
    stage.SetDefaultPrim(prim)
    return stage


def _xform(stage, path, position):
    xform = UsdGeom.Xform.Define(stage, path)
    xform.AddTranslateOp().Set(Gf.Vec3d(*position))
    return xform


def _box(stage, path, position, dimensions, color):
    box = UsdGeom.Cube.Define(stage, path)
    box.CreateSizeAttr(1)
    box.AddTranslateOp().Set(Gf.Vec3d(*position))
    box.AddScaleOp().Set(Gf.Vec3f(*dimensions))
    box.CreateDisplayColorAttr([Gf.Vec3f(*color)])
    return box


def _cylinder(stage, path, position, radius, height, color):
    cylinder = UsdGeom.Cylinder.Define(stage, path)
    cylinder.CreateAxisAttr("Z")
    cylinder.CreateRadiusAttr(radius)
    cylinder.CreateHeightAttr(height)
    cylinder.AddTranslateOp().Set(Gf.Vec3d(*position))
    cylinder.CreateDisplayColorAttr([Gf.Vec3f(*color)])


def _assets(directory: Path):
    directory.mkdir()
    grey = (0.28, 0.34, 0.40)
    blue = (0.08, 0.35, 0.62)
    orange = (0.95, 0.44, 0.08)
    stage = _stage(directory / "conveyor.usda", "/Conveyor")
    _box(stage, "/Conveyor/Belt", (0, 0, 0.73), (4.4, 0.7, 0.1), grey)
    for side, y in [("Left", -0.4), ("Right", 0.4)]:
        _box(stage, f"/Conveyor/{side}Rail", (0, y, 0.72), (4.6, 0.08, 0.18), blue)
        for i, x in enumerate((-1.8, 1.8)):
            _box(stage, f"/Conveyor/{side}Leg{i}", (x, y, 0.34), (0.12, 0.12, 0.68), grey)
    stage.GetRootLayer().Save()

    stage = _stage(directory / "robot.usda", "/Robot")
    UsdGeom.Xformable(stage.GetDefaultPrim()).AddTranslateOp().Set((0, 1.4, 0.74))
    _cylinder(stage, "/Robot/Base", (0, 0, -0.37), 0.23, 0.74, grey)
    _cylinder(stage, "/Robot/Column", (0, 0, 0.43), 0.13, 0.86, orange)
    shoulder = _xform(stage, "/Robot/Shoulder", (0, 0, 0.86))
    shoulder.AddRotateZOp().Set(0)
    _box(stage, "/Robot/Shoulder/Link", (0.75, 0, 0), (1.5, 0.15, 0.12), orange)
    elbow = _xform(stage, "/Robot/Shoulder/Elbow", (1.5, 0, 0))
    elbow.AddRotateZOp().Set(0)
    _box(stage, "/Robot/Shoulder/Elbow/Link", (0.75, 0, 0.08), (1.5, 0.12, 0.10), orange)
    _xform(stage, "/Robot/Shoulder/Elbow/Tool", (1.5, 0, -0.67))
    _cylinder(stage, "/Robot/Shoulder/Elbow/Tool/Slide", (0, 0, 0.45), 0.04, 0.9, grey)
    for side, y in [("Left", -0.075), ("Right", 0.075)]:
        _box(
            stage,
            f"/Robot/Shoulder/Elbow/Tool/{side}Finger",
            (0, y, -0.06),
            (0.16, 0.025, 0.12),
            grey,
        )
    stage.GetRootLayer().Save()

    stage = _stage(directory / "fixture.usda", "/Fixtures")
    UsdGeom.Xformable(stage.GetDefaultPrim()).AddTranslateOp().Set((0.4, 0.8, 0))
    _box(stage, "/Fixtures/Table", (0, 0, 0.79), (0.65, 0.55, 0.08), blue)
    for i, (x, y) in enumerate(((-0.25, -0.2), (-0.25, 0.2), (0.25, -0.2), (0.25, 0.2))):
        _box(stage, f"/Fixtures/Leg{i}", (x, y, 0.375), (0.06, 0.06, 0.75), grey)
    variants = stage.GetDefaultPrim().GetVariantSets().AddVariantSet("fixture")
    for name in FIXTURES:
        variants.AddVariant(name)
        variants.SetVariantSelection(name)
        with variants.GetVariantEditContext():
            if name == "clamp":
                for side, y in [("Left", -0.09), ("Right", 0.09)]:
                    _box(stage, f"/Fixtures/{side}Jaw", (0, y, 0.88), (0.22, 0.06, 0.10), orange)
            else:
                UsdGeom.Xform.Define(stage, "/Fixtures/Nest")
                for i, (x, y, dims) in enumerate(
                    [
                        (-0.12, 0, (0.04, 0.22, 0.08)),
                        (0.12, 0, (0.04, 0.22, 0.08)),
                        (0, -0.09, (0.2, 0.04, 0.08)),
                        (0, 0.09, (0.2, 0.04, 0.08)),
                    ]
                ):
                    _box(stage, f"/Fixtures/Nest/Wall{i}", (x, y, 0.87), dims, grey)
    variants.SetVariantSelection("clamp")
    stage.GetRootLayer().Save()

    stage = _stage(directory / "part.usda", "/Part")
    UsdGeom.Xformable(stage.GetDefaultPrim()).AddTranslateOp().Set((-1.8, 0, 0.83))
    _box(stage, "/Part/Body", (0, 0, 0), (0.16, 0.10, 0.08), (0.12, 0.75, 0.38))
    stage.GetRootLayer().Save()


def _layout(directory: Path, fixture: str):
    stage = _stage(directory / "layout.usda", "/World")
    UsdGeom.Xform.Define(stage, CELL)
    for name, file in [
        ("Conveyor", "conveyor"),
        ("Robot", "robot"),
        ("Fixtures", "fixture"),
        ("Part", "part"),
    ]:
        prim = UsdGeom.Xform.Define(stage, CELL + "/" + name).GetPrim()
        prim.GetReferences().AddReference(f"./assets/{file}.usda")
    stage.GetPrimAtPath(CELL + "/Fixtures").GetVariantSet("fixture").SetVariantSelection(fixture)
    _box(stage, "/World/Floor", (0, 0.6, -0.04), (6.0, 4.8, 0.08), (0.12, 0.16, 0.20))
    light = UsdLux.DomeLight.Define(stage, "/World/Light")
    light.CreateIntensityAttr(800)
    camera = UsdGeom.Camera.Define(stage, "/World/Camera")
    matrix = Gf.Matrix4d().SetLookAt(Gf.Vec3d(7, -9, 7), Gf.Vec3d(0, 0.6, 0.6), Gf.Vec3d(0, 0, 1))
    camera.AddTransformOp().Set(matrix.GetInverse())
    stage.GetRootLayer().Save()


def _motion(directory: Path, frames: int, fps: int):
    stage = Usd.Stage.CreateNew(str(directory / "motion.usda"))
    stage.SetTimeCodesPerSecond(fps)
    stage.SetFramesPerSecond(fps)
    part = stage.OverridePrim(PART).CreateAttribute("xformOp:translate", Sdf.ValueTypeNames.Double3)
    shoulder = stage.OverridePrim(ROBOT + "/Shoulder").CreateAttribute(
        "xformOp:rotateZ", Sdf.ValueTypeNames.Float
    )
    elbow = stage.OverridePrim(ROBOT + "/Shoulder/Elbow").CreateAttribute(
        "xformOp:rotateZ", Sdf.ValueTypeNames.Float
    )
    tool = stage.OverridePrim(TOOL).CreateAttribute("xformOp:translate", Sdf.ValueTypeNames.Double3)
    for frame in range(frames + 1):
        phase = frame / frames
        part.Set(part_position(phase), frame)
        target = part_position(min(0.875, max(0.25, phase)))
        x, y = target[0], target[1] - 1.4
        # Analytic 2-link planar IK, both links 1.5 m, elbow-positive branch.
        angle2 = math.acos(max(-1.0, min(1.0, (x * x + y * y - 4.5) / 4.5)))
        angle1 = math.atan2(y, x) - math.atan2(1.5 * math.sin(angle2), 1.5 + 1.5 * math.cos(angle2))
        shoulder.Set(math.degrees(angle1), frame)
        elbow.Set(math.degrees(angle2), frame)
        tool.Set(Gf.Vec3d(1.5, 0, target[2] + 0.1 - 1.6), frame)
    stage.GetRootLayer().Save()


def build_cell(
    output: str | Path, *, fixture: str = "clamp", seconds: float = 8, fps: int = 24
) -> Path:
    """Create a new bundle and return its entry stage. Never overwrite user files."""
    if fixture not in FIXTURES:
        raise ValueError(f"fixture must be one of {FIXTURES}")
    if isinstance(fps, bool) or not isinstance(fps, int) or not 1 <= fps <= 240:
        raise ValueError("fps must be an integer from 1 to 240")
    if (
        isinstance(seconds, bool)
        or not isinstance(seconds, (int, float))
        or not math.isfinite(seconds)
    ):
        raise ValueError("seconds must be a finite positive number")
    if seconds <= 0 or not 8 <= seconds * fps <= 24000:
        raise ValueError("cycle must contain between 8 and 24000 frames")
    frames = round(seconds * fps)
    directory = Path(output).expanduser().absolute()
    if directory.exists() or directory.is_symlink():
        raise FileExistsError(f"output already exists: {directory}; choose a new directory")
    directory.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".factory-cell-", dir=directory.parent) as scratch:
        bundle = Path(scratch) / "bundle"
        bundle.mkdir()
        _assets(bundle / "assets")
        _layout(bundle, fixture)
        _motion(bundle, frames, fps)
        stage = _stage(bundle / "cell.usda", "/World")
        stage.GetRootLayer().subLayerPaths = ["motion.usda", "layout.usda"]
        stage.SetStartTimeCode(0)
        stage.SetEndTimeCode(frames)
        stage.SetTimeCodesPerSecond(fps)
        stage.SetFramesPerSecond(fps)
        stage.GetRootLayer().customLayerData = {"cellVersion": 1, "cycleSeconds": frames / fps}
        stage.GetRootLayer().Save()
        stage = None
        # rename is within one filesystem; all authored asset paths remain relative.
        bundle.rename(directory)
    return directory / "cell.usda"
