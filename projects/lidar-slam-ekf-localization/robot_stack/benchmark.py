"""Run repeatable simulation and write trajectories, maps and metrics to results/."""
import json
from pathlib import Path
import numpy as np
from .core import EKF, Grid, ParticleFilter, lidar, move, scan_points, wrap
from .graph import optimize, relative
from .icp import align


def metrics(truth, estimate):
    error = np.linalg.norm(estimate[:, :2] - truth[:, :2], axis=1)
    return {'ate_rmse_m': float(np.sqrt(np.mean(error**2))), 'final_drift_m': float(error[-1])}


def run(seed):
    rng = np.random.default_rng(seed); angles = np.linspace(-np.pi, np.pi, 48, endpoint=False)
    # The reference map is built beforehand from surveyed poses and then frozen.
    known = Grid()
    for x in np.linspace(-3, 3, 5):
        for y in np.linspace(-3, 3, 5):
            p = np.array([x,y,0.]); known.update(p, lidar(p, angles, rng))
    occupied = known.occupied()
    truth = [np.array([0., -2., 0.])]; odom = [truth[0].copy()]; ekf = EKF(truth[0]); filtered = [truth[0].copy()]
    pf = ParticleFilter(truth[0], 100, rng); localized = [pf.estimate()]
    unknown = Grid(); scans = [lidar(truth[0], angles, rng)]; unknown.update(filtered[0], scans[0])
    # One lap on a circle of radius 2 m, returning to the start.
    for _ in range(80):
        p = move(truth[-1], 4*np.pi/80, 2*np.pi/80); truth.append(p)
        d = 4*np.pi/80 + .003 + rng.normal(0,.01); turn = 2*np.pi/80 + .003 + rng.normal(0,.015)
        odom.append(move(odom[-1], d, turn)); filtered.append(ekf.step(d, turn, wrap(p[2]+rng.normal(0,.04))))
        scan = lidar(p, angles, rng); scans.append(scan); unknown.update(filtered[-1], scan)
        hits = scan[scan[:,1] < 3.95][::3]
        localized.append(pf.step(d, turn, hits, occupied))
    # Graph nodes every ten steps. Neighbour edges come from odometry; closing
    # constraint comes from matching the final lidar scan to the initial scan.
    ids = list(range(0,81,10)); nodes = np.array(odom)[ids]
    edges = [(i, i+1, relative(nodes[i], nodes[i+1]), 1.) for i in range(len(nodes)-1)]
    initial = relative(nodes[0], nodes[-1])
    loop = align(scan_points(scans[-1]), scan_points(scans[0]), initial=initial, max_distance=.7)
    edges.append((0,len(nodes)-1,loop,2.))
    optimized = optimize(nodes, edges)
    corrected = Grid()
    for pose, idx in zip(optimized, ids):
        corrected.update(pose, scans[idx])
    return {'truth': np.array(truth), 'odom': np.array(odom), 'ekf': np.array(filtered), 'particle': np.array(localized), 'graph': optimized, 'ids': ids, 'known': known.logodds, 'unknown': unknown.logodds, 'corrected': corrected.logodds, 'loop': loop}


def main():
    out = Path('results'); out.mkdir(exist_ok=True)
    report = {}
    for seed in (3, 7, 11):
        r = run(seed)
        report[str(seed)] = {name: metrics(r['truth'], r[name]) for name in ('odom','ekf','particle')}
        report[str(seed)]['graph'] = metrics(r['truth'][r['ids']], r['graph'])
        np.savez_compressed(out / f'run-{seed}.npz', **r)
    (out/'metrics.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))

if __name__ == '__main__': main()
