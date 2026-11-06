"""Run parameter sweeps and convergence checks: python -m mixing.study."""
import argparse
import csv
import gc
import json
import platform
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import dolfinx
import gmsh
from dolfinx.io import XDMFFile
from dolfinx import fem
from .geometry import channel, LENGTH, floor
from .solver import stokes, transport, sections, integral, evaluate
from .verification import poiseuille, momentum, diffusion

H = 100e-6
D = 1e-9
RHO = 1000
MU = 1e-3


def physical(rate):
    if rate <= 0:
        raise ValueError("Total flow rate must be positive")
    velocity = rate*1e-9/60/(2*H*H)  # microlitres/min -> m^3/s
    return {"U_m_s":velocity,"Pe_H":velocity*H/D,"Re_H":RHO*velocity*H/MU,
            "diffusion_time_s":(2*H)**2/D,
            "diffusion_length_m":velocity*(2*H)**2/D}


def case(mesh, facets, velocity, ratio, rate):
    params = physical(rate)
    c = transport(mesh,facets,velocity,params["Pe_H"])
    profile = sections(velocity,c,ratio)
    volume = integral(fem.Constant(mesh,1.0))
    # Residence time is volume/Q, not a fitted mixing time.
    for row in profile:
        row["advective_time_s"] = row["x_H"]*H/params["U_m_s"]
    hits = [p["advective_time_s"] for p in profile if p["mixing_index"] >= .9]
    return c, {**params,"ratio":ratio,"rate_uL_min":rate,"profile":profile,
               "residence_time_s":volume*H**3/(rate*1e-9/60),
               "t90_s":hits[0] if hits else None,
               "c_min":float(c.x.array.min()),"c_max":float(c.x.array.max())}


def run(out, coarse=False, rates=None, ratios=None, h=None):
    out.mkdir(parents=True,exist_ok=True)
    rates = rates if rates is not None else ([1] if coarse else [.1,.5,2])
    ratios = ratios if ratios is not None else ([3] if coarse else [1,3,5])
    h = h if h is not None else (.55 if coarse else .30)
    if not 0 < h <= .7 or any(x <= 0 for x in [*rates,*ratios]):
        raise ValueError("Use 0 < mesh spacing <= 0.7 H and positive rates/ratios")
    (out/"provenance.json").write_text(json.dumps({
        "python":platform.python_version(),"dolfinx":dolfinx.__version__,
        "gmsh":gmsh.__version__,"H_m":H,"D_m2_s":D,"mu_Pa_s":MU,"rho_kg_m3":RHO,
        "rates_uL_min":rates,"water_organic_ratios":ratios,"sweep_mesh_H":h,
        "coarse":coarse,"mpi_ranks":1,"threads":1},indent=2)+"\n")
    verification = {"poiseuille":[poiseuille(n) for n in [4,8,16]],
                    "momentum":[momentum(n) for n in [8,16,32]],
                    "diffusion":[diffusion(n) for n in [8,16,32]]}
    (out/"verification.json").write_text(json.dumps(verification,indent=2)+"\n")
    rows = []
    for depth in [0,.25]:
        mesh,facets = channel(h,depth)
        for ratio in ratios:
            u,p,flux = stokes(mesh,facets,ratio)
            for rate in rates:
                c,row = case(mesh,facets,u,ratio,rate)
                row.update(depth_H=depth,h_H=h,cells=mesh.topology.index_map(3).size_global,flux=flux)
                rows.append(row)
                print(f"depth={depth}, ratio={ratio}, rate={rate}: M={row['profile'][-1]['mixing_index']:.4f}",flush=True)
                if ratio == 3 and rate == (.5 if not coarse else 1):
                    name = "smooth" if depth == 0 else "herringbone"
                    with XDMFFile(mesh.comm,str(out/f"{name}.xdmf"),"w") as file:
                        file.write_mesh(mesh)
                        c.name = "organic_fraction"
                        file.write_function(c)
                        display_u = fem.Function(fem.functionspace(mesh,("Lagrange",1,(3,))))
                        display_u.interpolate(u)
                        display_u.name = "velocity_over_U"
                        p.name = "pressure_over_muU_H"
                        file.write_function(display_u)
                        file.write_function(p)
                    plot_slice(out,name,u,c)
            del u,p,c
            gc.collect()
        del mesh,facets
        gc.collect()
    (out/"sweep.json").write_text(json.dumps(rows,indent=2)+"\n")
    with (out/"sweep.csv").open("w") as f:
        fields = ["depth_H","ratio","rate_uL_min","Pe_H","Re_H","residence_time_s","t90_s","outlet_mixing_index","c_min","c_max"]
        writer = csv.DictWriter(f,fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k:row["profile"][-1]["mixing_index"] if k == "outlet_mixing_index" else row[k] for k in fields})
    convergence = []
    sampling = []
    for depth in ([.25] if coarse else [0,.25]):
        for h in ([.7,.55] if coarse else [.6,.4,.3,.22]):
            mesh,facets = channel(h,depth)
            u,p,flux = stokes(mesh,facets,3)
            c,row = case(mesh,facets,u,3,.5)
            convergence.append({"depth_H":depth,"h_H":h,"cells":mesh.topology.index_map(3).size_global,
                                "outlet_mixing_index":row["profile"][-1]["mixing_index"],
                                "flux_imbalance":flux["relative_imbalance"]})
            if h == (.55 if coarse else .22):
                for n in [16,32,64]:
                    section = sections(u,c,3,xs=[15.5],n=n)[0]
                    sampling.append({"depth_H":depth,"samples_per_axis":n,**section})
            print(f"mesh depth={depth} h={h}: M={convergence[-1]['outlet_mixing_index']:.5f}",flush=True)
            del mesh,facets,u,p,c
            gc.collect()
    (out/"convergence.json").write_text(json.dumps(convergence,indent=2)+"\n")
    (out/"sampling.json").write_text(json.dumps(sampling,indent=2)+"\n")
    plot_results(out,rows,verification,convergence)
    return rows,convergence


