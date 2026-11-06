#!/usr/bin/env python3
"""Plot a measured occupancy map and timestamp-paired patrol trajectory."""
import argparse
import csv
from pathlib import Path
import sys
import yaml
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lab_patrol.metrics import read_pgm


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    opts = parser.parse_args()
    meta = yaml.safe_load((opts.run/'lab-map.yaml').read_text())
    width, height, pixels = read_pgm(opts.run/meta['image'])
    rows = list(csv.DictReader((opts.run/'pose-errors.csv').open()))
    ox, oy, _ = meta['origin']
    size = meta['resolution']
    fig, ax = plt.subplots(figsize=(7, 7), constrained_layout=True)
    ax.imshow(np.frombuffer(pixels, dtype=np.uint8).reshape(height, width), cmap='gray',
              vmin=0, vmax=254, extent=[ox, ox+width*size, oy, oy+height*size])
    for kind, color, label, style in [('truth', '#d47227', 'Actual position', '-'),
                                     ('estimate', '#245e9d', 'AMCL estimate', '--')]:
        ax.plot([float(r[kind+'_x']) for r in rows], [float(r[kind+'_y']) for r in rows],
                style, color=color, label=label, linewidth=1.8, alpha=.85)
    route = yaml.safe_load((ROOT/'config/waypoints.yaml').read_text())['waypoints']
    for index, (x, y, _) in enumerate(route, 1):
        ax.plot(x, y, 'o', color='#404040', markersize=4)
        ax.annotate(str(index), (x, y), xytext=(5, 5), textcoords='offset points', fontsize=9)
    ax.set(xlabel='Lab x (m)', ylabel='Lab y (m)', title='Saved laser map and measured patrol')
    ax.set_aspect('equal')
    ax.legend(loc='lower left', framealpha=.95)
    fig.savefig(opts.output, dpi=150)
    plt.close(fig)


if __name__ == '__main__':
    main()
