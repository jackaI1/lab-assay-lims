from hypothesis import given, settings, strategies as st
import pytest
from robot_scheduler.simulation import Batch, Step, simulate


@given(st.integers(1, 12), st.integers(0, 100000), st.sampled_from(["fifo", "earliest_due"]))
@settings(max_examples=60, deadline=None)
def test_capacity_and_reproducibility(count, seed, rule):
    steps = (Step("load", 3, ("robot", "incubator")),
             Step("hold", 8, ("incubator",)),
             Step("fill", 4, ("robot", "fill")))
    batches = [Batch(str(i), i % 3, 15 + i, steps) for i in range(count)]
    capacities = {"robot": 2, "incubator": 2, "fill": 1}
    result = simulate(batches, capacities, rule, seed, fault_probability=.3)
    assert result == simulate(batches, capacities, rule, seed, fault_probability=.3)
    assert len(result["completed"]) == count
    for resource, capacity in capacities.items():
        events = sorted((time, delta) for s in result["steps"] if resource in s["resources"]
                        for time, delta in ((s["start"], 1), (s["end"], -1)))
        active = 0
        for _, delta in events:
            active += delta
            assert 0 <= active <= capacity
        assert active == 0


def test_random_faults_change_duration_and_are_seeded():
    batches = [Batch(str(i), 0, 10, (Step("move", 1, ("robot",)),)) for i in range(40)]
    results = [simulate(batches, {"robot": 2}, seed=s, variation=0, fault_probability=.5, repair_time=5) for s in (1, 2)]
    faults = [[x["fault"] for x in r["steps"]] for r in results]
    assert any(faults[0]) and not all(faults[0])
    assert faults[0] != faults[1]
    assert all((x["end"] - x["start"] == 6) if x["fault"] else (x["end"] - x["start"] == 1) for x in results[0]["steps"])


def test_earliest_due_and_atomic_reservations():
    step = (Step("work", 10, ("robot", "fill")),)
    batches = [Batch("busy", 0, 100, step), Batch("late", 1, 90, step), Batch("urgent", 1, 20, step)]
    r = simulate(batches, {"robot": 1, "fill": 1}, "earliest_due", variation=0, fault_probability=0)
    assert [s["batch"] for s in r["steps"]] == ["busy", "urgent", "late"]
    assert r["lateness_seconds"]["urgent"] == 0


def test_unknown_resource_rejected():
    with pytest.raises(ValueError, match="unknown resource"):
        simulate([Batch("a", 0, 10, (Step("x", 1, ("missing",)),))], {"robot": 1})
