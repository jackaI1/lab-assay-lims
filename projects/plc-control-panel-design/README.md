# Filling-line control panel design

I built this drawing set to learn how controller signals, terminals and wires fit together in a control panel. It is a design study with a pinned example controller interface, rather than an installed panel.

Start with [the panel layout](design/panel-layout.svg) and [the design notes](docs/design.md). The schematic sheets are editable in KiCad. With KiCad 8 or later and Python 3 installed, run these commands from this directory:

```sh
for f in design/*.kicad_sch; do
  kicad-cli sch export netlist --format kicadxml -o "${f%.kicad_sch}.xml" "$f"
done
python3 scripts/check_io.py
python3 -m unittest discover -s tests -v
```

The checker reads `design/source-line.st`, compares its input and output names with `design/io.csv`, and follows the exported netlist connections between each controller channel and terminal. It checks for duplicate tags, terminal assignments and wire names. The drawings split supply, safety, inputs, outputs and field devices into separate sheets.

I counted four test methods in the Python test sources. This is not a certified or construction-ready panel. Actual components, fault ratings, safety validation and inspection still need separate engineering work.

## Tests and limits

There are 1 test source files in this copy. No test pass count is claimed here: I have not re-run the project suite as part of this move. This is a source snapshot, and running it on a new machine may need environment-specific setup.


Project checks run from this directory through the path-filtered hub workflows: `plc-control-panel-design-ci.yml`.
