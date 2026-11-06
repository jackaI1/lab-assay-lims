"""ROS-independent, timestamp-paired localization and measured-map metrics."""
from dataclasses import dataclass
import math
from pathlib import Path
import yaml


def wrap(angle):
    return math.atan2(math.sin(angle), math.cos(angle))


@dataclass(frozen=True)
class Pose:
    t: float
    x: float
    y: float
    yaw: float


def pair_pose(estimate, truth, max_skew=0.15):
    """Interpolate bracketing truth; reject stale data rather than lowering error."""
    for a, b in zip(truth, list(truth)[1:]):
        if a.t <= estimate.t <= b.t and b.t - a.t <= 2 * max_skew:
            f = (estimate.t - a.t) / (b.t - a.t) if b.t != a.t else 0
            return Pose(estimate.t, a.x + f * (b.x - a.x), a.y + f * (b.y - a.y),
                        wrap(a.yaw + f * wrap(b.yaw - a.yaw)))
    return None


def pose_error(estimate, truth):
    return math.hypot(estimate.x - truth.x, estimate.y - truth.y), abs(wrap(estimate.yaw - truth.yaw))


def summarize(errors):
    if not errors:
        raise ValueError('No timestamp-paired localization samples')
    xy, yaw = zip(*errors)
    return {'samples': len(xy), 'position_rmse_m': math.sqrt(sum(e*e for e in xy)/len(xy)),
            'position_max_m': max(xy), 'yaw_rmse_rad': math.sqrt(sum(e*e for e in yaw)/len(yaw))}


def read_pgm(path):
    """Read nav2_map_server binary PGM, including comments and arbitrary pixels."""
    with Path(path).open('rb') as stream:
        tokens = []
        while len(tokens) < 4:
            line = stream.readline()
            if not line:
                raise ValueError('Truncated PGM header')
            tokens.extend(line.split(b'#')[0].split())
        magic, width, height, maximum = tokens
        if magic != b'P5' or maximum != b'255':
            raise ValueError('Expected 8-bit binary PGM')
        w, h = int(width), int(height)
        data = stream.read()
        if len(data) != w * h:
            raise ValueError('Invalid PGM pixel count')
        return w, h, data


def map_accuracy(map_yaml, boxes, tolerance=0.12):
    """Compare learned occupied-cell centres with analytic box surfaces.

    Precision measures spurious walls. Recall samples the true visible boundaries,
    including unknown space as missing. No alignment fitting or truth map input to SLAM.
    """
    meta = yaml.safe_load(Path(map_yaml).read_text())
    w, h, pixels = read_pgm(Path(map_yaml).parent / meta['image'])
    resolution = meta['resolution']
    ox, oy, yaw = meta['origin']
    if abs(yaw) > 1e-6 or meta.get('negate', 0):
        raise ValueError('Evaluation expects an axis-aligned, non-negated map')
    occupied, known, correct = [], 0, 0
    for row in range(h):
        for col in range(w):
            value = pixels[row*w+col]
            x, y = ox+(col+0.5)*resolution, oy+(h-row-0.5)*resolution
            if not (-4.25 <= x <= 4.25 and -4.25 <= y <= 4.25):
                continue
            inside = any(abs(x-bx) <= bw/2 and abs(y-by) <= bd/2 for bx, by, bw, bd, _ in boxes)
            if value < 65:
                occupied.append((x, y))
            if -4 <= x <= 4 and -4 <= y <= 4 and (value < 65 or value > 250):
                known += 1
                correct += (value < 65) == inside
    if not occupied:
        raise ValueError('No measured occupied cells')
    def surface_distance(x, y, box):
        bx, by, bw, bd, _ = box
        dx, dy = abs(x-bx)-bw/2, abs(y-by)-bd/2
        return math.hypot(max(dx, 0), max(dy, 0)) if max(dx, dy) >= 0 else min(-dx, -dy)
    precision = sum(min(surface_distance(x,y,b) for b in boxes) <= tolerance for x,y in occupied)/len(occupied)
    # Sample boundaries on the lab-facing side of walls, all sides of benches.
    boundary = []
    for bx, by, bw, bd, _ in boxes:
        for i in range(max(2, math.ceil(bw/resolution))+1):
            x = bx-bw/2+i*bw/max(2, math.ceil(bw/resolution))
            for y in [by-bd/2, by+bd/2]:
                if -4.001 <= x <= 4.001 and -4.001 <= y <= 4.001:
                    boundary.append((x,y))
        for i in range(max(2, math.ceil(bd/resolution))+1):
            y = by-bd/2+i*bd/max(2, math.ceil(bd/resolution))
            for x in [bx-bw/2, bx+bw/2]:
                if -4.001 <= x <= 4.001 and -4.001 <= y <= 4.001:
                    boundary.append((x,y))
    recall = sum(any(math.hypot(x-a,y-b) <= tolerance for a,b in occupied) for x,y in boundary)/len(boundary)
    return {'occupied_precision_12cm': precision, 'boundary_recall_12cm': recall,
            'known_cell_accuracy': correct/known if known else 0,
            'known_fraction': known/round(64/resolution**2), 'occupied_cells': len(occupied)}
