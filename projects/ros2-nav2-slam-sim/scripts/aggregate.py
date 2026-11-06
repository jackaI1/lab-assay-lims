#!/usr/bin/env python3
"""Aggregate only reports measured by run_experiment.py; never synthesize results."""
import argparse
import json
from pathlib import Path
import statistics


def aggregate(reports):
    if not reports:
        raise ValueError('No measured reports found')
    reports = sorted(reports, key=lambda r: r['seed'])
    return {'seeds': [r['seed'] for r in reports], 'runs': len(reports),
            'completed_waypoints': sum(len(r['patrol']['waypoints']) for r in reports),
            'runs_with_recovery': sum(r['patrol']['removed'] and r['patrol']['recoveries'] > 0 for r in reports),
            'localization_rmse_m': {'mean': statistics.mean(r['localization']['position_rmse_m'] for r in reports),
                                    'worst': max(r['localization']['position_rmse_m'] for r in reports)},
            'map_boundary_recall_12cm': {'mean': statistics.mean(r['map']['boundary_recall_12cm'] for r in reports),
                                        'worst': min(r['map']['boundary_recall_12cm'] for r in reports)},
            'map_occupied_precision_12cm': {'mean': statistics.mean(r['map']['occupied_precision_12cm'] for r in reports),
                                           'worst': min(r['map']['occupied_precision_12cm'] for r in reports)}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directory', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    opts = parser.parse_args()
    result = aggregate([json.loads(p.read_text()) for p in sorted(opts.directory.glob('**/report.json'))])
    opts.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))
