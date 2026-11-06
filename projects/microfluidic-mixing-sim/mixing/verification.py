"""Analytic checks independent of the mixer geometry."""
import numpy as np
import ufl
from mpi4py import MPI
from petsc4py import PETSc
from basix.ufl import element, mixed_element
from dolfinx import fem, mesh
from dolfinx.fem.petsc import LinearProblem
from .solver import direct, integral, stokes_form


def poiseuille(n=8):
    domain = mesh.create_unit_square(MPI.COMM_WORLD,n,n)
    W = fem.functionspace(domain,mixed_element([
        element("Lagrange",domain.basix_cell(),2,shape=(2,)),
        element("Lagrange",domain.basix_cell(),1)]))
    V,_ = W.sub(0).collapse()
    exact = fem.Function(V)
    exact.interpolate(lambda x: np.stack([x[1]*(1-x[1]),np.zeros(x.shape[1])]))
    boundary = mesh.locate_entities_boundary(domain,1,lambda x: np.full(x.shape[1],True))
    bc = fem.dirichletbc(exact,fem.locate_dofs_topological((W.sub(0),V),1,boundary),W.sub(0))
    # Fix a single pressure dof, removing the constant-pressure nullspace.
    Q,_ = W.sub(1).collapse()
    zero = fem.Function(Q)
    vertex = mesh.locate_entities_boundary(domain,0,
                 lambda x: np.isclose(x[0],1)&np.isclose(x[1],0))
    pb = fem.dirichletbc(zero,fem.locate_dofs_topological((W.sub(1),Q),0,vertex),W.sub(1))
    u,p = ufl.TrialFunctions(W)
    v,q = ufl.TestFunctions(W)
    result = direct(stokes_form(u,p,v,q),ufl.inner(fem.Constant(domain,PETSc.ScalarType((0,0))),v)*ufl.dx,[bc,pb])
    uh,ph = result.sub(0).collapse(),result.sub(1).collapse()
    x = ufl.SpatialCoordinate(domain)
    ue = ufl.as_vector((x[1]*(1-x[1]),0))
    return {"n":n,"velocity_L2":np.sqrt(integral(ufl.inner(uh-ue,uh-ue))),
            "pressure_L2":np.sqrt(integral((ph-2*(1-x[0]))**2))}


def momentum(n=16):
    """P1 reduced Poiseuille momentum, with a nonzero spatial truncation error."""
    domain = mesh.create_unit_interval(MPI.COMM_WORLD,n)
    V = fem.functionspace(domain,("Lagrange",1))
    u,v = ufl.TrialFunction(V),ufl.TestFunction(V)
    ends = mesh.locate_entities_boundary(domain,0,lambda x: np.isclose(x[0],0)|np.isclose(x[0],1))
    bc = fem.dirichletbc(PETSc.ScalarType(0),fem.locate_dofs_topological(V,0,ends),V)
    uh = direct(ufl.inner(ufl.grad(u),ufl.grad(v))*ufl.dx,2*v*ufl.dx,[bc])
    x = ufl.SpatialCoordinate(domain)[0]
    return {"n":n,"L2":np.sqrt(integral((uh-x*(1-x))**2))}


def diffusion(n=16, end=0.05):
    """u_t=u_xx, zero endpoints, u(x,0)=sin(pi*x); backward Euler."""
    domain = mesh.create_unit_interval(MPI.COMM_WORLD,n)
    V = fem.functionspace(domain,("Lagrange",1))
    u,v = ufl.TrialFunction(V),ufl.TestFunction(V)
    previous = fem.Function(V)
    previous.interpolate(lambda x: np.sin(np.pi*x[0]))
    ends = mesh.locate_entities_boundary(domain,0,lambda x: np.isclose(x[0],0)|np.isclose(x[0],1))
    bc = fem.dirichletbc(PETSc.ScalarType(0),fem.locate_dofs_topological(V,0,ends),V)
    steps = int(np.ceil(end*n*n*4))
    dt = end/steps
    problem = LinearProblem(
        (u*v+dt*ufl.inner(ufl.grad(u),ufl.grad(v)))*ufl.dx,
        previous*v*ufl.dx,bcs=[bc],petsc_options={"ksp_type":"preonly","pc_type":"lu"})
    for _ in range(steps):
        result = problem.solve()
        previous.x.array[:] = result.x.array
    x = ufl.SpatialCoordinate(domain)[0]
    exact = ufl.sin(np.pi*x)*np.exp(-np.pi**2*end)
    return {"n":n,"dt":dt,"L2":np.sqrt(integral((previous-exact)**2))}
