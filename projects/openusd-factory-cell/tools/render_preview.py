"""Make a small software preview from the actual USD transforms and geometry.

Run: python tools/render_preview.py build/demo/cell.usda docs/cell-preview.gif
Requires Pillow, installed with `python -m pip install '.[preview]'`.
This is an orthographic illustration, not a Kit or RTX screenshot.
"""

import argparse
import itertools
import math
from pathlib import Path

from PIL import Image, ImageDraw
from pxr import Gf, Usd, UsdGeom


def faces(prim):
    if prim.IsA(UsdGeom.Cube):
        half = UsdGeom.Cube(prim).GetSizeAttr().Get() / 2
        vertices = [Gf.Vec3d(x, y, z) for x, y, z in itertools.product((-half, half), repeat=3)]
        indices = [
            (0, 1, 3, 2),
            (4, 6, 7, 5),
            (0, 4, 5, 1),
            (2, 3, 7, 6),
            (0, 2, 6, 4),
            (1, 5, 7, 3),
        ]
    elif prim.IsA(UsdGeom.Cylinder):
        cylinder = UsdGeom.Cylinder(prim)
        radius = cylinder.GetRadiusAttr().Get()
        half = cylinder.GetHeightAttr().Get() / 2
        vertices = [
            Gf.Vec3d(radius * math.cos(i * math.tau / 12), radius * math.sin(i * math.tau / 12), z)
            for z in (-half, half)
            for i in range(12)
        ]
        indices = [tuple(range(11, -1, -1)), tuple(range(12, 24))]
        indices += [(i, (i + 1) % 12, (i + 1) % 12 + 12, i + 12) for i in range(12)]
    else:
        return []
    return [[vertices[i] for i in face] for face in indices]


def project(point):
    x, y, z = point
    return (420 + 75 * (0.8 * x + 0.6 * y), 310 + 75 * (0.32 * x - 0.43 * y - 0.84 * z))


def render(stage, frame):
    image = Image.new("RGB", (880, 490), "#edf2f5")
    draw = ImageDraw.Draw(image)
    cache = UsdGeom.XformCache(Usd.TimeCode(frame))
    polygons = []
    for prim in stage.Traverse():
        polygons_local = faces(prim)
        if not polygons_local:
            continue
        transform = cache.GetLocalToWorldTransform(prim)
        color_attr = UsdGeom.Gprim(prim).GetDisplayColorAttr().Get()
        color = color_attr[0] if color_attr else Gf.Vec3f(0.5)
        for index, polygon in enumerate(polygons_local):
            world = [transform.Transform(v) for v in polygon]
            depth = sum(0.5 * p[0] - 0.7 * p[1] + 0.5 * p[2] for p in world) / len(world)
            # Display colors are linear. Convert to sRGB for the software image.
            shade = 0.76 + 0.04 * (index % 6)
            rgb = tuple(round(255 * min(1, float(c)) ** (1 / 2.2) * shade) for c in color)
            polygons.append((depth, [project(v) for v in world], rgb))
    for _, polygon, color in sorted(polygons, key=lambda p: p[0]):
        draw.polygon(polygon, fill=color, outline="#394b58")
    time = frame / stage.GetTimeCodesPerSecond()
    draw.text(
        (26, 20), "FACTORY CELL / conveyor, robot and interchangeable fixture", fill="#163149"
    )
    draw.text((26, 42), "Software preview sampled from the generated USD stage", fill="#496276")
    phase = frame / stage.GetEndTimeCode()
    label = (
        "Infeed"
        if phase < 0.25
        else "Transfer to fixture"
        if phase < 0.5
        else (
            "Fixture dwell"
            if phase <= 0.625
            else "Transfer to outfeed"
            if phase < 0.875
            else "Discharge"
        )
    )
    draw.text((26, 454), f"{time:0.2f} s   |   {label}   |   green = moving part", fill="#163149")
    draw.line((26, 478, 854, 478), fill="#c6d4df", width=4)
    draw.line((26, 478, 26 + 828 * phase, 478), fill="#198654", width=4)
    return image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    stage = Usd.Stage.Open(str(args.stage))
    frames = [render(stage, float(stage.GetEndTimeCode()) * i / 64) for i in range(65)]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    duration = round(1000 * stage.GetEndTimeCode() / stage.GetTimeCodesPerSecond() / 64)
    frames[0].save(args.output, save_all=True, append_images=frames[1:], duration=duration, loop=0)
    frames[32].save(args.output.with_suffix(".png"))
    print(f"Wrote {args.output}: {len(frames)} frames")


if __name__ == "__main__":
    main()
