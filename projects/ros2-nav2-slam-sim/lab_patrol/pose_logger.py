"""CSV logger: AMCL estimates are paired with bracketing simulator truth."""
from collections import deque
import csv
import math
from .metrics import Pose, pair_pose, pose_error


def stamp_seconds(stamp):
    return stamp.sec + stamp.nanosec * 1e-9


def quaternion_yaw(q):
    return math.atan2(2 * (q.w*q.z + q.x*q.y), 1 - 2 * (q.y*q.y + q.z*q.z))


def message_pose(msg):
    p = msg.pose.pose
    return Pose(stamp_seconds(msg.header.stamp), p.position.x, p.position.y, quaternion_yaw(p.orientation))


class PoseLog:
    fields = ['time_s', 'estimate_x', 'estimate_y', 'estimate_yaw',
              'truth_x', 'truth_y', 'truth_yaw', 'position_error_m', 'yaw_error_rad']

    def __init__(self, stream):
        self.writer = csv.writer(stream)
        self.writer.writerow(self.fields)
        self.truth = deque(maxlen=300)
        self.pending = deque(maxlen=100)
        self.errors = deque(maxlen=10000)
        self.dropped = 0

    def add_estimate(self, pose):
        self.pending.append(pose)
        self.drain()

    def add_truth(self, pose):
        self.truth.append(pose)
        self.drain()

    def drain(self):
        while self.pending and self.truth and self.pending[0].t <= self.truth[-1].t:
            estimate = self.pending.popleft()
            truth = pair_pose(estimate, self.truth)
            if truth is None:
                self.dropped += 1
                continue
            xy, yaw = pose_error(estimate, truth)
            self.errors.append((xy, yaw))
            self.writer.writerow([estimate.t, estimate.x, estimate.y, estimate.yaw,
                                  truth.x, truth.y, truth.yaw, xy, yaw])


def main(args=None):
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import qos_profile_sensor_data
    from geometry_msgs.msg import PoseWithCovarianceStamped
    from nav_msgs.msg import Odometry
    rclpy.init(args=args)
    node = Node('pose_logger')
    path = node.declare_parameter('output', '/tmp/pose-errors.csv').value
    try:
        with open(path, 'w', newline='') as stream:
            log = PoseLog(stream)
            node.create_subscription(Odometry, '/ground_truth',
                                     lambda m: log.add_truth(message_pose(m)), qos_profile_sensor_data)
            node.create_subscription(PoseWithCovarianceStamped, '/amcl_pose',
                                     lambda m: log.add_estimate(message_pose(m)), 20)
            node.create_timer(1.0, stream.flush)
            try:
                rclpy.spin(node)
            except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
                pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
