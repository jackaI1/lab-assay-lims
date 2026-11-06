"""Manifest-driven batch processing, provenance, summary tables and headless plots."""

import csv
import hashlib
import json
import re
from importlib.metadata import version
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .breakthrough import analyze_breakthrough
from .cycling import analyze_cycles


def _table(path, rows):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields or ["run_id", "kind"])
        writer.writeheader()
        writer.writerows(rows)


def _plot(path, kind, data, metrics):
    panels = 2 if kind == "breakthrough" else 3
    fig, axes = plt.subplots(1, panels, figsize=(5 * panels, 4), layout="constrained")
    try:
        if kind == "breakthrough":
            axes[0].plot(data["time_s"], data["ratio"], alpha=0.4, label="Measured")
            axes[0].plot(data["time_s"], data["threshold_ratio"], label="Threshold filter")
            for threshold in [0.05, 0.5, 0.95]:
                axes[0].axhline(threshold, color="grey", linestyle=":", linewidth=0.7)
            axes[0].set(xlabel="Time (s)", ylabel="Outlet / inlet CO2")
            axes[0].legend()
            axes[1].plot(data["time_s"], data["flow_ml_min"])
            axes[1].set(xlabel="Time (s)", ylabel="Inlet flow (mL/min)")
        else:
            for cycle in np.unique(data["cycle"]):
                mask = data["cycle"] == cycle
                if kind == "cv":
                    axes[0].plot(
                        data["voltage_v"][mask],
                        data["current_a"][mask],
                        label=f"Cycle {int(cycle)}",
                    )
                else:
                    axes[0].plot(
                        data["time_s"][mask], data["voltage_v"][mask], label=f"Cycle {int(cycle)}"
                    )
            axes[0].set(
                xlabel="Voltage (V)" if kind == "cv" else "Time within cycle (s)",
                ylabel="Current (A)" if kind == "cv" else "Voltage (V)",
            )
            axes[0].legend()
            for field, label in [("charge_mah", "Charge"), ("discharge_mah", "Discharge")]:
                axes[1].plot(
                    [r["cycle"] for r in metrics],
                    [np.nan if r[field] is None else r[field] for r in metrics],
                    "o-",
                    label=label,
                )
            flagged = [r for r in metrics if r["flags"] and r["discharge_mah"] is not None]
            axes[1].scatter(
                [r["cycle"] for r in flagged],
                [r["discharge_mah"] for r in flagged],
                color="red",
                marker="x",
                s=80,
                label="Flagged; see summary",
            )
            axes[1].set(xlabel="Cycle", ylabel="Integrated charge (mAh)")
            axes[1].legend()
            for field, label in [
                ("retention_pct", "Retention"),
                ("coulombic_efficiency_pct", "Coulombic efficiency"),
            ]:
                axes[2].plot(
                    [r["cycle"] for r in metrics],
                    [np.nan if r[field] is None else r[field] for r in metrics],
                    "o-",
                    label=label,
                )
            axes[2].set(xlabel="Cycle", ylabel="Percent (%)")
            axes[2].legend()
        fig.suptitle(f"{path.stem} | {kind}")
        fig.savefig(path, dpi=140)
    finally:
        plt.close(fig)


def run_batch(manifest_path, output):
    manifest_path, output = Path(manifest_path).resolve(), Path(output)
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    runs = manifest.get("runs") if isinstance(manifest, dict) else None
    if not isinstance(runs, list) or not runs:
        raise ValueError("manifest needs a nonempty runs list")
    ids = set()
    for run in runs:
        if not isinstance(run, dict):
            raise ValueError("each run must be an object")
        if set(run) != {"id", "kind", "file", "options"}:
            raise ValueError("each run needs exactly id, kind, file, options")
        if not isinstance(run["id"], str) or not re.fullmatch(r"[A-Za-z0-9_-]+", run["id"]):
            raise ValueError("run IDs must contain only letters, digits, underscores and hyphens")
        if run["id"] in ids:
            raise ValueError("run IDs must be unique")
        ids.add(run["id"])
        if run["kind"] not in ("breakthrough", "cycling", "cv"):
            raise ValueError("unknown run kind")
        if not isinstance(run["file"], str) or not isinstance(run["options"], dict):
            raise ValueError("file must be a path string and options an object")
    output.mkdir(parents=True, exist_ok=False)
    summaries, errors, provenance = [], [], []
    for run in runs:
        path = manifest_path.parent / run["file"]
        entry = {**run, "sha256": None}
        try:
            entry["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            if run["kind"] == "breakthrough":
                result, data = analyze_breakthrough(path, **run["options"])
                rows = [result]
            else:
                rows, data = analyze_cycles(path, kind=run["kind"], **run["options"])
            _plot(output / f"{run['id']}.png", run["kind"], data, rows)
            summaries.extend({"run_id": run["id"], "kind": run["kind"], **row} for row in rows)
            entry["status"] = "ok"
        except (OSError, ValueError, TypeError, KeyError) as exc:
            errors.append({"run_id": run["id"], "error": str(exc)})
            entry["status"] = "error"
        provenance.append(entry)
    _table(output / "summary.csv", summaries)
    (output / "errors.json").write_text(json.dumps(errors, indent=2) + "\n")
    (output / "manifest.json").write_bytes(manifest_bytes)
    (output / "provenance.json").write_text(
        json.dumps(
            {
                "package_version": version("co2-capture-data-analysis"),
                "numpy_version": np.__version__,
                "matplotlib_version": matplotlib.__version__,
                "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                "runs": provenance,
            },
            indent=2,
        )
        + "\n"
    )
    return len(summaries), errors
