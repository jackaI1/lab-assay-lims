from types import SimpleNamespace
import pytest
from lab_patrol.waypoints import load_waypoints, patrol


def test_real_lab_route():
    points = load_waypoints('config/waypoints.yaml')
    assert len(points) == 6
    assert points[-1] == (0, 0, 0)


@pytest.mark.parametrize('text', ['waypoints: []', 'waypoints: [[0, 1]]', 'waypoints: [[0, 1, .nan]]',
                                       'waypoints: [[true, 1, 2]]', 'waypoints: [[0, a, 2]]', 'null'])
def test_bad_route_rejected(tmp_path, text):
    file = tmp_path/'route.yaml'
    file.write_text(text)
    with pytest.raises(ValueError):
        load_waypoints(file)


class FakeNavigator:
    def __init__(self, result=1, accepted=True):
        self.result, self.accepted = result, accepted
        self.goals, self.polls, self.cancelled = [], 0, False
    def goToPose(self, pose):
        self.goals.append(pose)
        self.polls = 0
        return self.accepted
    def isTaskComplete(self):
        self.polls += 1
        return self.polls >= 3
    def getFeedback(self):
        return SimpleNamespace(number_of_recoveries=2)
    def getResult(self):
        return self.result
    def cancelTask(self):
        self.cancelled = True


def test_patrol_orders_goals_and_reports_recoveries():
    nav, feedback = FakeNavigator(), []
    result = patrol(nav, ['station-a', 'station-b'], on_feedback=feedback.append)
    assert nav.goals == ['station-a', 'station-b']
    assert [r['recoveries'] for r in result] == [2, 2]
    assert len(feedback) == 4


@pytest.mark.parametrize('result', [2, 3, 0])
def test_aborted_goal_stops_route(result):
    nav = FakeNavigator(result=result)
    with pytest.raises(RuntimeError, match='Waypoint 0 failed'):
        patrol(nav, ['a', 'b'])
    assert nav.goals == ['a']


def test_rejected_goal_stops_route():
    with pytest.raises(RuntimeError, match='rejected'):
        patrol(FakeNavigator(accepted=False), ['a'])


def test_timeout_cancels_goal():
    nav = FakeNavigator()
    with pytest.raises(TimeoutError):
        patrol(nav, ['a'], timeout_s=-1)
    assert nav.cancelled


def test_ros_commander_enum_success():
    from enum import Enum
    class TaskResult(Enum):
        SUCCEEDED = 1
    assert patrol(FakeNavigator(result=TaskResult.SUCCEEDED), ['a'])[0]['succeeded']


def test_previous_goal_feedback_cannot_inflate_recovery_count():
    class CachedNavigator(FakeNavigator):
        cached = SimpleNamespace(number_of_recoveries=4)
        def getFeedback(self):
            return self.cached
    assert patrol(CachedNavigator(), ['a'])[0]['recoveries'] == 0
