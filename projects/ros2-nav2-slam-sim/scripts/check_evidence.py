#!/usr/bin/env python3
"""Recalculate the committed map and pose results without ROS or Gazebo."""
import argparse
import csv
import json
import math
from pathlib import Path
import sys
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lab_patrol.metrics import map_accuracy, summarize


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    opts = parser.parse_args()
    reports = sorted(opts.directory.glob('seed-*/report.json'))
    if not reports:
        raise SystemExit('No measured reports found')
    boxes = yaml.safe_load((ROOT/'config/layout.yaml').read_text())['boxes']
    samples = stations = 0
    for path in reports:
        reported = json.loads(path.read_text())
        rows = list(csv.DictReader((path.parent/'pose-errors.csv').open()))
        measured = summarize([(float(r['position_error_m']), float(r['yaw_error_rad'])) for r in rows])
        # Recompute each error from the recorded poses as well as its summary.
        for row in rows:
            xy = math.hypot(float(row['estimate_x'])-float(row['truth_x']), float(row['estimate_y'])-float(row['truth_y']))
            yaw = abs(math.atan2(math.sin(float(row['estimate_yaw'])-float(row['truth_yaw'])),
                                 math.cos(float(row['estimate_yaw'])-float(row['truth_yaw']))))
            assert math.isclose(xy, float(row['position_error_m']), abs_tol=1e-10)
            assert math.isclose(yaw, float(row['yaw_error_rad']), abs_tol=1e-10)
        for section, calculated in [('localization', measured), ('map', map_accuracy(path.parent/'lab-map.yaml', boxes))]:
            for key, value in calculated.items():
                assert math.isclose(value, reported[section][key], abs_tol=1e-10), f'{path}: {section}.{key}'
        patrol = reported['patrol']
        assert len(patrol['waypoints']) == 6 and all(p['succeeded'] for p in patrol['waypoints'])
        assert patrol['removed'] and patrol['recoveries'] > 0
        assert patrol['recorded_messages']['/scan'] >= 50
        samples += measured['samples']
        stations += len(patrol['waypoints'])
    print(f'Recomputed {len(reports)} maps, {samples} paired poses and {stations} successful patrol stations.')


if __name__ == '__main__':
    main()
