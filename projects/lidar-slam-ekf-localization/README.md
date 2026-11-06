# lidar-slam-ekf-localization

I built a small robot mapping and localization experiment to learn how the underlying idea works. This is a learning project.

## Try it

Install Python 3.9 or newer and a C++ compiler, then run:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
make test
make benchmark
```

The benchmark writes `results/metrics.json` and one compressed NumPy file per seed. The latter contains the true and estimated paths, the surveyed and newly built occupancy maps, the corrected map and the loop constraint. For example:

```sh
python -c "import numpy as np; r=np.load('results/run-7.npz'); print(r.files); print(r['graph'])"
```

The numbers are metres. Absolute trajectory error is the root mean square distance between estimated and true positions in the same coordinate frame. Final drift is their distance at the end of the run. The graph is evaluated at its nine keyframes, while the other paths use all 81 poses. No alignment to ground truth is applied.

## How it works

The extended Kalman filter (EKF) predicts position from noisy wheel motion and corrects heading with the simulated IMU. The particle filter keeps many possible poses, scores laser endpoints against occupied map cells, and resamples when too few particles carry the weight. A likelihood field measures each endpoint's distance to the nearest occupied cell. The occupancy grid records evidence for free and occupied space, and a separate voxel function groups 3D points by cell.

The C++ iterative closest point (ICP) matcher finds a rigid transform between two scans using nearest neighbours. The Python pose graph holds relative odometry constraints and the scan-matched loop constraint, then adjusts keyframe poses with least squares. It anchors the first pose to remove the global coordinate ambiguity. This experiment assumes the final scan is a loop candidate; it does not detect loop candidates automatically. Its reference map is generated from surveyed simulator poses, so the localization results do not measure errors in map surveying.

The voxel function is a building block only: this repository does not yet reconstruct a 3D mesh, train Gaussian splats, or process camera and lidar data from a real driving dataset. Laser scans are simulated in 2D; there is no ROS 2 wrapper. ICP can also converge to an incorrect match when its initial guess is poor or the scene is repetitive.

## Tests and limits

There are 1 test source files in this copy. That source count does not establish an execution result. This is a source snapshot, and running it on a new machine may need environment-specific setup.



The relocated workflow did not complete successfully within the migration batch. Local test sources remain available.

No project-specific GitHub Actions workflow was retained. The local test sources remain in this folder.
