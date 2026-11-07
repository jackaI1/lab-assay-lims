"""Validate this project's cell contract on disk or in an editable USD stage."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from pathlib import Path

from pxr import Gf, Usd, UsdGeom, UsdUtils

from .builder import CELL, FIXTURES, PART, ROBOT, TOOL, part_position


@dataclass(frozen=True)
class Issue:
    code: str
    path: str
    message: str


@dataclass
class ValidationReport:
    issues: list[Issue] = field(default_factory=list)
    summary: dict = field(default_factory=dict)

    @property
    def valid(self) -> bool:
        return not self.issues

    def add(self, code: str, path: str, message: str):
        # A broken property gets one diagnostic, rather than one per frame.
        if not any(i.code == code and i.path == path for i in self.issues):
            self.issues.append(Issue(code, path, message))

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "issues": [asdict(i) for i in self.issues],
            "summary": self.summary,
        }


def open_stage(source: str | Path | Usd.Stage) -> Usd.Stage:
    if isinstance(source, Usd.Stage):
        return source
    return Usd.Stage.Open(str(Path(source).expanduser()))


def _finite(value) -> bool:
    try:
        if isinstance(value, (int, float)):
            return math.isfinite(value)
        return value is not None and all(math.isfinite(x) for x in value)
    except (TypeError, ValueError):
        return False


def _timing(stage, report):
    start, end = stage.GetStartTimeCode(), stage.GetEndTimeCode()
    fps = stage.GetTimeCodesPerSecond()
    if (
        not all(math.isfinite(x) for x in (start, end, fps))
        or start != 0
        or not 8 <= end <= 24000
        or not end.is_integer()
        or not 1 <= fps <= 240
        or fps != stage.GetFramesPerSecond()
        or not stage.HasAuthoredTimeCodeRange()
    ):
        report.add(
            "TIMING", "/", "Expected 0..N frames (8..24000) and matching positive time rates."
        )
        return None
    report.summary.update(frames=int(end), fps=fps, cycle_seconds=end / fps)
    return int(end)


def _hierarchy(stage, report):
    required = {
        "/World": UsdGeom.Xform,
        CELL: UsdGeom.Xform,
        CELL + "/Conveyor": UsdGeom.Xform,
        CELL + "/Conveyor/Belt": UsdGeom.Cube,
        ROBOT: UsdGeom.Xform,
        ROBOT + "/Shoulder": UsdGeom.Xform,
        ROBOT + "/Shoulder/Elbow": UsdGeom.Xform,
        TOOL: UsdGeom.Xform,
        CELL + "/Fixtures": UsdGeom.Xform,
        CELL + "/Fixtures/Table": UsdGeom.Cube,
        PART: UsdGeom.Xform,
        PART + "/Body": UsdGeom.Cube,
    }
    for path, schema in required.items():
        prim = stage.GetPrimAtPath(path)
        if not prim or not prim.IsActive() or not prim.IsDefined() or not prim.IsA(schema):
            report.add("HIERARCHY", path, f"Missing active {schema.__name__}.")
    fixture = stage.GetPrimAtPath(CELL + "/Fixtures")
    if fixture:
        variants = fixture.GetVariantSet("fixture")
        selection = variants.GetVariantSelection()
        report.summary["fixture"] = selection
        expected = ["LeftJaw", "RightJaw"] if selection == "clamp" else ["Nest/Wall0", "Nest/Wall3"]
        if (
            selection not in FIXTURES
            or set(variants.GetVariantNames()) != set(FIXTURES)
            or any(not stage.GetPrimAtPath(f"{CELL}/Fixtures/{child}") for child in expected)
        ):
            report.add(
                "VARIANT", str(fixture.GetPath()), "Select clamp or nest with its geometry present."
            )


def _motion(stage, frames, report):
    properties = [
        (PART, "xformOp:translate"),
        (ROBOT + "/Shoulder", "xformOp:rotateZ"),
        (ROBOT + "/Shoulder/Elbow", "xformOp:rotateZ"),
        (TOOL, "xformOp:translate"),
    ]
    attrs = []
    for path, name in properties:
        prim = stage.GetPrimAtPath(path)
        attr = prim.GetAttribute(name) if prim else None
        label = path + "." + name
        if not attr or attr.GetTimeSamples() != list(range(frames + 1)):
            report.add(
                "TIME_SAMPLES",
                label,
                "Expected a motion sample at every frame, including endpoints.",
            )
        attrs.append((attr, label))
    report.summary["part_samples"] = attrs[0][0].GetNumTimeSamples() if attrs[0][0] else 0
    part, tool = stage.GetPrimAtPath(PART), stage.GetPrimAtPath(TOOL)
    if not part or not tool or not part.IsActive() or not tool.IsActive():
        return
    for frame in range(frames + 1):
        finite = True
        for attr, label in attrs:
            if not attr or not _finite(attr.Get(frame)):
                report.add(
                    "NONFINITE_MOTION", label, f"Missing or nonfinite transform at frame {frame}."
                )
                finite = False
        if not finite:
            continue
        cache = UsdGeom.XformCache(Usd.TimeCode(frame))
        try:
            center = cache.GetLocalToWorldTransform(part).ExtractTranslation()
            tip = cache.GetLocalToWorldTransform(tool).ExtractTranslation()
        except RuntimeError as exc:
            report.add("TRANSFORM", CELL, f"Cannot evaluate transforms at frame {frame}: {exc}")
            return
        if not _finite(center) or not _finite(tip):
            report.add("NONFINITE_MOTION", CELL, "A composed world transform is nonfinite.")
            continue
        if not Gf.IsClose(center, part_position(frame / frames), 1e-5):
            report.add("PART_PATH", PART, f"Part leaves the expected cycle path at frame {frame}.")
        if 0.25 <= frame / frames <= 0.875 and not Gf.IsClose(
            tip, center + Gf.Vec3d(0, 0, 0.1), 1e-4
        ):
            report.add("TOOL_TRACKING", TOOL, f"Tool misses the transfer target at frame {frame}.")


def validate_stage(source: str | Path | Usd.Stage) -> ValidationReport:
    """Return bounded diagnostics; never edit or save the input stage."""
    report = ValidationReport()
    try:
        stage = open_stage(source)
        if not stage:
            raise ValueError("No stage was opened")
    except (OSError, ValueError, RuntimeError) as exc:
        report.add("STAGE_OPEN", str(source), str(exc))
        return report
    root = stage.GetRootLayer()
    try:
        _, _, unresolved = UsdUtils.ComputeAllDependencies(root.identifier)
        for path in unresolved[:12]:
            report.add("DEPENDENCY", path, "Referenced asset or sublayer cannot be resolved.")
        for error in stage.GetCompositionErrors()[:12]:
            report.add("COMPOSITION", "/", str(error))
    except RuntimeError as exc:
        report.add("DEPENDENCY", root.identifier, str(exc))
    default = stage.GetDefaultPrim()
    if not default or str(default.GetPath()) != "/World":
        report.add("DEFAULT_PRIM", "/", "Default prim must be /World.")
    if UsdGeom.GetStageMetersPerUnit(stage) != 1.0:
        report.add("UNITS", "/", "Cell dimensions are in metres; metersPerUnit must be 1.")
    if UsdGeom.GetStageUpAxis(stage) != "Z":
        report.add("UP_AXIS", "/", "Cell uses Z as its up axis.")
    report.summary["prim_count"] = sum(1 for _ in stage.Traverse())
    _hierarchy(stage, report)
    frames = _timing(stage, report)
    if frames is not None:
        _motion(stage, frames, report)
    return report
