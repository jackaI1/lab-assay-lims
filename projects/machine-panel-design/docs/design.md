# Bottle-filling panel design record

I used a small filling line to work through the parts of a control panel that a sequence diagram leaves out: power protection, wire endpoints, heat inside the box, and what must change when an assumption fails. This is a simulated engineering study. I have not assembled, energized, measured, certified, or obtained a UL listing for this panel.

## Design inputs

These are authored scenario assumptions, identified as `scenario` in the data, rather than borrowed manufacturer claims:

| Input | Chosen value and reason |
| --- | --- |
| Supply | 208 V line-to-line, grounded-wye, three-phase, 60 Hz; no neutral used |
| Prospective fault at incoming terminals | 4 kA rms symmetrical, assumed for the study, not a utility measurement |
| Conveyor M1 | Simulated 0.37 kW, 208 V, 2.0 A nameplate; motor outside the cabinet |
| Fill valve YV1 | Simulated normally closed spring-return valve, 24 V DC, 6 W, suppressed coil |
| Bottle sensor S4 | Simulated three-wire PNP sensor, brown +24, blue 0 V, black signal, 0.5 W |
| H1 run lamp | Simulated 24 V, 0.5 W door indicator |
| S0/S3 | Simulated two-pole NC stop and enable switches; one pole inhibits output supply, the other reports status |
| S1/S2 | Simulated NO start and reset pushbuttons |
| Enclosure E1 | Steel, 600 H x 400 W x 200 D mm, wall mounted, rear against wall, bottom obstructed, indoor clean dry air |
| Environment | 40 C continuous ambient; 45 C design target inside; sea level (0-100 m); no solar loading |
| Wire choices | 14 AWG copper power/PE and 18 AWG copper control as initial design choices, subject to installation-specific ampacity/derating review |
| Extra heat | 2 W internal wiring allowance; 0.3/0.2/0.3 W for F3/F4/F5; X0/X1 0.2 W per strip, X2/PE 0.1 W per assembly |
| Duty | Simultaneous rated heat entries, fan always on; no duty-cycle reduction |
| Layout envelopes | Conservative planning dimensions in each component record; only PS1, K1 and fan have explicitly sourced envelope references; final fit must be checked against vendor drawings |
| Air-flow allowance | Multiply calculated delivered flow by 1.25 for an initial selection allowance; verify actual dirty-filter performance in a physical build |

The DC fuse holders are Eaton CHCC1DU with FNQ-R-1/FNQ-R-2 fuses. Their heat entries are explicit design allowances at this small load, not manufacturer watt-loss claims. Terminal strips use Phoenix Contact PT 2,5 feed-through terminals and separate PT 2,5-PE earth terminals. Quantity means purchasing units; `heat_w` is the loss of the entire tagged assembly, so I do not multiply heat by quantity. PE is an assembly including inlet/motor earth terminals, earth bar, enclosure bond, door bond and the intentional DC bond. DIN rails, duct, enclosure and external field hardware are included in the BOM. `SIM-` parts are simulation specifications, not orderable products. Ferrules, end stops, labels, glands and mounting fasteners remain build-detail consumables rather than a released procurement package.

## Power circuit

Sheet 01 starts at X0, then Q0, a three-pole 6 A UL 489 breaker. After Q0 the power splits into Q1, the three-pole 6 A motor branch, and Q2, a two-pole 2 A control-supply branch. Q0 and Q1 have the same trip curve and rating; I make no selective coordination claim. A fault may open the incoming breaker too.

The motor path is Q1 -> K1 contactor -> OL1 thermal overload -> X1 -> M1. OL1 is set to the simulated 2.0 A nameplate with manual reset. K1 has a 24 V DC coil, and its 13-14 auxiliary contact reports movement to the PLC. Q2 feeds the L and N input terminals of PS1 from L1 and L2 at 208 V. Both conductors are ungrounded and both are protected and opened together; the terminal named N on PS1 does not imply a supply neutral. PS1 accepts this AC input range and supplies 24 V at up to 2.5 A.

The incoming PE conductor bonds the earth bar, motor frame, cabinet and door. It is neither switched nor fused. Sheet 02 shows one intentional 0 V-to-PE bond. Matching net names are cross-sheet electrical references; the `PE` port at the DC bond is the intentional exception joining 0 V and PE. A wire crossing without a shared terminal is not a junction. Original functional symbols are embedded in the QElectroTech project, with real QET terminals and conductor objects. The contactor coil and auxiliary contact have the same physical tag as their power poles, rather than appearing as extra purchased contactors.

