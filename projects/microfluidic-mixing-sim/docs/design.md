# Which channel would I try next?

I would try the grooved channel next, while keeping the smooth channel as a
control. At the same flow settings, the grooved version has a higher outlet
mixing index in all nine comparisons. The advantage is small in this short
device. I have not established an optimal groove depth, number of cycles,
pressure cost or nanoparticle formulation.

## Comparison at the saved sweep mesh

The channel is 200 µm wide, 100 µm high and 1.6 mm long after the Y-junction.
The grooves are 25 µm deep. These numbers use the 30 µm maximum mesh spacing;
the mesh study below is a separate, finer reference check.

| Water/organic ratio | Total flow (µL/min) | Smooth outlet index | Grooved outlet index |
| --- | --- | --- | --- |
| 1 | 0.1 | 0.9968 | 0.9976 |
| 1 | 0.5 | 0.7529 | 0.7730 |
| 1 | 2 | 0.3780 | 0.3992 |
| 3 | 0.1 | 0.9973 | 0.9979 |
| 3 | 0.5 | 0.7912 | 0.8080 |
| 3 | 2 | 0.4629 | 0.4817 |
| 5 | 0.1 | 0.9977 | 0.9983 |
| 5 | 0.5 | 0.8238 | 0.8379 |
| 5 | 2 | 0.5387 | 0.5550 |

The grooves create transverse motion in the solved flow, visible in
[the cross-section plot](../results/herringbone-crossflow.png). They also
increase channel volume, so the comparison at equal total flow includes
about 4.7% more nominal residence time. I cannot attribute the full gain to
stretching alone without an additional equal-volume control.

Increasing the water fraction gives a thinner organic stream and changes
the solvent dilution as well as the mixing score. I normalize each ratio
against its own segregated inlet variance. A high ratio is therefore not
automatically a better formulation; it changes the composition delivered
to any later nanoparticle process.

## How much does mesh choice matter?

At ratio 3 and 0.5 µL/min:

| Maximum spacing (µm) | Tetrahedra | Smooth index | Grooved index | Grooved minus smooth |
| --- | --- | --- | --- | --- |
| 60 | 1,442 | 0.82310 | 0.83796 | 0.01486 |
| 40 | 3,424 | 0.79320 | 0.80967 | 0.01647 |
| 30 | 8,281 | 0.79125 | 0.80803 | 0.01678 |
| 22 | 19,526 | 0.78282 | 0.80041 | 0.01759 |

The sign of the geometry difference survives all four meshes, while the
absolute indices continue to change. The last refinement changes the smooth
score by 0.00842 and the grooved score by 0.00761. This is not clean
asymptotic convergence, so I do not report a Richardson-extrapolated value
or claim mesh independence. The geometry itself changes as its rounded
grooves are resolved. The 30 µm sweep is suitable for preliminary comparison,
not a final manufacturing decision. Flow imbalance is below 4 × 10⁻¹⁵
for these reference runs; that checks volume conservation, not scalar accuracy.
Doubling the section integration grid from 32² to 64² points changes the
finest-mesh outlet index by less than 0.000071 for either geometry. This
sampling error is much smaller than the observed finite-element mesh effect.

The highest-flow runs have concentration overshoots as large as approximately
0.28 above the physical maximum of 1, and undershoots down to about -0.20.
These are numerical errors from the stabilized linear transport discretization,
not physical solvent fractions. Even at ratio 3 and 0.5 µL/min, the maximum
is approximately 1.12. I save the raw bounds and do not clip the figures or
indices into a more flattering result. The high-flow comparisons are
exploratory; they need finer interface meshes or a bound-preserving transport
method before quantitative design use. The 0.1 µL/min runs stay within about
0.0011 of the physical range.

## Mixing time and Peclet scaling

Molecular diffusion across width W takes a characteristic time W²/D, which
is **40 s** for these inputs. At 0.1 µL/min, U is 83.3 µm/s, Pe based on H
is 8.33, and the corresponding smooth-channel characteristic length is
3.33 mm. This is the textbook scaling `L/W ~ Pe_W`.

The first station reaching a mixing index of 0.9 occurs at **6.6 s** for
ratios 1 and 3 and **5.4 s** for ratio 5, for both geometries. That is
0.135 to 0.165 of W²/D. The same smooth-channel diffusion equation predicts
decay of its slowest transverse mode on W²/(π²D) = 4.05 s; reaching a given
index adds a logarithmic threshold factor. The inlet already supplies
several seconds of contact before my x/U clock starts, so I expect a
different prefactor from the simple width-crossing estimate. This is agreement
in scale, not an exact validation of mixing time.

At 0.5 and 2 µL/min, neither geometry reaches 0.9 in the sampled 1.55 mm.
Those times are saved as null, not extrapolated. At ratio 3, the nominal
full-device residence times are 4.65 s and 1.16 s for the smooth geometry,
and 4.87 s and 1.22 s for the grooved geometry. Faster flow raises Pe and
reduces the time available to diffuse. I cannot infer the logarithmic
high-Pe mixing-length scaling of a long chaotic mixer from eight grooves.

My next useful run would use more groove cycles, a finer mesh around the
solvent interface, and an equal-volume smooth control. I would also compare
pressure drop and check finite-inertia flow before selecting a throughput.
Actual particle formation would still need formulation-specific measurements.
