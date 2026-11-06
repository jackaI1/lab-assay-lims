import time

import pytest

from machine_health.core import Config, Monitor
from machine_health.opcua import Collector, Simulator


@pytest.mark.parametrize(
    ("scenario", "rule", "reason"),
    [
        ("slow", "cycle_drift", None),
        ("faults", "fault_rate", None),
        ("stopped", "availability", None),
        ("stale", "data_quality", "stale"),
        ("missing", "data_quality", "missing:cycle_time"),
        ("out_of_range", "data_quality", "out_of_range:cycle_time"),
        ("duplicate", "data_quality", "duplicate"),
        ("bad_status", "data_quality", "bad_status"),
    ],
)
async def test_real_opcua_fault_fires_deduplicates_and_clears(
    tmp_path, endpoint, scenario, rule, reason
):
    base = time.time()
    with Monitor(tmp_path / "history.sqlite3", Config(window_seconds=6)) as monitor:
        async with Simulator(endpoint) as simulator:
            async with Collector(endpoint, monitor) as collector:
                for step in range(3):
                    await simulator.publish(base + step)
                    assert (await collector.poll(base + step))["accepted"]
                simulator.scenario = scenario
                for step in range(3, 8):
                    await simulator.publish(base + step)
                    result = await collector.poll(base + step)
                incident = next(a for a in monitor.alerts() if a["rule"] == rule)
                assert incident["state"] == "active"
                assert incident["occurrences"] >= 2
                assert len([a for a in monitor.alerts() if a["rule"] == rule]) == 1
                if reason:
                    assert reason in result["reasons"]
                assert monitor.acknowledge(incident["id"], base + 8)
                simulator.scenario = "normal"
                for step in range(8, 18):
                    await simulator.publish(base + step)
                    await collector.poll(base + step)
                recovered = next(a for a in monitor.alerts() if a["id"] == incident["id"])
                assert recovered["state"] == "cleared"
                assert recovered["acknowledged"] == base + 8
                assert monitor.snapshot(base + 17)["condition"] == "healthy"


async def test_disconnect_reconnect_and_socket_cleanup(tmp_path, endpoint):
    import socket
    from urllib.parse import urlparse

    with Monitor(tmp_path / "log.sqlite3") as monitor:
        async with Simulator(endpoint) as simulator:
            await simulator.publish(time.time())
            async with Collector(endpoint, monitor) as collector:
                assert (await collector.poll())["accepted"]
        # Same endpoint is now offline; failed connection must produce a retained incident.
        collector = Collector(endpoint, monitor)
        assert not (await collector.sample_once())["accepted"]
        assert monitor.snapshot(time.time())["condition"] == "unknown"
        assert monitor.alerts()[0]["rule"] == "connection_lost"
        async with Simulator(endpoint) as simulator:
            await simulator.publish(time.time())
            assert (await collector.sample_once())["accepted"]
        assert (
            next(a for a in monitor.alerts() if a["rule"] == "connection_lost")["state"]
            == "cleared"
        )
        with socket.socket() as sock:
            assert sock.connect_ex(("127.0.0.1", urlparse(endpoint).port)) != 0


async def test_mixed_tag_timestamps_rejected(tmp_path, endpoint):
    from datetime import datetime, timezone

    from asyncua import ua

    with Monitor(tmp_path / "log.sqlite3") as monitor:
        async with Simulator(endpoint) as simulator:
            now = time.time()
            await simulator.publish(now)
            dv = ua.DataValue(
                ua.Variant(2.0, ua.VariantType.Double),
                SourceTimestamp=datetime.fromtimestamp(now - 1, timezone.utc),
            )
            await simulator.nodes["cycle_time"].write_value(dv)
            async with Collector(endpoint, monitor) as collector:
                result = await collector.poll(now)
                assert not result["accepted"]
                assert "incoherent_frame" in result["reasons"]


async def test_long_running_collector_recovers_after_server_restart(tmp_path, endpoint):
    import asyncio
    from contextlib import suppress

    async def until(predicate):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if predicate():
                return
            await asyncio.sleep(0.05)
        pytest.fail("Collector did not reach expected connection state")

    with Monitor(tmp_path / "log.sqlite3", Config(poll_seconds=0.1)) as monitor:
        collector = Collector(endpoint, monitor)
        task = publisher = None
        try:
            async with Simulator(endpoint) as simulator:
                await simulator.publish()
                publisher = asyncio.create_task(simulator.run(0.1))
                task = asyncio.create_task(collector.run())
                await until(lambda: any(r["accepted"] for r in monitor.readings()))
                publisher.cancel()
                with suppress(asyncio.CancelledError):
                    await publisher
            await until(
                lambda: any(
                    a["rule"] == "connection_lost" and a["state"] == "active"
                    for a in monitor.alerts()
                )
            )
            async with Simulator(endpoint) as simulator:
                await simulator.publish()
                publisher = asyncio.create_task(simulator.run(0.1))
                await until(
                    lambda: any(
                        a["rule"] == "connection_lost" and a["state"] == "cleared"
                        for a in monitor.alerts()
                    )
                )
                assert not task.done()
        finally:
            for owned in (task, publisher):
                if owned:
                    owned.cancel()
                    with suppress(asyncio.CancelledError):
                        await owned


async def test_wrong_opcua_payload_is_retained_and_next_sample_recovers(tmp_path, endpoint):
    from datetime import datetime, timezone

    from asyncua import ua

    with Monitor(tmp_path / "log.sqlite3") as monitor:
        async with Simulator(endpoint) as simulator:
            now = time.time()
            await simulator.publish(now)
            old = simulator.nodes["cycle_time"]
            parent, nodeid = await old.get_parent(), old.nodeid
            await old.delete()
            replacement = await parent.add_variable(
                nodeid, "cycle_time", b"wrong type", ua.VariantType.ByteString
            )
            await replacement.write_value(
                ua.DataValue(
                    ua.Variant(b"wrong type", ua.VariantType.ByteString),
                    SourceTimestamp=datetime.fromtimestamp(now, timezone.utc),
                )
            )
            async with Collector(endpoint, monitor) as collector:
                result = await collector.poll(now)
                assert result["reasons"] == ["invalid_type:cycle_time"]
                assert monitor.readings()[0]["raw"]["cycle_time"]["type"] == "bytes"
                await replacement.delete()
                simulator.nodes["cycle_time"] = await parent.add_variable(
                    nodeid, "cycle_time", 2.0, ua.VariantType.Double
                )
                await simulator.publish(now + 1)
                assert (await collector.poll(now + 1))["accepted"]
