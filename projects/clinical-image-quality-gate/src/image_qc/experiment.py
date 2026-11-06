"""Source-disjoint training, held-out evaluation, and auditable row-level outputs."""

import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from sklearn.model_selection import train_test_split

from .data import download, load_manifest
from .images import VARIANTS, degrade, features, lesion_vector, load_image, quality_vector
from .models import calibrate_rules, fit_logistic, probability, quality_decision

SEED = 42


def split_sources(records: list[dict]) -> dict[str, str]:
    if len({r["lesion_id"] for r in records}) != len(records):
        raise ValueError("each lesion must occur once before source splitting")
    ordered = sorted(records, key=lambda r: r["isic_id"])
    train_val, test = train_test_split(
        ordered, test_size=0.2, random_state=SEED, stratify=[r["label"] for r in ordered]
    )
    train, validation = train_test_split(
        train_val, test_size=0.25, random_state=SEED, stratify=[r["label"] for r in train_val]
    )
    return {
        r["isic_id"]: split
        for split, group in (("train", train), ("validation", validation), ("test", test))
        for r in group
    }


def accuracy(rows: list[dict]) -> dict:
    correct = sum(r["lesion_pred"] == r["label"] for r in rows)
    return {"n": len(rows), "correct": correct, "accuracy": correct / len(rows) if rows else None}


def rate(n: int, total: int) -> dict:
    return {"n": n, "total": total, "rate": n / total if total else None}


def bootstrap_difference(rows: list[dict], method: str, repeats: int) -> dict:
    """Resample sources (all variants together), not correlated individual images."""
    ids = sorted({r["isic_id"] for r in rows})
    counts = []
    for source in ids:
        group = [r for r in rows if r["isic_id"] == source]
        accepted = [r for r in group if r[method + "_accept"]]
        rejected = [r for r in group if not r[method + "_accept"]]
        counts.append(
            [
                len(accepted),
                sum(r["lesion_pred"] == r["label"] for r in accepted),
                len(rejected),
                sum(r["lesion_pred"] == r["label"] for r in rejected),
            ]
        )
    counts = np.array(counts)
    rng, diffs = np.random.default_rng(SEED), []
    for _ in range(repeats):
        a, ac, b, bc = counts[rng.integers(len(ids), size=len(ids))].sum(axis=0)
        if a and b:
            diffs.append(ac / a - bc / b)
    return {
        "unit": "source lesion",
        "repeats": repeats,
        "valid_repeats": len(diffs),
        "accepted_minus_rejected_ci95": np.quantile(diffs, [0.025, 0.975]).tolist()
        if diffs
        else None,
    }


def summarize(rows: list[dict], bootstrap: int = 500) -> dict:
    if not rows:
        raise ValueError("empty evaluation: no photo versions to score")
    result = {
        "overall": accuracy(rows),
        "clean_baseline": accuracy([r for r in rows if r["kind"] == "clean"]),
    }
    for method in ("rules", "learned"):
        key = method + "_accept"
        bad = [r for r in rows if r["bad"]]
        good = [r for r in rows if not r["bad"]]
        clean = [r for r in rows if r["kind"] == "clean"]
        result[method] = {
            "accepted": accuracy([r for r in rows if r[key]]),
            "rejected": accuracy([r for r in rows if not r[key]]),
            "coverage": rate(sum(r[key] for r in rows), len(rows)),
            "bad_rejected": rate(sum(not r[key] for r in bad), len(bad)),
            "acceptable_retained": rate(sum(r[key] for r in good), len(good)),
            "clean_retained": rate(sum(r[key] for r in clean), len(clean)),
            "by_class": {
                str(label): {
                    "accepted": accuracy([r for r in rows if r["label"] == label and r[key]]),
                    "rejected": accuracy([r for r in rows if r["label"] == label and not r[key]]),
                }
                for label in (0, 1)
            },
            "bootstrap": bootstrap_difference(rows, method, bootstrap),
        }
    result["by_degradation"] = []
    for kind, strength in VARIANTS:
        group = [r for r in rows if r["kind"] == kind and r["strength"] == strength]
        result["by_degradation"].append(
            {
                "kind": kind,
                "strength": strength,
                "bad": int(strength >= 2),
                "n": len(group),
                "baseline": accuracy(group),
                **{
                    m: rate(sum(not r[m + "_accept"] for r in group), len(group))
                    for m in ("rules", "learned")
                },
            }
        )
    if rows and "reject_probability" in rows[0]:
        result["threshold_curve"] = [
            {
                "threshold": t,
                **accuracy(
                    [
                        r
                        for r in rows
                        if r["reject_probability"] is not None and r["reject_probability"] <= t
                    ]
                ),
            }
            for t in np.linspace(0, 1, 21).tolist()
        ]
    return result


