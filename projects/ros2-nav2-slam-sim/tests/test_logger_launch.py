"""Launch the installed logger and exercise real DDS subscriptions and CSV output."""
import csv
from pathlib import Path
import shutil
import tempfile
import time
import unittest
import pytest

pytest.importorskip('launch_testing')
import launch
import launch_ros.actions
import launch_testing
import launch_testing.actions
import launch_testing.asserts
import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped
from nav_msgs.msg import Odometry

TEMP = Path(tempfile.mkdtemp(prefix='lab-patrol-launch-'))
OUTPUT = TEMP/'poses.csv'
ROUTE = TEMP/'route.yaml'
ROUTE.write_text('waypoints: [[1, 2, 0], [3, 4, 0]]\n')


@pytest.mark.launch_test
def generate_test_description():
    logger = launch_ros.actions.Node(package='lab_patrol', executable='pose_logger',
                                     parameters=[{'output': str(OUTPUT)}],
                                     remappings=[('/ground_truth', '/logger_test/truth'),
                                                 ('/amcl_pose', '/logger_test/estimate')])
    waypoint = launch_ros.actions.Node(package='lab_patrol', executable='patrol',
        arguments=['--mapping', '--waypoints', str(ROUTE)])
    return launch.LaunchDescription([logger, waypoint, launch_testing.actions.ReadyToTest()]), {
        'logger': logger, 'waypoint': waypoint}


class TestLoggerDDS(unittest.TestCase):
    def test_paired_pose_reaches_disk(self):
        rclpy.init()
        node = rclpy.create_node('logger_test_publisher')
        truth = node.create_publisher(Odometry, '/logger_test/truth', 10)
        estimates = node.create_publisher(PoseWithCovarianceStamped, '/logger_test/estimate', 10)
        try:
            end = time.monotonic()+15
            while truth.get_subscription_count() == 0 or estimates.get_subscription_count() == 0:
                assert time.monotonic() < end, 'Logger subscriptions never appeared'
                rclpy.spin_once(node, timeout_sec=.1)
            # Discovery is asynchronous. Use an isolated topic stream and fresh,
            # ordered brackets until the installed logger flushes a checked row.
            end = time.monotonic()+15
            sequence, next_send = 0, 0.0
            while time.monotonic() < end:
                if time.monotonic() >= next_send:
                    a, b = Odometry(), Odometry()
                    a.header.stamp.sec = b.header.stamp.sec = 10+sequence
                    b.header.stamp.nanosec = 100000000
                    a.pose.pose.orientation.w = b.pose.pose.orientation.w = 1.
                    estimate = PoseWithCovarianceStamped()
                    estimate.header.stamp.sec = 10+sequence
                    estimate.header.stamp.nanosec = 50000000
                    estimate.pose.pose.position.x = .12
                    estimate.pose.pose.orientation.w = 1.
                    truth.publish(a)
                    truth.publish(b)
                    estimates.publish(estimate)
                    sequence += 1
                    next_send = time.monotonic()+.25
                if OUTPUT.exists():
                    rows = list(csv.DictReader(OUTPUT.open()))
                    if rows:
                        assert float(rows[0]['position_error_m']) == pytest.approx(.12)
                        return
                rclpy.spin_once(node, timeout_sec=.1)
            self.fail('Logger never flushed a paired sample')
        finally:
            node.destroy_node()
            rclpy.shutdown()


class TestWaypointDDS(unittest.TestCase):
    def test_installed_patrol_sends_ordered_actions(self, proc_info, waypoint):
        from rclpy.action import ActionServer
        from lifecycle_msgs.srv import GetState
        from lifecycle_msgs.msg import State
        from nav2_msgs.action import NavigateToPose
        rclpy.init()
        node = rclpy.create_node('waypoint_test_server')
        received = []
        def active(request, response):
            response.current_state.id = State.PRIMARY_STATE_ACTIVE
            response.current_state.label = 'active'
            return response
        def execute(handle):
            p = handle.request.pose.pose.position
            received.append((p.x, p.y))
            feedback = NavigateToPose.Feedback()
            handle.publish_feedback(feedback)
            handle.succeed()
            return NavigateToPose.Result()
        lifecycle = node.create_service(GetState, '/bt_navigator/get_state', active)
        server = ActionServer(node, NavigateToPose, '/navigate_to_pose', execute)
        try:
            end = time.monotonic()+20
            while len(received) < 2 and time.monotonic() < end:
                rclpy.spin_once(node, timeout_sec=.1)
            assert received == [(1., 2.), (3., 4.)]
            # Deliver the final get-result response before waiting for the CLI to exit.
            until = time.monotonic()+2
            while time.monotonic() < until:
                rclpy.spin_once(node, timeout_sec=.1)
            proc_info.assertWaitForShutdown(process=waypoint, timeout=10)
        finally:
            server.destroy()
            node.destroy_service(lifecycle)
            node.destroy_node()
            rclpy.shutdown()


@launch_testing.post_shutdown_test()
class TestCleanExit(unittest.TestCase):
    def test_exit(self, proc_info):
        try:
            launch_testing.asserts.assertExitCodes(proc_info)
        finally:
            shutil.rmtree(TEMP)
