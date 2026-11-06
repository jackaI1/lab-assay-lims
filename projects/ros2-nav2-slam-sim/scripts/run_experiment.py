#!/usr/bin/env python3
"""Run real Gazebo -> SLAM -> saved map -> AMCL -> blocked patrol, with evidence."""
import argparse
from contextlib import contextmanager
import csv
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lab_patrol.metrics import map_accuracy, summarize
from lab_patrol.waypoints import load_waypoints, patrol, ros_pose
import yaml


@contextmanager
def process(command, log_path):
    """Own exactly this process group and retain a cleanup audit, even on failure."""
    with open(log_path, 'w') as log:
        child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        audit = {'pid': child.pid, 'pgid': child.pid, 'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                 'command': command, 'ports': 'ROS DDS dynamic UDP; Gazebo master 11345 in isolated container',
                 'cleanup': f'kill -INT -- -{child.pid}'}
        try:
            Path(str(log_path)+'.owner.json').write_text(json.dumps(audit, indent=2)+'\n')
            yield child
        finally:
            previous = {sig: signal.signal(sig, signal.SIG_IGN)
                        for sig in (signal.SIGINT, signal.SIGTERM)}
            try:
                # ros2 launch propagates SIGINT and owns the simulator and lifecycle nodes.
                for sig, seconds in [(signal.SIGINT, 15), (signal.SIGTERM, 5), (signal.SIGKILL, 3)]:
                    try:
                        os.killpg(child.pid, sig)
                    except ProcessLookupError:
                        break
                    try:
                        child.wait(timeout=seconds)
                    except subprocess.TimeoutExpired:
                        continue
                    # Parent exit does not prove descendants stopped. Check the whole group.
                    try:
                        os.killpg(child.pid, 0)
                    except ProcessLookupError:
                        break
                child.wait(timeout=5)
                audit['exit_code'] = child.returncode
                # Defunct descendants cannot hold ports or memory; report only live processes.
                listing = subprocess.run(['ps', '-eo', 'pid,pgid,stat'], capture_output=True, text=True, check=True)
                live = [line for line in listing.stdout.splitlines()[1:]
                        if len(line.split()) >= 3 and line.split()[1] == str(child.pid) and not line.split()[2].startswith('Z')]
                audit['live_descendants_after_cleanup'] = live
                Path(str(log_path)+'.owner.json').write_text(json.dumps(audit, indent=2)+'\n')
                if live:
                    raise RuntimeError(f'Owned process group {child.pid} did not stop')
            finally:
                for sig, handler in previous.items():
                    signal.signal(sig, handler)


def wait_for(node, predicate, timeout=90, description='data'):
    import rclpy
    end = time.monotonic()+timeout
    while not predicate():
        if time.monotonic() > end:
            raise TimeoutError(f'Timed out waiting for {description}')
        rclpy.spin_once(node, timeout_sec=0.1)


def service(node, kind, name, request):
    import rclpy
    client = node.create_client(kind, name)
    try:
        if not client.wait_for_service(timeout_sec=30):
            raise TimeoutError(name)
        future = client.call_async(request)
        rclpy.spin_until_future_complete(node, future, timeout_sec=30)
        if not future.done() or future.result() is None:
            raise RuntimeError(f'Service failed: {name}')
        response = future.result()
        if hasattr(response, 'success') and not response.success:
            raise RuntimeError(f'{name}: {response.status_message}')
        return response
    finally:
        node.destroy_client(client)