def run(manifest: str | Path, image_dir: str | Path, output: str | Path) -> dict:
    records = load_manifest(manifest)
    download(records, image_dir)
    splits = split_sources(records)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    quality_x, quality_y, lesion_x, lesion_y, validation_good = [], [], [], [], []
    # Bounded memory: retain feature vectors, never an augmented image collection.
    for r in records:
        split = splits[r["isic_id"]]
        if split == "test":
            continue
        image = load_image(Path(image_dir) / (r["isic_id"] + ".jpg"))
        if split == "train":
            lesion_x.append(lesion_vector(image))
            lesion_y.append(r["label"])
        for kind, strength in VARIANTS:
            damaged = degrade(image, kind, strength, seed=int(r["isic_id"][5:]))
            if split == "train":
                quality_x.append(quality_vector(damaged))
                quality_y.append(int(strength >= 2))
            elif strength < 2:
                validation_good.append(damaged)
    quality = fit_logistic(np.array(quality_x), np.array(quality_y))
    # Fixed target: retain 90% of validation images labelled acceptable.
    threshold = float(
        np.quantile(
            [float(probability(quality, quality_vector(im))) for im in validation_good], 0.90
        )
    )
    bundle = {
        "schema_version": 1,
        "seed": SEED,
        "quality": quality,
        "threshold": threshold,
        "lesion": fit_logistic(np.array(lesion_x), np.array(lesion_y)),
        "rules": calibrate_rules([features(im) for im in validation_good]),
        "quality_feature_names": list(features(validation_good[0])),
        "manifest_sha256": hashlib.sha256(Path(manifest).read_bytes()).hexdigest(),
    }
    (output / "models.json").write_text(json.dumps(bundle, indent=2) + "\n")
    (output / "splits.json").write_text(json.dumps(splits, indent=2, sort_keys=True) + "\n")
    rows = []
    for r in records:
        if splits[r["isic_id"]] != "test":
            continue
        image = load_image(Path(image_dir) / (r["isic_id"] + ".jpg"))
        for kind, strength in VARIANTS:
            damaged = degrade(image, kind, strength, seed=int(r["isic_id"][5:]))
            learned = quality_decision(damaged, bundle)
            rules = quality_decision(damaged, bundle, "rules")
            # Deliberate counterfactual evaluation: score rejected images here only.
            # The real selective_predict CLI never calls the lesion model after abstaining.
            pred = int(probability(bundle["lesion"], lesion_vector(damaged)) >= 0.5)
            rows.append(
                {
                    "isic_id": r["isic_id"],
                    "lesion_id": r["lesion_id"],
                    "kind": kind,
                    "strength": strength,
                    "bad": int(strength >= 2),
                    "label": r["label"],
                    "lesion_pred": pred,
                    "rules_accept": rules["decision"] == "accept",
                    "learned_accept": learned["decision"] == "accept",
                    "reject_probability": learned["reject_probability"],
                    **features(damaged),
                }
            )
    with (output / "predictions.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    metrics = summarize(rows)
    metrics["dataset"] = {
        "sources": len(records),
        "variants_per_source": len(VARIANTS),
        "split_counts": {
            s: list(splits.values()).count(s) for s in ("train", "validation", "test")
        },
        "manifest_sha256": bundle["manifest_sha256"],
        "seed": SEED,
    }
    (output / "metrics.json").write_text(json.dumps(metrics, indent=2, allow_nan=False) + "\n")
    from .report import write_report

    write_report(metrics, rows, records, image_dir, output, bundle)
    return metrics