## PLC and sequence

The PLC is a CLICK C0-00DR-D with relay outputs. Its inputs have C1/C2 commons bonded to 0 V; positive 24 V signals drive X1-X7. X8 is spare. Dry relay outputs use C3 for Y1-Y4, and C4/Y5/Y6 are left unused. Each selected load is under the published 1 A-per-output rating: K1 5.4/24 = 0.225 A, YV1 6/24 = 0.250 A, and H1 0.5/24 = 0.021 A. Their combined demand is below the 4 A C3 group rating. K1's BD coil has built-in suppression; YV1 uses a flyback diode with its cathode at positive supply. The DC load budget includes the external valve and sensor, even though their heat is outside the cabinet.

| PLC point | Meaning |
| --- | --- |
| X1 | Bottle present, S4 PNP output |
| X2 | Start, S1 NO |
| X3 | Stop healthy, S0 second NC pole |
| X4 | Enable healthy, S3 second NC pole |
| X5 | Overload tripped, OL1 97-98 NO |
| X6 | Contactor feedback, K1 13-14 NO |
| X7 | Reset, S2 NO |
| Y1 | K1 conveyor coil |
| Y2 | Fill valve YV1 |
| Y3 | Run lamp H1 |

S0, S3 and OL1 95-96 are physically in series ahead of C3. Opening one removes power from Y1-Y4 loads independently of the PLC program. This is an educational inhibit circuit, not a safety-rated emergency stop. The PLC remains powered for diagnostics.

`python3 -m panel simulate` runs a deterministic Python model, not PLC firmware. Start moves a bottle; the bottle sensor stops the conveyor and opens the valve for two seconds. The conveyor then clears the bottle and returns to convey. Losing the bottle during fill or missing K1 feedback for more than 0.5 s faults the cycle. Stop, disabled enable, or overload turns outputs off. Recovery requires healthy contacts, reset with start released, and a new start edge. A real PLC implementation, feedback dropout during filling, guarding, safe torque removal, fault diagnostics and a machine risk assessment are outside this study.

## SCCR method and boundary

SCCR means short-circuit current rating, the fault current equipment can withstand under its specified conditions. It is different from normal operating current and from a breaker's interrupting rating, its ability to clear a fault.

