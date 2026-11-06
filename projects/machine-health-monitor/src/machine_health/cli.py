"""One foreground process owns the web server, OPC UA session and optional simulator."""

import argparse
import asyncio
import json
import logging
from contextlib import AsyncExitStack, asynccontextmanager, suppress
from pathlib import Path

import uvicorn

from .core import Config, Monitor
from .opcua import NAMESPACE, Collector, Simulator
from .web import create_app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["demo", "monitor"])
    parser.add_argument("--db", type=Path, default=Path(".build/health.sqlite3"))
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--opc-port", type=int, default=4840, help="Local demo source port")
    parser.add_argument("--endpoint", help="Read-only OPC UA source URL for monitor mode")
    parser.add_argument("--namespace", default=NAMESPACE)
    parser.add_argument("--config", type=Path, help="JSON rule thresholds; see config.example.json")
    args = parser.parse_args()
    if args.mode == "monitor" and not args.endpoint:
        parser.error("monitor mode needs --endpoint")
    try:
        config = Config(**json.loads(args.config.read_text())) if args.config else Config()
    except (ValueError, TypeError, OSError) as error:
        parser.error(str(error))
    args.db.parent.mkdir(parents=True, exist_ok=True)
    endpoint = (
        f"opc.tcp://127.0.0.1:{args.opc_port}/filling-line/"
        if args.mode == "demo"
        else args.endpoint
    )
    simulator = Simulator(endpoint) if args.mode == "demo" else None
    logging.basicConfig(level=logging.WARNING)
    with Monitor(args.db, config) as monitor:
        collector = Collector(endpoint, monitor, args.namespace)

        @asynccontextmanager
        async def lifespan(app):
            tasks = []
            async with AsyncExitStack() as stack:
                try:
                    if simulator:
                        await stack.enter_async_context(simulator)
                        await simulator.publish()
                        tasks.append(asyncio.create_task(simulator.run(config.poll_seconds)))
                    tasks.append(asyncio.create_task(collector.run()))
                    yield
                finally:
                    for task in tasks:
                        task.cancel()
                    for task in tasks:
                        with suppress(asyncio.CancelledError):
                            await task

        uvicorn.run(
            create_app(monitor, simulator, lifespan),
            host="127.0.0.1",
            port=args.port,
            log_level="warning",
        )


if __name__ == "__main__":
    main()
