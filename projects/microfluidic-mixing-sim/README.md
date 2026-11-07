# microfluidic-mixing-sim

I built a small-channel mixing simulator to learn how the underlying idea works. This is a learning project.

The channel and mixing examples are numerical simulations.

## Running my full comparison

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 micromamba run -n microfluidic python -m mixing.study --output my-results
```

The full run compares water-to-organic flow ratios of 1, 3 and 5, at total flow rates of 0.1, 0.5 and 2 microlitres per minute, for both channel shapes. It also runs analytic checks and refines both channel meshes. It runs on one processor; no GPU or commercial licence is needed. Keep the thread limits above to avoid unnecessary parallel work.

For a different operating window:

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 micromamba run -n microfluidic python -m mixing.study --rates 0.2 0.4 --ratios 2 4 --mesh 0.3 --output another-run
```

The analytic checks and mesh study retain their reference conditions. The model dimensions, liquid properties and groove definition are in [the model note](docs/model.md). Python writes all outputs under the selected folder and exits; it starts no server.

## Looking at the outputs

- `sweep.csv` contains one row per operating condition, including the outlet score, Reynolds and Peclet numbers, and concentration bounds. Reynolds number compares inertia with viscosity; Peclet number compares transport by flow with molecular diffusion.
- `sweep.json` includes every sampled cross section, its mean concentration and the mixing score. `t90_s` is the first sampled time reaching a score of 0.9; a blank CSV entry or JSON null means it was not reached inside this channel.
- `convergence.json` records how the outlet score changes as I refine the tetrahedral mesh, the small volume elements used by the solver.
- The PNG files show concentration, groove shape, transverse flow, verification error and mesh sensitivity.
- Each run writes `.xdmf` and `.h5` files for [ParaView](https://www.paraview.org/), a free 3D results viewer. Open the XDMF file to inspect concentration, pressure and velocity. These regenerable field files are not committed.
- `provenance.json` records solver versions, physical parameters and the requested sweep.

## Tests and limits

There are 2 test source files in this copy. That source count does not establish an execution result. This is a source snapshot, and running it on a new machine may need environment-specific setup.



Generated output omitted from this copy: results/ (generated output). Regenerate it with the project scripts.

The relocated workflow failed in GitHub Actions and was removed to keep the hub checks independent. Local test sources remain available.

No project-specific GitHub Actions workflow was retained. The local test sources remain in this folder.
