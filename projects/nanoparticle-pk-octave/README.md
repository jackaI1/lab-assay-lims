# nanoparticle-pk-octave

I built a nanoparticle drug circulation simulator to learn how the underlying idea works. This is a learning project.

## Running it on my own data

On Ubuntu, the complete installation is:

```sh
sudo apt-get update
sudo apt-get install octave gnuplot-nox ghostscript fonts-freefont-otf
octave --no-gui --quiet scripts/run_tests.m
octave --no-gui --quiet scripts/regenerate_all.m
octave --no-gui --quiet scripts/check_results.m
```

On macOS, I use `brew install octave gnuplot`. There are no extra Octave packages or paid toolboxes. Docker is another option: `docker build -t nanoparticle-pk .` followed by `docker run --rm nanoparticle-pk`. That runs tests and regeneration inside the container; its files disappear when it exits. To keep the output on my computer, I use `docker run --rm -v "$PWD/figures:/work/figures" -v "$PWD/results:/work/results" nanoparticle-pk`.

For a different experiment, I can call the functions directly in Octave:

```matlab
addpath('src');
p = pk_parameters(2);        % Two pools, initially assumed parameters
p.dose = 50;                 % mg
p.infusion = 1.5;            % hours; use 0 for an immediate bolus
p.V = [2, 1];                % litres, central first
p.CL = 0.02;                 % central clearance, L/h
p.Q = 0.01;                  % exchange clearance, L/h
s = pk_simulate(p, [0 1 2 24 48 96]);
plot(s.time, s.concentration);
xlabel('Time (h)'); ylabel('Concentration (mg/L)');

% These are synthetic example observations, not published measurements.
f = pk_fit([2 24 48 96], [24 18 14 8], p, {'CL', 'V1'});
a = pk_sensitivity(f.params, [2 24 48 96], {'CL', 'V1', 'Q1'});
m = pk_monte_carlo(f.params, [0 2 24 48 96], {'CL', 'V1'}, 0.2, 200, 2026);
```

`pk_parameters(1)`, `(2)` and `(3)` select one, two or three compartments. Units are mg, L and hours; mg/L has the same numerical value as µg/mL. For the published example, the dose is 50 mg/m², so the fitted volumes and clearances are interpreted per square metre of body surface area. I keep that scaling explicit instead of guessing a patient size.

## Library and reproducible outputs

Each function in `src/` has a help comment with its inputs, outputs and units. `scripts/regenerate_all.m` rebuilds all four figures and seven CSV files in `results/`, including fitted parameters, concentration curves, sensitivity, every Monte Carlo draw, percentile curves and mass balance. Nothing downloads during a run.

## Tests and limits

There are 0 test source files in this copy. That source count does not establish an execution result. This is a source snapshot, and running it on a new machine may need environment-specific setup.



Generated output omitted from this copy: results/ (generated output). Regenerate it with the project scripts.

The relocated workflow failed in GitHub Actions and was removed to keep the hub checks independent. Local test sources remain available.

No project-specific GitHub Actions workflow was retained. The local test sources remain in this folder.
