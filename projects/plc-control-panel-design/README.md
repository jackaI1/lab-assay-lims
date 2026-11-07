# Filling-line control panel design

I wanted to learn how a control panel drawing connects power, safety circuits and field devices, so I built a practice filling-line drawing set and an I/O checker.

I use illustrative component loads and a practice filling-line design.

Start with [the panel layout](design/panel-layout.svg) and [the wiring notes](docs/design.md). The layout is drawn in millimetres. Open the `.kicad_sch` files in [KiCad](https://www.kicad.org/) to inspect the five editable sheets. The [I/O table](design/io.csv) gives each signal a terminal and wire number. This is a design study, not a construction-ready or certified panel: actual components, fault ratings, safety validation, and local inspection are still needed.

## Try the checks

Install KiCad 8 or later and Python 3, then from the project directory run:

```sh
for f in design/*.kicad_sch; do
  kicad-cli sch export netlist --format kicadxml -o "${f%.kicad_sch}.xml" "$f"
done
python3 scripts/check_io.py
python3 -m unittest discover -s tests -v
```

A netlist is the list of electrically connected pins exported from a schematic. The checker verifies all 15 input and output names against a pinned copy of [my filling-line program](https://github.com/jackaI1/plc-filling-line), then checks that each assigned controller channel and terminal share its wire. It also catches duplicate tags, terminals and wires. The circuit blocks are functional representations; the wiring notes explain what must be resolved before buying parts or wiring equipment.

## Tests and limits

I kept 1 files of test code and supporting test helpers in this copy. This is a file inventory, not an execution result. This is a source snapshot, and running it on a new machine may need environment-specific setup.


Project checks run from this directory through the path-filtered hub workflows: `plc-control-panel-design-ci.yml`.
