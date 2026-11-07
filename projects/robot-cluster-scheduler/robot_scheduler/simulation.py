"""A seeded, atomic-reservation dispatcher and SimPy execution model."""
from dataclasses import dataclass
import random
import simpy


@dataclass(frozen=True)
class Step:
    name: str
    duration: float
    resources: tuple


@dataclass(frozen=True)
class Batch:
    name: str
    arrival: float
    due: float
    steps: tuple


def simulate(batches, capacities, rule="fifo", seed=0, variation=0.15,
             fault_probability=0.05, repair_time=30):
    """Run batches; times and durations are seconds. Reservations are atomic.

    Each resource in a step consumes one unit. Robot faults add repair time while
    holding all step resources. A separate random stream per batch makes outcomes
    reproducible even when dispatch order changes.
    """
    batches = list(batches)
    if rule not in ("fifo", "earliest_due"):
        raise ValueError("unknown scheduling rule")
    if not 0 <= variation < 1 or not 0 <= fault_probability <= 1 or repair_time < 0:
        raise ValueError("invalid variation or fault parameters")
    if any(not isinstance(n, int) or n < 1 for n in capacities.values()):
        raise ValueError("capacities must be positive integers")
    if len({b.name for b in batches}) != len(batches):
        raise ValueError("batch names must be unique")
    for b in batches:
        if b.arrival < 0 or b.due < b.arrival or not b.steps:
            raise ValueError("invalid batch timing or empty steps")
        for step in b.steps:
            if step.duration <= 0 or len(set(step.resources)) != len(step.resources):
                raise ValueError("invalid step")
            if any(resource not in capacities for resource in step.resources):
                raise ValueError("unknown resource")

    env = simpy.Environment()
    available = dict(capacities)
    waiting = []
    records = []
    completed = {}
    wake = simpy.Store(env)
    streams = {b.name: random.Random(f"{seed}:{b.name}") for b in batches}
    sequence = iter(range(sum(len(b.steps) for b in batches)))

    def enqueue(batch, index):
        waiting.append((next(sequence), batch, index))
        wake.put(None)

    def arrive(batch):
        yield env.timeout(batch.arrival)
        enqueue(batch, 0)

    def execute(batch, index, step):
        start = env.now
        rng = streams[batch.name]
        duration = step.duration * rng.uniform(1 - variation, 1 + variation)
        fault = "robot" in step.resources and rng.random() < fault_probability
        if fault:
            duration += repair_time
        yield env.timeout(duration)
        records.append(dict(batch=batch.name, step=step.name, start=start,
                            end=env.now, resources=step.resources, fault=fault))
        for resource in step.resources:
            available[resource] += 1
        if index + 1 < len(batch.steps):
            enqueue(batch, index + 1)
        else:
            completed[batch.name] = env.now
            wake.put(None)

    def dispatch():
        while True:
            yield wake.get()
            # Skip blocked requests so independent work can proceed. Each step
            # takes all resources at once, so no process holds one while waiting.
            waiting.sort(key=lambda item: (item[1].due, item[0]) if rule == "earliest_due" else (item[0],))
            for item in waiting[:]:
                _, batch, index = item
                step = batch.steps[index]
                if all(available[r] > 0 for r in step.resources):
                    waiting.remove(item)
                    for resource in step.resources:
                        available[resource] -= 1
                    env.process(execute(batch, index, step))

    env.process(dispatch())
    for batch in batches:
        env.process(arrive(batch))
    env.run()
    if len(completed) != len(batches):
        raise RuntimeError("unfinished batches: resource requests cannot be dispatched")
    makespan = max(completed.values(), default=0)
    busy = {r: sum(x["end"] - x["start"] for x in records if r in x["resources"]) for r in capacities}
    return {"rule": rule, "seed": seed, "makespan_seconds": makespan,
            "throughput_per_hour": len(batches) * 3600 / makespan if makespan else 0,
            "utilization": {r: busy[r] / (makespan * n) if makespan else 0 for r, n in capacities.items()},
            "lateness_seconds": {b.name: max(0, completed[b.name] - b.due) for b in batches},
            "completed": completed, "steps": records}
