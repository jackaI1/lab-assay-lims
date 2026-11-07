# Model and reproducibility

I use solvent mixing as one part of understanding lipid-nanoparticle production.
An organic stream carrying lipid meets an aqueous stream. This model follows
only the solvent fraction; it does not simulate lipid assembly, particle size,
encapsulation or a particular commercial cartridge.

## Geometry and units

All solver coordinates are divided by channel height H = 100 µm. The main
channel is 200 µm wide, 100 µm high and 1,600 µm long. Two 100 µm-wide inlet
arms join it through an actual Y-shaped volume. The inlets are at x = -300 µm;
the branch separation ends at x = -75 µm. x = 0 marks the start of the
constant-width channel, not the inlet boundary.

The grooved version has eight rounded chevron grooves, 25 µm deep, 90 µm
wide in the axial direction, at 150 µm pitch. The chevron apex moves between
y = -W/6 and +W/6 after each pair of grooves. These are four alternating
half cycles of a small staggered-herringbone design, not a replica of a
manufacturer's device. Groove centerlines are

`x/H = 2 + 1.5 k + 0.65 abs(y/H - apex_k)`, k = 0,...,7.

`geometry.floor` depresses the floor with a cosine profile across each groove.
Gmsh makes an unstructured tetrahedral Y-channel mesh. I map its vertical
coordinates from [0,1] to [floor(x,y),1]. The resulting affine tetrahedra
approximate the rounded floor; refining the mesh refines the geometry too.
The constructor checks signed element Jacobians before and after the map
and rejects an inverted or collapsed tetrahedron.
This is a 3D wall shape that drives transverse motion, not an imposed swirl
velocity or a 2D herringbone drawing.

## Flow and concentration

I solve steady incompressible Stokes flow:

`-div(2 μ sym(grad u)) + grad p = 0`, `div u = 0`.

The fluid has constant μ = 0.001 Pa s and density 1,000 kg/m³. There is no
slip on the walls. The two inlet velocities have smooth, zero-at-wall
profiles and specified integrated flow rates. I normalize the interpolated
profiles on each mesh so the requested flow rates are exact. The outlet has
zero natural traction. Quadratic velocity and linear pressure elements
(Taylor-Hood P2/P1) form the mixed finite element problem. PETSc/MUMPS solves
the coupled sparse system. Outlet traction fixes the pressure reference.

For each flow-rate ratio, I solve one dimensionless velocity with total
flux 2 and mean main-channel velocity 1. Stokes flow is linear, so changing
total flow scales that velocity exactly within this model. The scalar solve
uses the corresponding Pe = UH/D, where U = Q/(WH). The physical diffusivity
is D = 10⁻⁹ m²/s, an illustrative solvent diffusivity, not a measured value
for a particular formulation. Water/organic ratios are 1, 3 and 5; total
flow rates are 0.1, 0.5 and 2 µL/min. Re based on H ranges from 0.0083 to
0.167. Inertia is omitted; the upper endpoint is a screening approximation
and should be checked with Navier-Stokes before using it for design.

The steady solvent equation is `u · grad c - D laplacian(c) = 0`, with c = 1
at the organic inlet and c = 0 at the aqueous inlet. Walls and outlet have
zero natural diffusive flux. I use continuous linear concentration elements
and streamline-upwind/Petrov-Galerkin (SUPG) stabilization, which adds a
residual along streamlines. Its time scale combines diffusion and advection:

`tau = [(2|u|/h)² + (4/(Pe h²))²]^(-1/2)`.

SUPG is not positivity preserving. The CSV records raw minimum and maximum
concentration. I do not clip concentrations to make mixing look better.
The design note reports mesh sensitivity rather than treating one mesh as
the physical answer. Finite-element stabilization can create numerical
mixing, especially when the interface is narrower than a cell.

## Mixing index and time

At 16 stations from x = 50 to 1,550 µm, I sample concentration and axial
velocity on a uniform area grid across the full meshed cross section,
including the grooves. Samples outside the actual tetrahedral mesh are
discarded. Weights are forward axial velocity, so stagnant fluid contributes
little to the material leaving a section. Reverse flux is reported separately
in every station record. The default quadrature is 32 by 32; it is distinct
from the finite-element mesh. The tests also check sample-grid sensitivity.

`M = 1 - sqrt(<(c - <c>)²>_flux / [c_in (1-c_in)])`,
where `c_in = 1/(1 + water/organic ratio)`.

M = 0 represents separated inlet streams; M = 1 represents a uniform solvent
fraction. I use the inlet segregated variance for every station, including
unequal ratios. The local mean is also saved so material-balance drift is
visible. I do not renormalize every ratio to a 50/50 feed.

The predicted mixing time t90 is the first sampled station with M ≥ 0.9,
using the nominal advective time x/U from the constant-width channel start.
This is a station-resolution estimate, not a Lagrangian residence-time
distribution. It includes the inlet's effect on concentration but excludes
the inlet transit from its clock. If no station reaches 0.9, t90 is null,
meaning the channel is too short at that operating condition. Volume/Q is
reported separately as the nominal residence time of the entire device.

For a smooth channel, diffusion gives `t ~ W²/D = 40 s` and
`L ~ U W²/D = Pe_W W`. This is a characteristic scale, not the exact time
to reach this project's 90% index. The first transverse diffusion mode has
an additional 1/π² factor, and unequal inlet ratios change its amplitude.
Herringbone stretching can shorten the diffusion distance; a finite-device
sweep does not establish a logarithmic high-Pe asymptote.

## Verification

`verification.poiseuille` uses the same mixed weak form as the 3D flow solve
on a 2D channel with exact boundary data: u = (y(1-y),0), p = 2(1-x).
P2/P1 represents these polynomials exactly, so this checks the pressure,
velocity and coupling to numerical precision, not an empirical convergence
order. A separate P1 reduced momentum problem checks second-order L2
convergence against the same parabolic profile.

`verification.diffusion` solves the time-dependent 1D heat/diffusion equation
with initial sin(πx), zero endpoints and analytic solution
`sin(πx) exp(-π²t)`. Backward Euler time steps scale with h², so combined
space/time errors should decrease fourfold on each mesh refinement.

The mixer mesh study runs both geometries at four mesh sizes,
ratio 3 and 0.5 µL/min. It reports outlet mixing index and flow imbalance.
`sampling.json` separately compares 16², 32² and 64² area samples on the
finest mesh, separating integration error from finite-element mesh error.
It is a sensitivity study, not proof of asymptotic convergence of every
ratio, groove parameter or high-Pe scalar boundary layer.

## References

- [Belliveau et al., Microfluidic Synthesis of Highly Potent Limit-size Lipid Nanoparticles (2012)](https://pmc.ncbi.nlm.nih.gov/articles/PMC3442367/)
  explains the solvent-mixing context for lipid-nanoparticle formation. My
  low-flow screening study is not a reproduction of its formulation experiments.
- [FEniCSx 0.9 Taylor-Hood Stokes formulation](https://docs.fenicsproject.org/dolfinx/v0.9.0/python/demos/demo_stokes.html)
  describes the mixed flow discretization and solver options.
- [Gmsh integration in FEniCSx](https://docs.fenicsproject.org/dolfinx/v0.9.0/python/demos/demo_gmsh.html)
  describes conversion of physical mesh tags into finite-element meshes.
- [Stroock et al., Chaotic Mixer for Microchannels, Science (2002)](https://www.gmwgroup.harvard.edu/publications/chaotic-mixer-microchannels)
  motivates alternating herringbone grooves and the comparison with smooth
  diffusion-limited channels. The paper's device and measurements are not
  validation data for my different geometry.
