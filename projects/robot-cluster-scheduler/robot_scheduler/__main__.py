import argparse
import json
from .simulation import Batch, Step, simulate


def main():
    parser = argparse.ArgumentParser(description="Compare batch scheduling rules")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--batches", type=int, default=12)
    args = parser.parse_args()
    if args.batches < 1:
        parser.error("--batches must be positive")
    steps = (Step("load incubator", 40, ("robot", "incubator")),
             Step("incubate", 300, ("incubator",)),
             Step("centrifuge", 120, ("robot", "centrifuge")),
             Step("fill", 90, ("robot", "fill_station")))
    batches = [Batch(f"batch-{i+1}", i * 30, 900 + i * 60, steps) for i in range(args.batches)]
    capacities = {"robot": 2, "incubator": 2, "centrifuge": 1, "fill_station": 1}
    print(json.dumps([simulate(batches, capacities, rule, args.seed) for rule in ("fifo", "earliest_due")], indent=2))


if __name__ == "__main__":
    main()
