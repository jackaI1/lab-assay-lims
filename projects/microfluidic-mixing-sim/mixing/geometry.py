"""Y-junction with a smooth, staggered chevron-grooved floor; lengths in H."""
import gmsh
import numpy as np
from mpi4py import MPI
from dolfinx.io import gmshio

LENGTH = 16.0


def floor(x, y, depth):
    z = np.zeros_like(x)
    for k in range(8):
        apex = (-1 if (k // 2) % 2 else 1) / 3
        center = 2.0 + 1.5 * k + 0.65 * np.abs(y - apex)
        d = np.abs(x - center) / 0.45
        z -= depth * np.where(d < 1, (1 + np.cos(np.pi * np.minimum(d, 1))) / 2, 0)
    return z


def channel(h=0.4, depth=0.25):
    if h <= 0 or not 0 <= depth <= 0.5:
        raise ValueError("h must be positive; groove depth must be between 0 and 0.5 H")
    if MPI.COMM_WORLD.size != 1:
        raise RuntimeError("This reproducible study uses one MPI rank")
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.option.setNumber("General.NumThreads", 1)
        gmsh.model.add("Y-channel")
        xy = [(-3,-2), (-3,-1), (-0.75,0), (-3,1), (-3,2),
              (0,1), (LENGTH,1), (LENGTH,-1), (0,-1)]
        points = [gmsh.model.occ.addPoint(x,y,0,h) for x,y in xy]
        lines = [gmsh.model.occ.addLine(points[i], points[(i+1)%len(points)])
                 for i in range(len(points))]
        surface = gmsh.model.occ.addPlaneSurface([gmsh.model.occ.addCurveLoop(lines)])
        entities = gmsh.model.occ.extrude([(2,surface)],0,0,1)
        gmsh.model.occ.synchronize()
        volumes = [tag for dim,tag in entities if dim == 3]
        gmsh.model.addPhysicalGroup(3, volumes, 1)
        groups = {1: [], 2: [], 3: [], 4: []}
        for _, tag in gmsh.model.getEntities(2):
            x,y,_ = gmsh.model.occ.getCenterOfMass(2,tag)
            marker = (1 if y < 0 else 2) if np.isclose(x,-3) else (3 if np.isclose(x,LENGTH) else 4)
            groups[marker].append(tag)
        for marker,tags in groups.items():
            gmsh.model.addPhysicalGroup(2,tags,marker)
        gmsh.option.setNumber("Mesh.MeshSizeMax",h)
        gmsh.option.setNumber("Mesh.MeshSizeMin",h)
        gmsh.model.mesh.generate(3)
        mesh, _, facets = gmshio.model_to_mesh(gmsh.model,MPI.COMM_WORLD,0,gdim=3)
    finally:
        gmsh.finalize()
    xyz = mesh.geometry.x
    cells = mesh.geometry.dofmap
    def determinants():
        vertices = xyz[cells]
        return np.linalg.det(vertices[:,1:]-vertices[:,:1])
    original = determinants()
    bottom = floor(xyz[:,0],xyz[:,1],depth)
    xyz[:,2] = bottom + (1-bottom)*xyz[:,2]
    if np.min(determinants()/original) <= 1e-8:
        raise ValueError("Floor mapping inverted a tetrahedron; refine the mesh or reduce groove depth")
    return mesh, facets
