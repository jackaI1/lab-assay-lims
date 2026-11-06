"""Local service dashboard. No machine-control writes are exposed."""

import time
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .core import Monitor
from .opcua import SCENARIOS, Simulator

STATIC = Path(__file__).parent / "static"


class Scenario(BaseModel):
    scenario: Literal[
        "normal",
        "slow",
        "faults",
        "stopped",
        "stale",
        "missing",
        "out_of_range",
        "duplicate",
        "bad_status",
    ]


def create_app(monitor: Monitor, simulator: Simulator | None = None, lifespan=None):
    app = FastAPI(title="Filling-line health monitor", lifespan=lifespan)
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"]
    )

    @app.middleware("http")
    async def local_writes(request: Request, call_next):
        origin = request.headers.get("origin")
        if (
            request.method == "POST"
            and origin
            and urlparse(origin).netloc != request.headers["host"]
        ):
            return PlainTextResponse("Only same-origin local actions are allowed.", status_code=403)
        return await call_next(request)

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/api/status")
    async def status():
        return monitor.snapshot(time.time()) | {
            "demo": simulator is not None,
            "scenario": simulator.scenario if simulator else None,
            "scenarios": SCENARIOS if simulator else [],
        }

    @app.get("/api/readings")
    async def readings(limit: int = Query(100, ge=1, le=500)):
        return monitor.readings(limit)

    @app.post("/api/alerts/{incident_id}/ack")
    async def acknowledge(incident_id: int):
        if not monitor.acknowledge(incident_id, time.time()):
            raise HTTPException(409, "Alert is missing or no longer active.")
        return {"acknowledged": incident_id}

    @app.post("/api/scenario")
    async def scenario(body: Scenario):
        if simulator is None:
            raise HTTPException(403, "Fault injection is available only in local demo mode.")
        simulator.scenario = body.scenario
        return {"scenario": simulator.scenario}

    @app.get("/api/report", response_class=PlainTextResponse)
    async def report():
        snapshot = monitor.snapshot(time.time())
        lines = [
            "Filling-line service report",
            time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "",
            snapshot["report"],
            "",
        ]
        metrics = snapshot["metrics"]
        for label, key in [
            ("Availability", "availability"),
            ("Performance", "performance"),
            ("Cycle-time drift", "cycle_time_drift"),
            ("Usable window", "coverage"),
        ]:
            value = metrics[key]
            lines.append(
                f"{label}: {value * 100:.1f}%"
                if value is not None
                else f"{label}: not enough usable data"
            )
        rate = metrics["fault_rate_per_minute"]
        lines.append(
            f"Fault rate: {rate:.1f} events per observed minute"
            if rate is not None
            else "Fault rate: not enough usable data"
        )
        lines.extend(["", "Calculation details:"])
        for key, value in snapshot["metrics"].items():
            lines.append(f"{key}: {value if value is not None else 'not enough usable data'}")
        lines.extend(["", "Configured rules:"])
        lines.extend(f"{key}: {value}" for key, value in snapshot["config"].items())
        lines.extend(["", "Recent alert incidents:"])
        lines.extend(
            f"#{a['id']} {a['rule']}: {a['state']}. {a['message']}" for a in snapshot["alerts"]
        )
        lines.extend(["", "Recent rejected readings (up to 500):"])
        lines.extend(
            f"{r['received']}: {', '.join(r['reasons'])}"
            for r in monitor.readings(500)
            if not r["accepted"]
        )
        return "\n".join(lines) + "\n"

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