I implement the conservative weakest-component part of UL 508A Supplement SB, using the published [Eaton procedure](https://www.eaton.com/content/dam/eaton/markets/machinebuilding/protect-personnel-assets-and-machine-reliability/documents/documents-english-language/eaton-control-panel-design-guide-ul-508a-br033001en-us.pdf) and the [Mersen reproduction of Table SB4.1](https://www.mersen.com/sites/default/files/files_imported_ep/WP-Achieving-Higher-Short-Circuit-Current-Ratings-for-Industrial-Control-Panels.pdf). The power-path components and branch protective devices are explicitly in scope. Q2 is included even though it supplies controls. PS1 and its downstream control-only devices are excluded using the control-supply boundary described in [ABB's SB3.2.1 guidance](https://electrification.us.abb.com/nec409ul-508a-support).

The study uses 10 kA for Q0/Q1/Q2, conservatively taking the lower published UL interrupting figure, 10 kA default for X0/X1 feed-through terminals, and 5 kA default for K1 and OL1. I do not claim a larger manufacturer tested combination rating. Their minimum is **5 kA at 208 V**, with **K1 and OL1 tied as the limiting components**. This exceeds the assumed 4 kA site fault; at 6 kA the calculator reports inadequate. Changing a rated voltage below 208 V, omitting an in-scope rating, or using a delta supply fails validation.

I do not apply fuse let-through credit, series ratings, motor contribution, transformer exceptions, or automatic tested-combination lookup. A branch breaker with a lower interrupting rating caps the answer. All ratings have a source and a basis field. This is a documented calculation exercise, not the complete UL 508A assessment and not an instruction to apply an SCCR nameplate to hardware.

## Heat and cooling

The PLC input allowance is `26.4 * (2*0.006 + 5*0.005) = 0.9768 W`, using the maximum published currents for all seven connected input channels. I charge this to both the DC budget and panel heat in addition to CPU consumption. Adding it pushed the one-outlet fan arrangement below my 25% selection allowance, so I used the published two-outlet arrangement.

The [input-source index](sources.md) locates every published numerical input. Manufacturer figures account for the breaker assemblies (3.5 + 3.5 + 2.8 W), K1 (three 0.2 W AC-3 poles plus its 5.4 W DC coil), OL1 (1.67 W), PLC (24 x 0.120 = 3.8568 W including its seven input channels), and the supply. The overload publication labels its thermal burden VA; I treat it as resistive watts. PS1's full-load estimate is `60 * (1 / 0.90 - 1) = 6.667 W`, based on typical efficiency. That is a planning estimate, not a guaranteed worst-case dissipation at 208 V or all load fractions. I have kept the full-load estimate despite the much smaller actual DC budget. I include a conservative 3 W fan allowance because the current fan performance table says 2.4 W while its legacy tender text still says 3 W. The report separates sources and allowances for review.

Following [Rittal's published heat-balance method](https://www.rittal.com/imf3/none/3_8419/3305500_Catalogo_tecnico_EN/), with steel heat-transfer coefficient `k = 5.5 W/(m2 K)`, I calculate:

```text
A = W*H + 2*D*H + W*D = 0.56 m2    (front + sides + top)
G = k*A = 3.08 W/K
natural rise = Q/G
surface cooling = G*(Tlimit - Tambient)
residual cooling = max(0, Q - surface cooling)
required air = 3.1 * residual cooling / (Tlimit - Tambient)
selected air requirement = required air * 1.25
```

The area is conservative exposed geometry that omits rear and bottom. I do not claim a full IEC TR 60890 enclosure verification. The air factor is Rittal's sea-level factor in m3 K/(W h); it must change at altitude. At 34.893 W, passive rise is 11.329 K, so the interior reaches 51.329 C at 40 C ambient. At the 45 C target, walls remove 15.4 W and the fan must remove 19.493 W. Required delivered flow is 12.086 m3/h, or **15.107 m3/h with the chosen 25% allowance**. B1 plus EF1 and EF2 outlets provides **16 m3/h**, giving an estimated **44.234 C** inside with clean filters.

If ambient equals or exceeds the target, the calculator returns a refrigeration requirement in watts, including enclosure heat gain, and no finite fan recommendation. Fan selection uses installed flow with an outlet filter, never the larger 20 m3/h free-air figure. This small flow margin needs a physical temperature test and filter-maintenance plan before a build. This model omits hot spots, solar input, humidity, actual filter fouling and airflow obstruction. Filtered ventilation suits this clean indoor simulation; it is not a washdown enclosure design.

## Layout and revisions

Sheet 05 uses millimetres at one drawing unit per millimetre. [Layout coordinates](../reports/layout.csv) give x/y and envelopes from the backplate upper-left. Power sits left of the centre duct and low-voltage control sits right. Rails, cable duct, bottom cable entry, door controls, side intake and high outlets are visible. I reserve PS1's required top/bottom ventilation space. The side outline shows positions projected onto one side view; intake and both outlets are on opposite walls in the intended assembly.

I retained an actual design iteration as Revision A in [drawings/revisions](../drawings/revisions). It is the passive design that failed the 40 C thermal review. Revision B adds F5, B1, EF1 and EF2, with a machine-readable A-to-B redline and red marks on the layout. Both iterations were made in this project change; these are design revisions, not fabricated past commits. Revision A is intentionally not a releasable design. Its side view is empty and its report records the failed cooling result.

## Data, drawings and checks

`data/panel.json` is the source for component ratings, heat, sources, locations, terminals, wires, layout and I/O. `python3 -m panel build` refreshes reports and previews while auditing the existing QET file. After an intentional drawing/data change, `python3 -m panel build --regenerate-drawing` creates the native drawing too. The generated original symbols can be opened and edited in QElectroTech without a separate symbol library. For a permanent design change, update the data first so BOM, calculations, previews and native file stay aligned. A manual native edit that changes a part, position, endpoint or rating must be reconciled with the data before CI passes.

The independent XML audit checks sheet count, component identity, purchasing quantity, visible part text, heat, SCCR, pin coordinates and the multiset of terminal-to-terminal conductors with net labels. Generated reports and SVGs are checked against fresh output. Mutation tests deliberately corrupt the rating, heat, visible part, wire endpoint, wire count and BOM output. The audit is not an electrical rule checker, a protection-coordination study or a substitute for reviewing the connections.

The release manifest binds the visually checked PDF, data, and native drawing by SHA-256. CI requires that manifest. A hash proves file identity, not engineering correctness or an independent visual inspection. QElectroTech saved and exported the final five sheets on 2026-11-05; I removed its local saved-file path before publishing.