def phase(output, seed, mapping, map_file, block):
    import rclpy
    from rclpy.parameter import Parameter
    from rclpy.qos import qos_profile_sensor_data, QoSProfile, DurabilityPolicy, ReliabilityPolicy
    from nav2_simple_commander.robot_navigator import BasicNavigator
    from nav_msgs.msg import OccupancyGrid, Odometry
    from sensor_msgs.msg import LaserScan
    from gazebo_msgs.srv import SpawnEntity, DeleteEntity
    name = 'mapping' if mapping else 'localization'
    command = ['ros2', 'launch', 'lab_patrol', 'lab.launch.py', f'mapping:={str(mapping).lower()}',
               f'map:={map_file}', f'seed:={seed}']
    with process(command, output/f'{name}.log'):
        rclpy.init()
        nav = BasicNavigator(node_name=f'{name}_experiment')
        nav.set_parameters([Parameter('use_sim_time', value=True)])
        scans, maps, truth = [], [], []
        def on_scan(msg):
            if not scans:
                sample = {'frame': msg.header.frame_id, 'time_s': msg.header.stamp.sec + msg.header.stamp.nanosec*1e-9,
                          'angle_min': msg.angle_min, 'angle_increment': msg.angle_increment,
                          'range_min': msg.range_min, 'range_max': msg.range_max,
                          'ranges_m': [float(v) if math.isfinite(v) else None for v in msg.ranges]}
                (output/f'{name}-scan.json').write_text(json.dumps(sample, indent=2)+'\n')
            if len(scans) < 10000:
                scans.append(msg.header.stamp)
        nav.create_subscription(LaserScan, '/scan', on_scan, qos_profile_sensor_data)
        nav.create_subscription(OccupancyGrid, '/map', lambda m: maps.append(m) if len(maps) < 2 else None,
                                QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                                           reliability=ReliabilityPolicy.RELIABLE))
        nav.create_subscription(Odometry, '/ground_truth', lambda m: truth.append(m) if len(truth) < 2 else None,
                                qos_profile_sensor_data)
        try:
            wait_for(nav, lambda: scans and maps and truth, description='laser, learned map and Gazebo truth')
            nav.setInitialPose(ros_pose(nav, 0, 0, 0))
            # A separate wall-clock watchdog outside this process bounds lifecycle startup.
            nav.waitUntilNav2Active(localizer='bt_navigator' if mapping else 'amcl')
            if block:
                req = SpawnEntity.Request()
                req.name = 'route_blocker'
                req.xml = '''<sdf version="1.6"><model name="route_blocker"><static>true</static>
<pose>0 2.5 0.5 0 0 0</pose><link name="body"><collision name="box"><geometry><box><size>1.2 1.2 1</size></box></geometry></collision>
<visual name="box"><geometry><box><size>1.2 1.2 1</size></box></geometry></visual></link></model></sdf>'''
                service(nav, SpawnEntity, '/spawn_entity', req)
                # Let the actual laser and costmaps observe the obstacle before the goal.
                until = time.monotonic()+4
                wait_for(nav, lambda: time.monotonic() >= until, timeout=8, description='obstacle observation')
            state = {'removed': False, 'recoveries': 0}
            def feedback(feedback):
                state['recoveries'] = max(state['recoveries'], feedback.number_of_recoveries)
                if block and not state['removed'] and feedback.number_of_recoveries > 0:
                    req = DeleteEntity.Request()
                    req.name = 'route_blocker'
                    service(nav, DeleteEntity, '/delete_entity', req)
                    state['removed'] = True
            route = load_waypoints(ROOT/'config/waypoints.yaml')
            poses = [ros_pose(nav, *p) for p in route]
            with process(['ros2', 'bag', 'record', '-o', str(output/f'{name}-bag'),
                          '--storage', 'sqlite3', '--use-sim-time', '/scan', '/odom', '/tf', '/tf_static', '/ground_truth', '/amcl_pose', '/clock'],
                         output/f'{name}-bag.log') as recorder:
                with process(['ros2', 'run', 'lab_patrol', 'pose_logger', '--ros-args', '-p',
                              f'output:={output / "pose-errors.csv"}', '-p', 'use_sim_time:=true'], output/f'{name}-logger.log') as logger:
                    def checked_feedback(msg):
                        for label, child in [('scan recorder', recorder), ('pose logger', logger)]:
                            if child.poll() is not None:
                                raise RuntimeError(f'{label} exited during the patrol; see {name} logs')
                        feedback(msg)
                    results = patrol(nav, poses, timeout_s=160, on_feedback=checked_feedback)
                if mapping:
                    subprocess.run(['ros2', 'run', 'nav2_map_server', 'map_saver_cli', '-f', str(map_file.with_suffix('')),
                                    '--ros-args', '-p', 'use_sim_time:=true', '-p', 'save_map_timeout:=15.0'],
                                   stdout=subprocess.DEVNULL, check=True, timeout=30)
            if block and not state['removed']:
                raise AssertionError('Patrol did not report a real Nav2 recovery')
            if len(scans) < 50:
                raise AssertionError(f'Only {len(scans)} laser scans observed')
            metadata = yaml.safe_load((output/f'{name}-bag/metadata.yaml').read_text())['rosbag2_bagfile_information']
            recorded = {entry['topic_metadata']['name']: entry['message_count']
                        for entry in metadata['topics_with_message_count']}
            if recorded.get('/scan', 0) < 50:
                raise AssertionError('Scan recording is missing or incomplete')
            return {'waypoints': results, 'scans_observed': len(scans), 'recorded_messages': recorded, **state}
        finally:
            nav.destroy_node()
            if rclpy.ok():
                rclpy.shutdown()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=7)
    parser.add_argument('--output', type=Path, default=ROOT/'artifacts/seed-7')
    opts = parser.parse_args()
    def terminate(signum, frame):
        raise SystemExit(128 + signum)
    signal.signal(signal.SIGTERM, terminate)
    output = opts.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output/'report.json').exists() or (output/'mapping-bag').exists():
        raise SystemExit('Use a fresh output directory to preserve previous evidence')
    map_file = output/'lab-map.yaml'
    mapping = phase(output, opts.seed, True, map_file, False)
    localization = phase(output, opts.seed, False, map_file, True)
    rows = list(csv.DictReader((output/'pose-errors.csv').open()))
    errors = [(float(r['position_error_m']), float(r['yaw_error_rad'])) for r in rows]
    boxes = yaml.safe_load((ROOT/'config/layout.yaml').read_text())['boxes']
    report = {'seed': opts.seed, 'mapping': mapping, 'patrol': localization,
              'map': map_accuracy(map_file, boxes), 'localization': summarize(errors)}
    (output/'report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2), flush=True)
    assert report['localization']['samples'] >= 30, 'Too few paired AMCL poses'
    assert report['localization']['position_rmse_m'] < 0.25, 'Localization RMSE exceeds 25 cm'
    assert report['localization']['yaw_rmse_rad'] < 0.2, 'Heading RMSE exceeds 0.2 rad'
    assert report['map']['occupied_precision_12cm'] > 0.85, 'Spurious map walls'
    assert report['map']['boundary_recall_12cm'] > 0.70, 'Missing lab boundaries'
    assert report['map']['known_fraction'] > 0.85, 'Incomplete map'


if __name__ == '__main__':
    main()
