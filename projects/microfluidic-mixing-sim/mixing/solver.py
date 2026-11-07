"""Taylor-Hood Stokes and P1 SUPG convection-diffusion, no fitted mixing law."""
import numpy as np
import ufl
from basix.ufl import element, mixed_element
from dolfinx import fem, geometry
from dolfinx.fem.petsc import LinearProblem
from petsc4py import PETSc


def direct(a, L, bcs):
    problem = LinearProblem(a,L,bcs=bcs,petsc_options={
        "ksp_type":"preonly", "pc_type":"lu", "pc_factor_mat_solver_type":"mumps"})
    solution = problem.solve()
    if problem.solver.getConvergedReason() <= 0:
        factor = problem.solver.getPC().getFactorMatrix()
        raise RuntimeError(f"PETSc linear solve failed: reason={problem.solver.getConvergedReason()}, MUMPS={factor.getMumpsInfog(1)}, detail={factor.getMumpsInfog(2)}")
    solution.x.scatter_forward()
    return solution


def integral(expr, measure=ufl.dx):
    return float(fem.assemble_scalar(fem.form(expr*measure)))


def stokes_form(u,p,v,q):
    return (2*ufl.inner(ufl.sym(ufl.grad(u)),ufl.sym(ufl.grad(v)))
            -p*ufl.div(v)+q*ufl.div(u))*ufl.dx


def stokes(mesh, facets, ratio=3.0):
    if ratio <= 0:
        raise ValueError("water/organic flow-rate ratio must be positive")
    P2 = element("Lagrange",mesh.basix_cell(),2,shape=(3,))
    P1 = element("Lagrange",mesh.basix_cell(),1)
    W = fem.functionspace(mesh,mixed_element([P2,P1]))
    V,_ = W.sub(0).collapse()
    u,p = ufl.TrialFunctions(W)
    v,q = ufl.TestFunctions(W)
    bcs = []
    ds = ufl.Measure("ds",domain=mesh,subdomain_data=facets)
    for marker, fraction in [(4,0),(1,1/(1+ratio)),(2,ratio/(1+ratio))]:
        value = fem.Function(V)
        if marker != 4:
            low = -2 if marker == 1 else 1
            def profile(x, low=low, fraction=fraction):
                a = np.zeros((3,x.shape[1]))
                a[0] = 72*fraction*(x[1]-low)*(low+1-x[1])*x[2]*(1-x[2])
                return a
            value.interpolate(profile)
            # Normalize the interpolated polynomial, so Q is exact on every mesh.
            value.x.array[:] *= 2*fraction/integral(value[0],ds(marker))
        dofs = fem.locate_dofs_topological((W.sub(0),V),2,facets.find(marker))
        bcs.append(fem.dirichletbc(value,dofs,W.sub(0)))
    a = stokes_form(u,p,v,q)
    L = ufl.inner(fem.Constant(mesh,PETSc.ScalarType((0,0,0))),v)*ufl.dx
    solution = direct(a,L,bcs)
    velocity = solution.sub(0).collapse()
    pressure = solution.sub(1).collapse()
    n = ufl.FacetNormal(mesh)
    flux = {str(i):integral(ufl.dot(velocity,n),ds(i)) for i in (1,2,3)}
    flux["relative_imbalance"] = abs(sum(flux.values()))/abs(flux["3"])
    return velocity,pressure,flux


def transport(mesh, facets, velocity, peclet, inlet_values=(1,0)):
    if peclet <= 0:
        raise ValueError("Peclet number must be positive")
    V = fem.functionspace(mesh,("Lagrange",1))
    c,v = ufl.TrialFunction(V),ufl.TestFunction(V)
    bcs = [fem.dirichletbc(PETSc.ScalarType(val),
            fem.locate_dofs_topological(V,2,facets.find(marker)),V)
            for marker,val in zip((1,2),inlet_values)]
    D = 1/peclet
    speed = ufl.sqrt(ufl.dot(velocity,velocity)+1e-16)
    h = ufl.CellDiameter(mesh)
    # Smooth SUPG time scale includes advection and diffusion. The full strong
    # residual retains the (zero for affine P1 cells) diffusion contribution.
    tau = 1/ufl.sqrt((2*speed/h)**2+(4*D/h**2)**2)
    stream = ufl.dot(velocity,ufl.grad(c))
    residual = stream-D*ufl.div(ufl.grad(c))
    a = (D*ufl.inner(ufl.grad(c),ufl.grad(v))+stream*v
         +tau*ufl.dot(velocity,ufl.grad(v))*residual)*ufl.dx
    L = fem.Constant(mesh,PETSc.ScalarType(0))*v*ufl.dx
    return direct(a,L,bcs)


def evaluate(function, points):
    points = np.asarray(points,dtype=np.float64)
    mesh = function.function_space.mesh
    tree = geometry.bb_tree(mesh,mesh.topology.dim)
    candidates = geometry.compute_collisions_points(tree,points)
    collisions = geometry.compute_colliding_cells(mesh,candidates,points)
    cells = np.array([collisions.links(i)[0] if len(collisions.links(i)) else -1
                      for i in range(len(points))],dtype=np.int32)
    values = np.full((len(points),int(np.prod(function.ufl_shape))),np.nan)
    valid = cells >= 0
    values[valid] = function.eval(points[valid],cells[valid]).reshape(sum(valid),-1)
    return values


def sections(velocity, concentration, ratio, xs=None, n=32):
    """Forward-flux-weighted variance over the actual meshed cross section.

    Uniform area quadrature includes grooves; points outside the mesh are
    discarded. Reverse flow is separately reported, never silently clipped.
    """
    if xs is None:
        xs = np.linspace(0.5,15.5,16)
    y = -1+(np.arange(n)+0.5)*2/n
    bottom = velocity.function_space.mesh.geometry.x[:,2].min()
    z = bottom+(1-bottom)*(np.arange(n)+0.5)/n
    yy,zz = np.meshgrid(y,z,indexing="ij")
    rows = []
    for x in xs:
        points = np.column_stack([np.full(n*n,x),yy.ravel(),zz.ravel()])
        c = evaluate(concentration,points)[:,0]
        ux = evaluate(velocity,points)[:,0]
        valid = np.isfinite(c)&np.isfinite(ux)
        if valid.sum() < n*n/2:
            raise RuntimeError("Too few interior section samples")
        c,ux = c[valid],ux[valid]
        weights = np.maximum(ux,0)
        mean = np.average(c,weights=weights)
        variance = np.average((c-mean)**2,weights=weights)
        cin = 1/(1+ratio)
        rows.append({"x_H":float(x),"mean":float(mean),
                     "reverse_flux_fraction":float(-np.minimum(ux,0).sum()/weights.sum()),
                     "mixing_index":float(1-np.sqrt(variance/(cin*(1-cin))))})
    return rows