def plot_slice(out,name,u,c):
    xs,ys = np.meshgrid(np.linspace(.05,15.95,250),np.linspace(-.99,.99,65))
    points = np.column_stack([xs.ravel(),ys.ravel(),np.full(xs.size,.35)])
    values = evaluate(c,points)[:,0].reshape(xs.shape)
    fig,ax = plt.subplots(figsize=(10,2.8),layout="constrained")
    plot = ax.pcolormesh(xs*100,ys*100,values,vmin=0,vmax=1,cmap="viridis",shading="auto")
    ax.set(xlabel="Distance after junction (µm)",ylabel="Width (µm)",title=f"{name}: solvent fraction at z = 35 µm, ratio 3")
    fig.colorbar(plot,ax=ax,label="Organic solvent fraction")
    fig.savefig(out/f"{name}-concentration.png",dpi=150)
    plt.close(fig)
    # Save the actual modeled floor, rather than an illustrative groove pattern.
    fig,ax = plt.subplots(figsize=(10,2.5),layout="constrained")
    ax.pcolormesh(xs*100,ys*100,floor(xs,ys,.25 if name == "herringbone" else 0)*100,shading="auto")
    ax.set(xlabel="Distance (µm)",ylabel="Width (µm)",title=f"{name}: modeled floor elevation (µm)")
    fig.savefig(out/f"{name}-floor.png",dpi=150)
    plt.close(fig)
    fig,axes = plt.subplots(1,2,figsize=(9,3.5),layout="constrained")
    for ax,x in zip(axes,[4.8,10.8]):
        yy,zz = np.meshgrid(np.linspace(-.95,.95,17),np.linspace(-.22,.97,14))
        points = np.column_stack([np.full(yy.size,x),yy.ravel(),zz.ravel()])
        uv = evaluate(u,points)
        cv = evaluate(c,points)[:,0]
        ax.scatter(yy.ravel()*100,zz.ravel()*100,c=cv,cmap="viridis",vmin=0,vmax=1,s=20)
        ax.quiver(yy.ravel()*100,zz.ravel()*100,uv[:,1],uv[:,2])
        ax.set(xlabel="y (µm)",ylabel="z (µm)",title=f"x = {x*100:g} µm")
    fig.suptitle(f"{name}: solved transverse velocity (arrows), solvent (colour)")
    fig.savefig(out/f"{name}-crossflow.png",dpi=150)
    plt.close(fig)


def plot_results(out,rows,verification,convergence):
    fig,axes = plt.subplots(1,2,figsize=(11,4),layout="constrained")
    for row in rows:
        if row["ratio"] == 3:
            axes[0].plot([r["x_H"]*100 for r in row["profile"]],[r["mixing_index"] for r in row["profile"]],
                         label=f"{'Grooved' if row['depth_H'] else 'Smooth'}, {row['rate_uL_min']} µL/min")
    axes[0].set(xlabel="Distance after junction (µm)",ylabel="Mixing index",ylim=(0,1))
    axes[0].legend(fontsize=8)
    for kind in ["momentum","diffusion"]:
        axes[1].loglog([1/r["n"] for r in verification[kind]],[r["L2"] for r in verification[kind]],"o-",label=kind)
    axes[1].set(xlabel="Analytic-case mesh spacing",ylabel="L2 error")
    axes[1].legend()
    fig.savefig(out/"mixing-and-verification.png",dpi=150)
    plt.close(fig)
    fig,axes = plt.subplots(1,2,figsize=(10,4),layout="constrained")
    for depth in sorted(set(r["depth_H"] for r in convergence)):
        subset = [r for r in convergence if r["depth_H"] == depth]
        axes[0].plot([r["cells"] for r in subset],[r["outlet_mixing_index"] for r in subset],"o-",label=f"depth {depth} H")
    axes[0].set(xlabel="Tetrahedra",ylabel="Outlet mixing index",title="Mesh sensitivity, ratio 3, 0.5 µL/min")
    axes[0].legend()
    for depth in sorted(set(r["depth_H"] for r in rows)):
        selected = [r for r in rows if r["depth_H"] == depth and r["ratio"] == 3]
        axes[1].plot([r["Pe_H"] for r in selected],[r["residence_time_s"] for r in selected],"o-",label=f"Residence, depth {depth} H")
        reached = [r for r in selected if r["t90_s"] is not None]
        axes[1].scatter([r["Pe_H"] for r in reached],[r["t90_s"] for r in reached],marker="x",s=60,label=f"t90 reached, depth {depth} H")
    axes[1].axhline(40,color="black",linestyle="--",label="W²/D diffusion scale")
    axes[1].set(xlabel="Peclet number UH/D",ylabel="Time (s)",yscale="log")
    axes[1].legend(fontsize=8)
    fig.savefig(out/"mesh-and-timescale.png",dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=Path("results"))
    parser.add_argument("--coarse",action="store_true",help="Small CI smoke study; not design evidence")
    parser.add_argument("--rates",type=float,nargs="+",help="Total flow rates in µL/min")
    parser.add_argument("--ratios",type=float,nargs="+",help="Water/organic flow-rate ratios")
    parser.add_argument("--mesh",type=float,help="Maximum sweep mesh spacing in channel heights")
    args = parser.parse_args()
    run(args.output,args.coarse,args.rates,args.ratios,args.mesh)
