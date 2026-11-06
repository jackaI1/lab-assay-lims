# Running individual parts

Use x86-64 Ubuntu 22.04 and ROS 2 Humble. The container fixes this architecture, including when built on Apple Silicon with x86 emulation. Gazebo Classic 11 is the simulator paired with this configuration. It is an older, fixed stack; a move to modern Gazebo needs different simulator plugins.

```sh
sudo apt-get update
sudo apt-get install ros-humble-navigation2 ros-humble-nav2-bringup \
  ros-humble-nav2-simple-commander ros-humble-slam-toolbox \
  ros-humble-gazebo-ros-pkgs ros-humble-launch-testing \
  ros-humble-launch-testing-ros python3-colcon-common-extensions python3-pytest python3-yaml
source /opt/ros/humble/setup.bash
colcon build --symlink-install
source install/setup.bash
export ROS_LOCALHOST_ONLY=1
export GAZEBO_MODEL_DATABASE_URI=''
```

Run these in separate terminals with the same ROS environment:

```sh
ros2 launch lab_patrol lab.launch.py mapping:=true seed:=7
ros2 run lab_patrol patrol --mapping --ros-args -p use_sim_time:=true
ros2 run nav2_map_server map_saver_cli -f /tmp/lab-map
```

Stop the mapping launch with Ctrl-C before starting localization. This avoids competing publishers for the map-to-odometry transform. The launch starts headless Gazebo; run `gzclient` on a Linux desktop to view the lab, and close that viewer when finished.

```sh
ros2 launch lab_patrol lab.launch.py mapping:=false map:=/tmp/lab-map.yaml seed:=7
ros2 run lab_patrol pose_logger --ros-args -p use_sim_time:=true -p output:=/tmp/pose-errors.csv
ros2 run lab_patrol patrol --ros-args -p use_sim_time:=true
```

The standalone patrol initializes AMCL at the known starting station. It stops on a rejected, failed or timed-out station instead of silently skipping it. The automatic experiment adds the temporary obstacle and checks recovery feedback. For the automatic run, use `bash scripts/ci.sh 19` in the container, or `python3 scripts/run_experiment.py --seed 19 --output artifacts/seed-19` in the built workspace.

The automatic run timestamps recordings with the simulation clock and records `/scan`, `/odom`, `/tf`, `/tf_static`, `/ground_truth`, `/amcl_pose` and `/clock` into SQLite ROS bags. Inspect one with `ros2 bag info artifacts/seed-7/mapping-bag`. Replay with `ros2 bag play artifacts/seed-7/mapping-bag --clock --topics /scan /odom /tf /tf_static /ground_truth /amcl_pose` after stopping the live simulator; subscribers should use `use_sim_time:=true`. Do not run live and recorded clocks together.

For multiple seeds, use fresh output directories and run sequentially in one container, or use isolated containers. DDS topics and Gazebo's port 11345 must not be shared between simultaneous runs. Combine reports with `python3 scripts/aggregate.py artifacts --output artifacts/summary.json`.

Every temporary process started by the automatic runner has a `.owner.json` file alongside its log, with its PID, process-group ownership, start time, cleanup command and final live-process check. The runner sends SIGINT, then escalates only for that owned group. Docker's init process reaps children, and `--rm` removes the stopped container. The workflow also stops its named container if a job fails or is cancelled.
