import asyncio
import json
import sys
import time
from urllib.parse import urlparse

import pytest

from machine_health import cli
from machine_health.core import Monitor
from machine_health.opcua import Collector, Simulator


@pytest.mark.parametrize("args", [[], ["monitor"], ["demo", "--config", "/missing/rules.json"]])
def test_cli_explains_invalid_arguments(monkeypatch, args):
    monkeypatch.setattr(sys, "argv", ["machine-health", *args])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2


async def test_cli_owns_runtime_tasks_and_stops_them(tmp_path, endpoint, monkeypatch):
    captured = {}
    config = tmp_path / "rules.json"
    config.write_text(json.dumps({"poll_seconds": 0.1}))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "machine-health",
            "demo",
            "--db",
            str(tmp_path / "cli.sqlite3"),
            "--opc-port",
            str(urlparse(endpoint).port),
            "--config",
            str(config),
        ],
    )
    monkeypatch.setattr(cli.uvicorn, "run", lambda app, **kwargs: captured.update(app=app))
    # main normally owns the monitor until uvicorn returns. Capture a fresh equivalent
    # monitor for lifespan execution because this stub returns immediately.
    original = cli.Monitor
    monitor = Monitor(tmp_path / "runtime.sqlite3")
    monkeypatch.setattr(cli, "Monitor", lambda *args: monitor)
    monkeypatch.setattr(Monitor, "__exit__", lambda *args: None)
    before = set(asyncio.all_tasks())
    try:
        cli.main()
        app = captured["app"]
        async with app.router.lifespan_context(app):
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and not monitor.readings():
                await asyncio.sleep(0.05)
            assert monitor.readings()[0]["accepted"]
        assert not [t for t in asyncio.all_tasks() - before if not t.done()]
    finally:
        monitor.db.close()
        monkeypatch.setattr(cli, "Monitor", original)


async def test_unknown_namespace_is_retained_connection_failure(tmp_path, endpoint):
    async with Simulator(endpoint):
        with Monitor(tmp_path / "log.sqlite3") as monitor:
            collector = Collector(endpoint, monitor, namespace="urn:missing")
            result = await collector.sample_once()
            assert not result["accepted"]
            assert monitor.alerts()[0]["rule"] == "connection_lost"
