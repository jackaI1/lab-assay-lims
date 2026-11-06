# machine-panel-design

I built a control panel design for a simulated bottle-filling machine to learn how the underlying idea works. This is a learning project.

## What I put in the panel

I used a small three-phase conveyor motor, a contactor (an electrically operated power switch), an overload relay, a 24 V power supply, and a PLC (a small industrial controller). The drawings include incoming power, branch protection, controller inputs and outputs, wire endpoints, protective earth connections, and the positions of parts inside the enclosure.

| Sheet | What I can trace |
| --- | --- |
| [01](drawings/01.svg) | Supply, breakers, motor starter and earth bonds |
| [02](drawings/02.svg) | 24 V supply, controller power, fuses and fan |
| [03](drawings/03.svg) | Bottle sensor, buttons and controller inputs |
| [04](drawings/04.svg) | Output relays, hardwired inhibit, motor coil and valve |
| [05](drawings/05.svg) | Enclosure, rails, cable duct, door and cooling positions |

## What the calculations tell me

The short-circuit current rating, or SCCR, is the fault current the panel can withstand under its stated conditions. My conservative calculation follows the weakest-component part of UL 508A Supplement SB. **K1 and OL1 limit the study to 5 kA at 208 V**, above the assumed 4 kA supply fault. I do not claim a higher rating from unverified combinations of parts.

The heat calculation led to a real design change: the original unventilated box exceeded my 45 C internal target at 40 C ambient. Revision B adds a fused fan and outlet filters. [The calculation record](reports/calculations.md) shows the heat from each part, the enclosure's cooling through its walls, required installed air flow, and the selected fan's published performance. Every published input has a source; simulated loads and extra allowances are identified separately.

I kept [Revision A and the redlines](drawings/revisions) so I can see what changed and why. [The parts list](reports/bom.csv), [terminal list](reports/terminals.csv), and [layout coordinates](reports/layout.csv) come from the same data as the drawings.

## Changing the design

Edit [data/panel.json](data/panel.json), then run:

```sh
python3 -m panel build --regenerate-drawing
python3 -m unittest discover -s tests -v
python3 -m panel build --check
```

For a new PDF, open the QET file in QElectroTech, save it, choose **File > Export in pdf**, select all five sheets, and export over `drawings/bottle-filler.pdf`. Run `python3 -m panel release` after checking every page. It records hashes that keep the reviewed PDF tied to the data and native file.

The [design notes](docs/design.md) explain the circuit, hand calculations, assumptions, sequence, and limits. I have not implemented safety-rated emergency stopping, a real PLC program, or a physical temperature test.

## Tests and limits

There are 2 test source files in this copy. No test pass count is claimed here: I have not re-run the project suite as part of this move. This is a source snapshot, and running it on a new machine may need environment-specific setup.


Project checks run from this directory through the path-filtered hub workflows: (removed workflow).

Generated output omitted from this copy: reports/ (generated output). Regenerate it with the project scripts.

The relocated workflow failed in GitHub Actions and was removed to keep the hub checks independent. Local test sources remain available.
