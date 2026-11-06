"""Pose graph using relative SE(2) constraints and numerical Gauss-Newton."""
import numpy as np
from .core import wrap


def relative(a, b):
    c, s = np.cos(a[2]), np.sin(a[2]); d = b[:2]-a[:2]
    return np.array([c*d[0]+s*d[1], -s*d[0]+c*d[1], wrap(b[2]-a[2])])


def optimize(poses, edges, iterations=10):
    p = np.array(poses, dtype=float).copy(); n = len(p)
    for _ in range(iterations):
        rows, residuals = [], []
        for i, j, measurement, weight in edges:
            error = relative(p[i], p[j]) - measurement; error[2] = wrap(error[2])
            jac = np.zeros((3, 3*(n-1)))
            for node in (i,j):
                if node == 0: continue
                for k in range(3):
                    shifted = p.copy(); shifted[node,k] += 1e-6
                    delta = relative(shifted[i], shifted[j]) - relative(p[i], p[j]); delta[2] = wrap(delta[2])
                    jac[:, 3*(node-1)+k] = delta / 1e-6
            rows.append(jac * weight); residuals.append(error * weight)
        J = np.vstack(rows); r = np.concatenate(residuals)
        delta = np.linalg.lstsq(J, -r, rcond=None)[0]
        p[1:] += delta.reshape(-1,3); p[:,2] = wrap(p[:,2])
        if np.linalg.norm(delta) < 1e-7: break
    return p
