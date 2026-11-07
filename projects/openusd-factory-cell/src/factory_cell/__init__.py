"""Export simple equipment envelopes as a real OpenUSD stage."""

import math
import re
from pathlib import Path

from pxr import Gf, Usd, UsdGeom

from .builder import build_cell
from .controller import CellController
from .validation import ValidationReport, validate_stage

__all__ = [
    "CellController",
    "ValidationReport",
    "build_cell",
    "validate_stage",
    "validate_layout",
    "write_stage",
]


def _vector(value, field, *, positive=False):
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError(f"{field} must contain three numbers")
    try:
        finite = all(type(n) in (int, float) and math.isfinite(n) for n in value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError(f"{field} must contain finite numbers representable as doubles")
    if positive and any(n <= 0 for n in value):
        raise ValueError(f"{field} dimensions must be greater than zero")
    return value


def validate_layout(layout):
    """Reject invalid layouts before any output is opened or replaced."""
    if not isinstance(layout, dict):
        raise ValueError("layout must be an object with an equipment list")
    equipment = layout.get("equipment")
    if not isinstance(equipment, list) or not equipment:
        raise ValueError("equipment must be a nonempty list")
    names = set()
    for item in equipment:
        if not isinstance(item, dict):
            raise ValueError("each equipment entry must be an object")
        name = item.get("name")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise ValueError(
                "name must start with a letter or underscore and contain only "
                "letters, digits or underscores"
            )
        if name in names:
            raise ValueError(f"duplicate equipment name: {name}")
        names.add(name)
        _vector(item.get("size_m"), f"{name}.size_m", positive=True)
        _vector(item.get("position_m"), f"{name}.position_m")


def write_stage(layout, destination):
    """Write box envelopes, with size and centre position in metres."""
    validate_layout(layout)
    destination = Path(destination)
    if destination.suffix not in {".usd", ".usda", ".usdc"}:
        raise ValueError("output must end in .usd, .usda or .usdc")
    stage = Usd.Stage.CreateInMemory()
    root = UsdGeom.Xform.Define(stage, "/FactoryCell")
    stage.SetDefaultPrim(root.GetPrim())
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    for item in layout["equipment"]:
        cube = UsdGeom.Cube.Define(stage, f"/FactoryCell/{item['name']}")
        cube.CreateSizeAttr(1.0)
        cube.AddTranslateOp().Set(Gf.Vec3d(*(float(n) for n in item["position_m"])))
        cube.AddScaleOp(UsdGeom.XformOp.PrecisionDouble).Set(
            Gf.Vec3d(*(float(n) for n in item["size_m"]))
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not stage.GetRootLayer().Export(str(destination)):
        raise OSError(f"could not write {destination}")
