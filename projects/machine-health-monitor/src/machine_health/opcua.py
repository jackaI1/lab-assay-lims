"""Read-only OPC UA collector and an explicitly separate, fault-injectable training source."""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import suppress
from datetime import datetime, timezone

from asyncua import Client, Server, ua

from .core import TAGS, Frame, Monitor

NAMESPACE = "urn:jacklai:filling-line"
SCENARIOS = (
    "normal",
    "slow",
    "faults",
    "stopped",
    "stale",
    "missing",
    "out_of_range",
    "duplicate",
    "bad_status",
)
VARIANTS = {
    "cycle_count": ua.VariantType.UInt32,
    "cycle_time": ua.VariantType.Double,
    "motor_running": ua.VariantType.Boolean,
    "fault_code": ua.VariantType.UInt16,
    "fault_count": ua.VariantType.UInt32,
}


class Simulator:
    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        self.server = Server()
        self.nodes = {}
        self.scenario = "normal"
        self.count = self.fault_count = 0
        self._last_cycle = None

    async def __aenter__(self):
        await self.server.init()
        self.server.set_endpoint(self.endpoint)
        self.server.set_server_name("Simulated filling line (no physical equipment)")
        self.server.set_security_policy([ua.SecurityPolicyType.NoSecurity])
        idx = await self.server.register_namespace(NAMESPACE)
        line = await self.server.nodes.objects.add_object(idx, "FillingLine")
        for tag in TAGS:
            initial = False if tag == "motor_running" else 2.0 if tag == "cycle_time" else 0
            self.nodes[tag] = await line.add_variable(
                ua.NodeId(tag, idx), tag, initial, VARIANTS[tag]
            )
        await self.server.start()
        return self

    async def __aexit__(self, *_):
        await self.server.stop()

    async def publish(self, now: float | None = None):
        now = time.time() if now is None else now
        if self.scenario == "duplicate":
            return
        cycle_time = 3.5 if self.scenario == "slow" else 2.0
        fault = self.scenario == "faults"
        running = self.scenario != "stopped" and not fault
        if self._last_cycle is None:
            self._last_cycle = now
        if running and now - self._last_cycle >= cycle_time:
            self.count += int((now - self._last_cycle) // cycle_time)
            self._last_cycle = now
        elif not running:
            self._last_cycle = now
        # Repeated conveyor trips, one per publication, for an obvious fault-rate exercise.
        if fault:
            self.fault_count += 1
        values = {
            "cycle_count": self.count,
            "cycle_time": cycle_time,
            "motor_running": running,
            "fault_code": 2 if fault else 0,
            "fault_count": self.fault_count,
        }
        timestamp = datetime.fromtimestamp(
            now - (60 if self.scenario == "stale" else 0), timezone.utc
        )
        for tag, value in values.items():
            variant = VARIANTS[tag]
            if tag == "cycle_time":
                if self.scenario == "missing":
                    value, variant = None, ua.VariantType.Null
                elif self.scenario == "out_of_range":
                    value = 999.0
            status = (
                ua.StatusCode(ua.StatusCodes.BadSensorFailure)
                if self.scenario == "bad_status" and tag == "cycle_time"
                else ua.StatusCode(ua.StatusCodes.BadNoData)
                if self.scenario == "missing" and tag == "cycle_time"
                else ua.StatusCode()
            )
            dv = ua.DataValue(
                ua.Variant(value, variant), SourceTimestamp=timestamp, StatusCode_=status
            )
            await self.nodes[tag].write_value(dv)

    async def run(self, period=1.0):
        while True:
            await self.publish()
            await asyncio.sleep(period)


class Collector:
    def __init__(self, endpoint: str, monitor: Monitor, namespace=NAMESPACE):
        self.endpoint, self.monitor, self.namespace = endpoint, monitor, namespace
        self.client = None
        self.nodes = []

    async def __aenter__(self):
        self.client = Client(self.endpoint, timeout=2)
        try:
            await self.client.connect()
            idx = await self.client.get_namespace_index(self.namespace)
            self.nodes = [self.client.get_node(ua.NodeId(tag, idx)) for tag in TAGS]
        except BaseException:
            await self.__aexit__()
            raise
        return self

    async def __aexit__(self, *_):
        if self.client:
            with suppress(Exception):
                await self.client.disconnect()
            self.client = None

    async def poll(self, now: float | None = None):
        data = await self.client.read_attributes(self.nodes)
        now = time.time() if now is None else now
        values = {tag: dv.Value.Value if dv.Value else None for tag, dv in zip(TAGS, data)}
        timestamps = [dv.SourceTimestamp.timestamp() if dv.SourceTimestamp else None for dv in data]
        coherent = (
            all(t is not None for t in timestamps) and max(timestamps) - min(timestamps) < 0.001
        )
        frame = Frame(
            values,
            timestamps[0] if coherent else None,
            all(dv.StatusCode.is_good() for dv in data),
            () if coherent else ("incoherent_frame",),
        )
        return self.monitor.ingest(frame, now)

    async def sample_once(self):
        """One bounded connection attempt, used for recovery checks and external scripts."""
        try:
            async with self:
                return await self.poll()
        except (OSError, asyncio.TimeoutError, ua.UaError, ConnectionError, ValueError) as error:
            self.monitor.disconnected(time.time(), type(error).__name__)
            return {"accepted": False, "reasons": ["connection_lost"]}

    async def run(self):
        """Reuse a session while healthy; retry disconnected sources without losing history."""
        while True:
            try:
                async with self:
                    while True:
                        await self.poll()
                        await asyncio.sleep(self.monitor.config.poll_seconds)
            except (
                OSError,
                asyncio.TimeoutError,
                ua.UaError,
                ConnectionError,
                ValueError,
            ) as error:
                logging.getLogger(__name__).warning("OPC UA unavailable: %s", type(error).__name__)
                self.monitor.disconnected(time.time(), type(error).__name__)
                await asyncio.sleep(self.monitor.config.poll_seconds)
