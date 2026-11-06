# ros2-nav2-slam-sim

I built a simulated robot that maps a lab and patrols it to learn how the underlying idea works. This is a learning project.

## What I can change

I put the patrol stations in [config/waypoints.yaml](config/waypoints.yaml), in metres. The lab is eight metres square. The benches and walls are defined in [config/layout.yaml](config/layout.yaml); after changing them, I run `python3 scripts/generate_world.py` with PyYAML installed to regenerate the Gazebo world. Gazebo is the simulator that moves the robot and produces its sensor readings.

I use ROS 2 Humble, which carries messages between the robot's sensors and navigation programs. `slam_toolbox` builds the map from the laser and wheel motion. SLAM means building a map while estimating where the robot is. On the second run, AMCL estimates the robot's position using that saved map. Nav2 plans routes, drives the two wheels, and runs its standard recovery behaviour tree when it cannot make progress. That tree can clear old obstacles, turn, wait, or back up.

For an existing Ubuntu 22.04 ROS 2 setup, the [run guide](docs/running.md) covers dependencies, separate launches, recording and replay. The [measurement notes](docs/measurements.md) explain what the accuracy numbers mean and what this simulation does not prove.

## Tests and limits

There are 6 test source files in this copy. That source count does not establish an execution result. This is a source snapshot, and running it on a new machine may need environment-specific setup.



Generated output omitted from this copy: results/ (generated output). Regenerate it with the project scripts.

The relocated workflow failed in GitHub Actions and was removed to keep the hub checks independent. Local test sources remain available.

No project-specific GitHub Actions workflow was retained. The local test sources remain in this folder.
