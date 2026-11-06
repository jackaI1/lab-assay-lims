import importlib.util
from pathlib import Path
import xml.etree.ElementTree as ET
import yaml


def generated(module):
    spec = importlib.util.spec_from_file_location(module, f'scripts/generate_{module}.py')
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def test_committed_geometry_is_reproducible():
    assert Path('worlds/lab.world').read_text() == generated('world').world()
    assert Path('models/lab_bot/model.sdf').read_text() == generated('robot').robot()


def test_truth_cannot_drive_navigation():
    robot = ET.parse('models/lab_bot/model.sdf')
    drive = robot.find(".//plugin[@name='drive']")
    assert drive.findtext('odometry_source') == '0'  # encoder, never simulator world pose
    assert drive.findtext('publish_odom_tf') == 'true'
    params = Path('config/nav2.yaml').read_text()+Path('config/slam.yaml').read_text()
    assert 'ground_truth' not in params


def test_route_has_clearance_from_lab_fixtures():
    boxes = yaml.safe_load(Path('config/layout.yaml').read_text())['boxes']
    route = yaml.safe_load(Path('config/waypoints.yaml').read_text())['waypoints']
    for x, y, _ in route:
        assert all(abs(x-bx) > w/2+.25 or abs(y-by) > d/2+.25 for bx, by, w, d, _ in boxes)


def test_controller_and_goal_checker_share_position_tolerance():
    params = yaml.safe_load(Path('config/nav2.yaml').read_text())['controller_server']['ros__parameters']
    assert params['FollowPath']['xy_goal_tolerance'] == params['general_goal_checker']['xy_goal_tolerance']
