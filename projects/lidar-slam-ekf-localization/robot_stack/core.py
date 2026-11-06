"""Small, deterministic 2D robot simulation and estimators."""
import math
import numpy as np


def wrap(a):
    return (a + np.pi) % (2 * np.pi) - np.pi


def move(p, distance, turn):
    theta = p[2] + turn / 2
    return np.array([p[0] + distance * np.cos(theta), p[1] + distance * np.sin(theta), wrap(p[2] + turn)])


class EKF:
    def __init__(self, pose):
        self.pose = np.array(pose, dtype=float)
        self.cov = np.diag([.01, .01, .01])

    def step(self, distance, wheel_turn, imu_heading):
        t = self.pose[2] + wheel_turn / 2
        F = np.eye(3); F[0, 2] = -distance * np.sin(t); F[1, 2] = distance * np.cos(t)
        self.pose = move(self.pose, distance, wheel_turn)
        self.cov = F @ self.cov @ F.T + np.diag([.002**2, .002**2, .015**2])
        h = np.array([[0., 0., 1.]])
        k = self.cov @ h.T / (float((h @ self.cov @ h.T)[0, 0]) + .04**2)
        self.pose += k[:, 0] * wrap(imu_heading - self.pose[2]); self.pose[2] = wrap(self.pose[2])
        # Joseph form maintains positive semidefiniteness with rounding.
        a = np.eye(3) - k @ h
        self.cov = a @ self.cov @ a.T + k @ k.T * .04**2
        return self.pose.copy()


class Grid:
    def __init__(self, size=120, resolution=.1):
        self.size, self.resolution = size, resolution
        self.logodds = np.zeros((size, size))

    def index(self, xy):
        return np.floor(np.asarray(xy) / self.resolution + self.size / 2).astype(int)

    def update(self, pose, scan, max_range=4.):
        start = self.index(pose[:2])
        for angle, distance in scan:
            end_xy = pose[:2] + distance * np.array([np.cos(pose[2]+angle), np.sin(pose[2]+angle)])
            end = self.index(end_xy)
            n = max(abs(end-start)) + 1
            for i, cell in enumerate(np.linspace(start, end, n).astype(int)):
                x, y = cell
                if 0 <= x < self.size and 0 <= y < self.size:
                    self.logodds[y, x] = np.clip(self.logodds[y, x] + (.85 if i == n-1 and distance < max_range-.01 else -.4), -4, 4)

    def occupied(self):
        y, x = np.nonzero(self.logodds > .5)
        return (np.column_stack((x, y)) + .5 - self.size/2) * self.resolution


class ParticleFilter:
    def __init__(self, pose, count, rng):
        self.rng = rng
        self.particles = np.tile(pose, (count, 1)).astype(float) + rng.normal(0, [.15, .15, .08], (count, 3))
        self.weights = np.full(count, 1/count)

    def step(self, distance, turn, scan, occupied):
        n = len(self.particles)
        for i in range(n):
            self.particles[i] = move(self.particles[i], distance + self.rng.normal(0, .015), turn + self.rng.normal(0, .02))
        if len(occupied) == 0:
            return self.estimate()
        # Likelihood field: penalize distance from each measured endpoint to map.
        scores = np.empty(n)
        for i, p in enumerate(self.particles):
            angles = p[2] + scan[:, 0]
            endpoints = p[:2] + scan[:, 1, None] * np.column_stack((np.cos(angles), np.sin(angles)))
            d2 = ((endpoints[:, None, :] - occupied[None, :, :]) ** 2).sum(axis=2).min(axis=1)
            scores[i] = -np.minimum(d2, .25).sum() / (2 * .15**2)
        scores += np.log(np.maximum(self.weights, 1e-300))
        scores -= scores.max(); self.weights = np.exp(scores); self.weights /= self.weights.sum()
        estimate = self.estimate()
        if 1 / np.sum(self.weights**2) < n / 2:
            positions = (self.rng.random() + np.arange(n)) / n
            indexes = np.searchsorted(np.cumsum(self.weights), positions).clip(0, n-1)
            self.particles = self.particles[indexes].copy(); self.weights.fill(1/n)
        return estimate

    def estimate(self):
        xy = self.weights @ self.particles[:, :2]
        heading = np.arctan2(self.weights @ np.sin(self.particles[:, 2]), self.weights @ np.cos(self.particles[:, 2]))
        return np.r_[xy, heading]


# Walls and interior obstacles, as line segments in metres.
WALLS = np.array([[[-4,-4],[4,-4]], [[4,-4],[4,4]], [[4,4],[-4,4]], [[-4,4],[-4,-4]], [[-1,-2],[-1,1]], [[1,0],[2,0]], [[2,0],[2,2]]], dtype=float)


def lidar(pose, angles, rng, noise=.01, max_range=4.):
    readings = []
    for angle in angles:
        direction = np.array([np.cos(pose[2]+angle), np.sin(pose[2]+angle)])
        best = max_range
        for a, b in WALLS:
            v = b-a
            matrix = np.column_stack((direction, -v))
            if abs(np.linalg.det(matrix)) < 1e-9: continue
            t, u = np.linalg.solve(matrix, a-pose[:2])
            if t > 0 and 0 <= u <= 1: best = min(best, t)
        readings.append([angle, np.clip(best + rng.normal(0, noise), .01, max_range)])
    return np.array(readings)


def scan_points(scan):
    return scan[:, 1, None] * np.column_stack((np.cos(scan[:, 0]), np.sin(scan[:, 0])))


def voxelize(points, resolution):
    """Return occupied voxel indices and counts, including negative coordinates."""
    return np.unique(np.floor(np.asarray(points) / resolution).astype(int), axis=0, return_counts=True)
