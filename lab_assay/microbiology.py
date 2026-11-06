"""Synthetic plate count and environmental monitoring calculations."""

import csv
import json
from datetime import datetime, timezone
from pathlib import Path


def plate_result(counts, dilution, volume_ml, limit, countable=(25, 250), agreement=0.2):
    if (
        dilution <= 0
        or dilution > 1
        or volume_ml <= 0
        or limit < 0
        or not counts
        or any(int(c) != c or c < 0 for c in counts)
    ):
        raise ValueError("invalid plate inputs")
    if any(not countable[0] <= c <= countable[1] for c in counts):
        return {"status": "invalid", "reason": "outside countable range", "cfu": None}
    mean = sum(counts) / len(counts)
    if len(counts) > 1 and (max(counts) - min(counts)) / mean > agreement:
        return {"status": "invalid", "reason": "plate agreement", "cfu": None}
    cfu = mean / dilution / volume_ml
    return {"cfu": cfu, "status": "pass" if cfu <= limit else "fail"}


def environmental_flags(records, limits):
    seen = {}
    result = []
    for row in records:
        threshold = limits[row["room"]]
        count = float(row["count"])
        if count < 0 or threshold["alert"] > threshold["action"]:
            raise ValueError("invalid monitoring limits or count")
        level = (
            "action" if count >= threshold["action"] else "alert" if count >= threshold["alert"] else "normal"
        )
        key = (row["room"], row["location"])
        seen[key] = seen.get(key, 0) + 1 if level != "normal" else 0
        result.append({**row, "level": level, "repeat_location": seen[key] >= 2})
    return result


def media_volume(plates, ml_per_plate, overage_percent=0):
    if plates < 0 or ml_per_plate <= 0 or overage_percent < 0:
        raise ValueError("invalid media preparation")
    return plates * ml_per_plate * (1 + overage_percent / 100)


def plate_report(path, limit, unit="mL"):
    with Path(path).open(newline="") as f:
        rows = list(csv.DictReader(f))
    results = []
    for row in rows:
        result = plate_result(
            [int(row["plate_1"]), int(row["plate_2"])], float(row["dilution"]), float(row["volume_ml"]), limit
        )
        results.append({**row, **result, "unit": f"CFU/{unit}"})
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": str(path),
        "criteria": {"limit": limit, "countable": [25, 250], "agreement": 0.2},
        "audit": [
            {
                "event": "import and calculate",
                "source": str(path),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ],
        "results": results,
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv")
    parser.add_argument("--limit", type=float, required=True)
    parser.add_argument("--unit", choices=["g", "mL"], default="mL")
    parser.add_argument("--output", default="microbiology-report.json")
    parser.add_argument("--environment", help="CSV with room, location and count columns in time order")
    parser.add_argument("--limits", help="JSON mapping room grades to alert and action counts")
    parser.add_argument("--media-lot", help="Synthetic medium lot identifier")
    parser.add_argument("--plates", type=int, default=0)
    parser.add_argument("--ml-per-plate", type=float, default=15)
    parser.add_argument("--overage", type=float, default=10)
    args = parser.parse_args()
    report = plate_report(args.csv, args.limit, args.unit)
    if bool(args.environment) != bool(args.limits):
        parser.error("--environment and --limits must be supplied together")
    if args.environment:
        with Path(args.environment).open(newline="") as f:
            records = list(csv.DictReader(f))
        limits = json.loads(Path(args.limits).read_text())
        report["environment"] = {"limits": limits, "results": environmental_flags(records, limits)}
        report["audit"].append(
            {"event": "monitoring import", "source": args.environment, "timestamp": report["created_at"]}
        )
    if args.media_lot:
        report["media"] = {
            "lot": args.media_lot,
            "plates": args.plates,
            "ml_per_plate": args.ml_per_plate,
            "overage_percent": args.overage,
            "total_ml": media_volume(args.plates, args.ml_per_plate, args.overage),
        }
    Path(args.output).write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
