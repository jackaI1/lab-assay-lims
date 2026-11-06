"""Validated waypoint routes and a bounded Nav2 action patrol."""
import json
import math
from pathlib import Path
import time
import yaml


def load_waypoints(path):
    data = yaml.safe_load(Path(path).read_text())
    rows = data.get('waypoints') if isinstance(data, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ValueError('waypoints must be a nonempty list of [x, y, yaw]')
    result = []
    for row in rows:
        if not isinstance(row, list) or len(row) != 3 or any(
                isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in row):
            raise ValueError(f'Invalid waypoint: {row!r}')
        result.append(tuple(float(v) for v in row))
    return result


def patrol(navigator, poses, timeout_s=180, on_feedback=lambda feedback: None):
    """One goal at a time; an abort never silently skips a patrol station."""
    results = []
    for index, pose in enumerate(poses):
        # Humble keeps the preceding goal's feedback until a new message arrives.
        stale_feedback = navigator.getFeedback()
        if not navigator.goToPose(pose):
            raise RuntimeError(f'Waypoint {index} was rejected')
        deadline = time.monotonic() + timeout_s
        recoveries = 0
        while not navigator.isTaskComplete():
            feedback = navigator.getFeedback()
            if feedback is not None and feedback is not stale_feedback:
                recoveries = max(recoveries, feedback.number_of_recoveries)
                on_feedback(feedback)
            if time.monotonic() > deadline:
                navigator.cancelTask()
                raise TimeoutError(f'Waypoint {index} exceeded {timeout_s}s')
        result = navigator.getResult()
        # nav2_simple_commander TaskResult.SUCCEEDED has value 1 in Humble.
        if getattr(result, 'value', result) != 1:
            raise RuntimeError(f'Waypoint {index} failed: {result}')
        results.append({'waypoint': index, 'recoveries': recoveries, 'succeeded': True})
    return results


def ros_pose(node, x, y, yaw):
    from geometry_msgs.msg import PoseStamped
    pose = PoseStamped()
    pose.header.frame_id = 'map'
    pose.header.stamp = node.get_clock().now().to_msg()
    pose.pose.position.x, pose.pose.position.y = float(x), float(y)
    pose.pose.orientation.z, pose.pose.orientation.w = math.sin(yaw/2), math.cos(yaw/2)
    return pose


def main(args=None):
    import argparse
    import rclpy
    from nav2_simple_commander.robot_navigator import BasicNavigator
    from ament_index_python.packages import get_package_share_directory
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--waypoints', default=str(Path(get_package_share_directory('lab_patrol')) / 'config/waypoints.yaml'))
    parser.add_argument('--mapping', action='store_true')
    parser.add_argument('--timeout', type=float, default=180)
    opts, ros_args = parser.parse_known_args(args)
    route = load_waypoints(opts.waypoints)
    rclpy.init(args=ros_args)
    nav = BasicNavigator()
    try:
        nav.setInitialPose(ros_pose(nav, 0, 0, 0))
        nav.waitUntilNav2Active(localizer='bt_navigator' if opts.mapping else 'amcl')
        print(json.dumps(patrol(nav, [ros_pose(nav, *p) for p in route], opts.timeout)))
    finally:
        nav.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
