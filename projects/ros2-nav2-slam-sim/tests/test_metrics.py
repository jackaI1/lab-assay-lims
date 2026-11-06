import csv
import io
import math
import pytest
from lab_patrol.metrics import Pose, map_accuracy, pair_pose, pose_error, read_pgm, summarize
from lab_patrol.pose_logger import PoseLog


def test_interpolation_wraps_heading():
    paired = pair_pose(Pose(1.05, 0, 0, 0), [Pose(1, 0, 0, 3.1), Pose(1.1, 1, 2, -3.1)])
    assert paired.x == pytest.approx(.5)
    assert paired.y == pytest.approx(1)
    assert abs(paired.yaw) == pytest.approx(math.pi)


def test_stale_truth_is_rejected():
    assert pair_pose(Pose(2, 0, 0, 0), [Pose(1, 0, 0, 0), Pose(3, 0, 0, 0)]) is None


def test_error_and_rmse():
    assert pose_error(Pose(0, 3, 4, math.pi-.1), Pose(0, 0, 0, -math.pi+.1)) == pytest.approx((5, .2))
    result = summarize([(3, .1), (4, .2)])
    assert result['position_rmse_m'] == pytest.approx(math.sqrt(12.5))
    assert result['samples'] == 2
    with pytest.raises(ValueError):
        summarize([])


def test_logger_waits_for_future_truth_and_writes_actual_error():
    stream = io.StringIO()
    log = PoseLog(stream)
    log.add_truth(Pose(10, 0, 0, 0))
    log.add_estimate(Pose(10.05, .15, 0, .1))
    assert not log.errors
    log.add_truth(Pose(10.1, .1, 0, 0))
    row = list(csv.DictReader(io.StringIO(stream.getvalue())))[0]
    assert float(row['position_error_m']) == pytest.approx(.1)
    assert float(row['yaw_error_rad']) == pytest.approx(.1)


def test_logger_drops_unpaired_samples():
    log = PoseLog(io.StringIO())
    log.add_estimate(Pose(1, 0, 0, 0))
    log.add_truth(Pose(2, 0, 0, 0))
    assert log.dropped == 1
    assert not log.errors


def test_buffers_are_bounded():
    log = PoseLog(io.StringIO())
    for i in range(1000):
        log.add_truth(Pose(i, 0, 0, 0))
    assert len(log.truth) == 300


def test_pgm_preserves_whitespace_valued_first_pixel(tmp_path):
    file = tmp_path/'map.pgm'
    file.write_bytes(b'P5\n# map saver\n2 2\n255\n'+bytes([10, 32, 0, 255]))
    assert read_pgm(file) == (2, 2, bytes([10, 32, 0, 255]))


def test_truncated_pgm_rejected(tmp_path):
    file = tmp_path/'bad.pgm'
    file.write_bytes(b'P5\n2 2\n255\n\x00')
    with pytest.raises(ValueError, match='pixel count'):
        read_pgm(file)


def test_empty_map_cannot_pass_accuracy(tmp_path):
    (tmp_path/'map.yaml').write_text('image: map.pgm\nresolution: 0.05\norigin: [0, 0, 0]\n')
    (tmp_path/'map.pgm').write_bytes(b'P5\n2 2\n255\n'+bytes([205]*4))
    with pytest.raises(ValueError, match='occupied'):
        map_accuracy(tmp_path/'map.yaml', [[0, 0, 1, 1, 1]])
