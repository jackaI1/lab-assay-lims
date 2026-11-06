import numpy as np
import pytest
from robot_stack.core import EKF, Grid, ParticleFilter, move, voxelize
from robot_stack.graph import optimize, relative
from robot_stack.icp import align


def test_ekf_fuses_heading_and_covariance():
    f = EKF([0,0,0]); p = f.step(1, .3, 0)
    assert 0 < p[2] < .3
    assert np.linalg.eigvalsh(f.cov).min() > 0


def test_particle_filter_concentrates_near_matching_map():
    rng = np.random.default_rng(42); f = ParticleFilter([0,0,0], 300, rng)
    occupied = np.array([[1.,0.],[0.,1.],[-1.,0.]])
    scan = np.array([[0.,1.],[np.pi/2,1.],[np.pi,1.]])
    p = f.step(0,0,scan,occupied)
    assert np.linalg.norm(p[:2]) < .1 and abs(p[2]) < .1


def test_grid_and_voxels():
    g = Grid(size=100, resolution=.1); g.update(np.zeros(3), np.array([[0., 1.]]))
    assert g.logodds[50,60] > 0 and g.logodds[50,55] < 0
    indices, counts = voxelize(np.array([[-.01,0,0],[.01,0,0],[.02,0,0]]), .1)
    assert len(indices) == 2 and sorted(counts) == [1,2]


def test_cpp_icp_recovers_transform():
    rng = np.random.default_rng(2); points = rng.uniform(-1,1,(100,2))
    a=.07; rot=np.array([[np.cos(a),-np.sin(a)],[np.sin(a),np.cos(a)]])
    target=points @ rot.T + [.08,-.04]
    assert np.allclose(align(points,target,max_distance=.5), [.08,-.04,a], atol=.01)


def test_loop_closure_reduces_drift():
    p = np.array([[0.,0.,0.],[1.,0.,0.],[2.2,0.,0.]])
    edges=[(0,1,relative(p[0],p[1]),1.), (1,2,relative(p[1],p[2]),1.), (0,2,np.array([2.,0.,0.]),3.)]
    result=optimize(p,edges)
    assert abs(result[-1,0]-2) < .02


def test_particle_weights_persist_between_updates_without_resampling():
    class ZeroNoise:
        def normal(self, *args, **kwargs):
            return 0.
    f = ParticleFilter([0, 0, 0], 2, np.random.default_rng(1))
    f.rng = ZeroNoise()
    f.particles[:] = [0, 0, 0]
    f.weights[:] = [.8, .2]
    scan = np.array([[0., 1.]])
    occupied = np.array([[1., 0.]])
    f.step(0, 0, scan, occupied)
    f.step(0, 0, scan, occupied)
    assert np.allclose(f.weights, [.8, .2])
