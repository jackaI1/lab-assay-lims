# openusd-factory-cell

I built a small factory-cell model to learn how the underlying idea works. This is a learning project.

## Try it

I use Python 3.11 or newer for development. The generator runs on macOS, Linux and Windows without a GPU or Omniverse installation.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
factory-cell generate --output build/my-cell
factory-cell validate build/my-cell/cell.usda
```

On Windows, I activate the environment with `.venv\Scripts\Activate.ps1` in PowerShell instead of `source`. `python -m factory_cell` also works in place of `factory-cell`.

The first command creates the scene; the second prints a JSON report, a structured text format that another tool can read. A clean cell reports `"valid": true`, 193 part-position samples and an eight-second cycle. Failed checks return exit code 1. I keep the whole output folder together when sharing it.

## Change the fixture or timing

A fixture holds a part in place while another operation happens. I included two options: a clamp with jaws, and a nest with locating walls.

```sh
factory-cell generate --output build/nest-cell --fixture nest --seconds 12 --fps 30
factory-cell inspect build/nest-cell/cell.usda
```

This makes a 12-second cycle at 30 frames per second, with 361 sampled positions including both endpoints. I choose a new output directory for each generated cell so the tool never replaces my existing files. `inspect` lists the scene objects, selected fixture, layers and timing.

I can also call the same code from Python:

```python
from factory_cell import build_cell, validate_stage

stage_path = build_cell("build/python-cell", fixture="clamp", seconds=10, fps=24)
report = validate_stage(stage_path)
assert report.valid, report.to_dict()
```

## Keep a simple equipment layout

When I only need equipment envelopes, or boxes showing the space each machine occupies, I use the original JSON layout exporter:

```sh
factory-cell examples/cell.json build/layout.usda
```

I edit `examples/cell.json` to change each machine's name, `size_m` (width, depth and height in metres) and `position_m` (its centre). The last axis points up. This export has a `/FactoryCell` root and no animation. It accepts `.usd`, `.usda` and `.usdc` files. I can still call `write_stage(layout, destination)` and `validate_layout(layout)` from Python. Invalid names, duplicate equipment, bad dimensions and nonfinite values are rejected before opening the output.

## What is in the scene

I use OpenUSD, a file format for combining 3D objects and their changes over time. The `pxr` Python modules come from the `usd-core` package. A stage is the combined scene; a prim is one object in its hierarchy.

```text
World
├── Cell
│   ├── Conveyor
│   ├── Robot
│   │   └── Shoulder → Elbow → Tool
│   ├── Fixtures
│   └── Part
├── Floor
├── Light
└── Camera
```

I keep the equipment reusable and the motion editable:

| Generated file | What I put in it |
| --- | --- |
| `cell.usda` | Entry point, units and timeline settings |
| `layout.usda` | Equipment placement and references, which reuse separate asset files |
| `motion.usda` | Changes in part position and robot joints over time |
| `assets/*.usda` | Conveyor, robot, fixture and part geometry |

Layers combine edits from multiple files. Motion has priority over the layout, so I can change movement without rewriting geometry. Variants are named alternatives inside one asset: the fixture contains both `clamp` and `nest`. All asset paths are relative, so moving the entire generated folder keeps it working. I explain the tradeoffs in [the design notes](docs/design.md).

The robot is a simplified SCARA arm, with two horizontal rotating links and a vertical tool slide. I calculate its joint angles from the target position and write transforms, or position and rotation changes, at each frame. The validator checks required objects, units, dependencies, fixture selection, time samples, the part's route and the robot's transfer alignment. It reports damaged properties once instead of printing an error for every frame.

## Extension and limits

The core lives in `src/factory_cell/`. I package that folder for the command line, and the extension manifest loads the same source from the repository. `factory_cell_kit/` contains the Kit-only window and lifecycle code; it imports `omni.*`, while the core imports only Python libraries and `pxr`. Kit uses its bundled USD runtime.

The extension validates before playing and converts USD frame numbers to timeline seconds. If I switch scenes, its controls refuse to operate the other stage. Disabling it cancels a pending load, stops playback it started, and removes the window while keeping the scene open.

This is a layout and handoff preview. It does not simulate contact, gripping forces, collision clearance or robot safety, and the dwell represents time at a station rather than a simulated manufacturing operation. The validator enforces this generated cell's motion contract; it is not a general USD certification tool. I have not run the native Kit viewport on this Mac. The tests exercise the actual extension adapter through a host harness, not a GPU renderer. [Kit notes](docs/kit.md) explain that boundary.

## Tests and limits

There are 8 test source files in this copy. That source count does not establish an execution result. This is a source snapshot, and running it on a new machine may need environment-specific setup.



Retained project workflows: `openusd-factory-cell-ci.yml`. Their commands use this folder and their triggers use its paths.
