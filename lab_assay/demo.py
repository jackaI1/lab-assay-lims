"""Known-ground-truth synthetic endpoint plates, never represented as measurements."""

import csv
import hashlib
import io
from datetime import date, timedelta

import numpy as np


def synthetic_plate(seed=2026, bad=False):
    rng = np.random.default_rng(seed)
    mapping = []
    signals = {}

    def add(well, role, signal, **kwargs):
        mapping.append(dict(well=well, role=role, **kwargs))
        signals[well] = round(float(signal), 7)

    def response(x):
        return 0.07 + 2.7 / (1 + (x / 7) ** 1.3)

    # A decreasing competitive-assay curve with triplicate standards.
    for row, x in zip("ABCDEFGH", [0, 0.2, 0.5, 1, 2, 5, 20, 100], strict=True):
        for col in [1, 2, 3]:
            add(f"{row}{col}", "standard", response(x) + rng.normal(0, 0.0004), concentration=x)
    for col in [4, 5, 6]:
        add(f"A{col}", "blank", 0.07 + rng.normal(0, 0.0001))
        add(f"B{col}", "positive", 2.65 + rng.normal(0, 0.25 if bad else 0.005))
        add(f"C{col}", "negative", 0.1 + rng.normal(0, 0.25 if bad else 0.001))
    truth = {"DEMO-S1": 7.0, "DEMO-S2": 12.0}
    for row, sample, original, factor in [("D", "DEMO-S1", 7, 2), ("E", "DEMO-S2", 12, 3)]:
        for col in [4, 5, 6]:
            add(
                f"{row}{col}",
                "sample",
                response(original / factor) + rng.normal(0, 0.0004),
                sample_id=sample,
                dilution_factor=factor,
            )
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["well", "signal"])
    writer.writerows(signals.items())
    return mapping, out.getvalue().encode(), truth


def seed_demo(store, actor="local-user"):
    from .analysis import analyse
    from .importers import parse_reader

    description = "Synthetic buffer sample; no biological material"
    lot_id = "SYNTHETIC-LOT-2026"
    name = "Synthetic demo, seed 2026"
    mapping, content, truth = synthetic_plate()
    expected_wells = sorted(
        [{**w, "dilution_factor": w.get("dilution_factor", 1)} for w in mapping], key=lambda w: w["well"]
    )
    with store.transaction():
        samples = {s["id"]: s for s in store.list_records("samples")}
        for sample_id in truth:
            if sample_id in samples and samples[sample_id]["description"] != description:
                raise ValueError(
                    f"Reserved demo sample {sample_id} already has unrelated data; use a separate demo database"
                )
            if sample_id not in samples:
                store.create_sample(dict(id=sample_id, description=description), actor)
        lots = {lot["id"]: lot for lot in store.list_records("lots")}
        if lot_id in lots:
            lot = lots[lot_id]
            if (
                lot["reagent"] != "Synthetic assay reagent"
                or date.fromisoformat(lot["expires_on"]) < date.today()
            ):
                raise ValueError(
                    "Reserved demo lot has unrelated or expired data; use a separate demo database"
                )
        else:
            store.create_lot(
                dict(
                    id=lot_id,
                    reagent="Synthetic assay reagent",
                    expires_on=str(date.today() + timedelta(days=365)),
                ),
                actor,
            )
        existing = next((p for p in store.list_records("plates") if p["name"] == name), None)
        if existing:
            plate = store.get_plate(existing["id"])
            imported = next(
                (i for i in plate["imports"] if i["sha256"] == hashlib.sha256(content).hexdigest()), None
            )
            if (
                plate["lot_id"] != lot_id
                or plate["unit"] != "ng/mL"
                or plate["wells"] != expected_wells
                or not imported
            ):
                raise ValueError("Reserved demo plate has unrelated data; use a separate demo database")
            for saved in plate["analyses"]:
                snapshot = store.get_analysis(saved["id"])
                if (
                    snapshot["result"].get("provenance")
                    == dict(kind="synthetic", seed=2026, ground_truth=truth)
                    and snapshot["import_id"] == imported["id"]
                ):
                    return dict(plate_id=plate["id"], analysis_id=saved["id"]), False
            raise ValueError(
                "Reserved demo plate has no verified synthetic snapshot; use a separate demo database"
            )
        plate = store.create_plate(dict(name=name, lot_id=lot_id, unit="ng/mL", wells=mapping), actor)
        signals = parse_reader("synthetic-reader.csv", content)
        run = store.add_import(plate["id"], "synthetic-reader.csv", content, signals, actor)
        result = analyse(mapping, signals)
        result.update(
            unit="ng/mL",
            reagent_lot=plate["lot"],
            source_sha256=run["sha256"],
            analysed_on=str(date.today()),
            provenance=dict(kind="synthetic", seed=2026, ground_truth=truth),
        )
        analysis = store.save_analysis(run["id"], "4pl", result, actor)
        return dict(plate_id=plate["id"], analysis_id=analysis["id"]), True


if __name__ == "__main__":
    import argparse
    from pathlib import Path

    from .store import Store

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="assays.sqlite")
    parser.add_argument("--export", type=Path)
    args = parser.parse_args()
    data, _ = seed_demo(Store(args.db))
    if args.export:
        import json

        args.export.mkdir(parents=True, exist_ok=True)
        mapping, content, truth = synthetic_plate()
        (args.export / "synthetic-reader.csv").write_bytes(content)
        (args.export / "synthetic-map.json").write_text(json.dumps(mapping, indent=2) + "\n")
        (args.export / "synthetic-truth.json").write_text(json.dumps(truth, indent=2) + "\n")
    print(data)
