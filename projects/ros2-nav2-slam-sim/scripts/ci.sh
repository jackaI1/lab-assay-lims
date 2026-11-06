#!/usr/bin/env bash
set -eo pipefail
source /opt/ros/humble/setup.bash
export ROS_LOCALHOST_ONLY=1
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export GAZEBO_MODEL_DATABASE_URI=''
colcon build --symlink-install --event-handlers console_cohesion+
source install/setup.bash
colcon test --python-testing pytest --event-handlers console_cohesion+ --return-code-on-test-failure
colcon test-result --verbose
# Exercise repeated DDS startup after a discovery race was found on a clean runner.
for attempt in 1 2 3; do
  python3 -m pytest -q tests/test_logger_launch.py
done
python3 scripts/check_evidence.py results
# Outer watchdog bounds startup as well as goals. Python finally blocks stop all owned groups.
timeout --signal=INT --kill-after=30s 1000s python3 scripts/run_experiment.py --seed "${1:-7}" --output "artifacts/seed-${1:-7}"
python3 scripts/aggregate.py artifacts --output artifacts/summary.json
