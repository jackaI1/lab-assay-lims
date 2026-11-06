"""Fail-closed, single-controller gateway. No cached control stream survives a loss."""
import asyncio
import contextlib
import json
import logging
import math
import secrets
import ssl
import time
from pathlib import Path

from pymavlink.dialects.v20 import common as mav

from .identity import context, fingerprint
from .wire import Codec, read_packet, write_packet

LOG = logging.getLogger(__name__)


class Policy:
    def __init__(self, timeout=0.75):
        self.timeout = timeout
        self.last_heartbeat = None

    def accept(self, msg, now):
        if (msg.get_srcSystem(), msg.get_srcComponent()) != (255, 190):
            raise ValueError("unexpected controller source")
        if self.last_heartbeat is not None and now - self.last_heartbeat >= self.timeout:
            raise ValueError("controller heartbeat expired")
        kind = msg.get_type()
        if kind == "HEARTBEAT":
            if msg.type != mav.MAV_TYPE_GCS or msg.autopilot != mav.MAV_AUTOPILOT_INVALID:
                raise ValueError("invalid controller heartbeat")
            self.last_heartbeat = now
            return
        if self.last_heartbeat is None or now - self.last_heartbeat >= self.timeout:
            raise ValueError("controller heartbeat expired")
        if (getattr(msg, "target_system", 0), getattr(msg, "target_component", 0)) != (1, 1):
            raise ValueError("wrong vehicle target")
        if kind == "SET_POSITION_TARGET_LOCAL_NED":
            values = [msg.x, msg.y, msg.z, msg.vx, msg.vy, msg.vz, msg.afx, msg.afy, msg.afz,
                      msg.yaw, msg.yaw_rate]
            if (not all(math.isfinite(v) for v in values) or msg.coordinate_frame != mav.MAV_FRAME_LOCAL_NED
                    or msg.type_mask != 0xDF8 or abs(msg.x) > 10 or abs(msg.y) > 10 or not -5 <= msg.z <= 0):
                raise ValueError("setpoint outside simulation envelope")
        elif kind == "COMMAND_LONG":
            params = tuple(getattr(msg, f"param{i}") for i in range(1, 8))
            allowed = {
                mav.MAV_CMD_COMPONENT_ARM_DISARM: {(1., 0., 0., 0., 0., 0., 0.), (0., 0., 0., 0., 0., 0., 0.)},
                mav.MAV_CMD_DO_SET_MODE: {(1., 6., 0., 0., 0., 0., 0.), (1., 4., 6., 0., 0., 0., 0.)},
            }
            if params not in allowed.get(msg.command, set()):
                raise ValueError("command is not permitted")
        else:
            raise ValueError("message is not permitted")


class VehicleUDP(asyncio.DatagramProtocol):
    def __init__(self, remote):
        self.remote = remote
        self.listeners = set()
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        if addr != self.remote:
            return
        for queue in self.listeners:
            if not queue.full():
                queue.put_nowait(data)

    def send(self, packet):
        self.transport.sendto(packet, self.remote)


class Gateway:
    def __init__(self, credentials: Path, vehicle, timeout=0.75):
        self.credentials = credentials
        self.vehicle = vehicle
        self.timeout = timeout
        self.active = False
        self.handlers = set()
        self.forwarded = 0
        self.rejected = 0

    async def handle(self, reader, writer):
        task = asyncio.current_task()
        self.handlers.add(task)
        claimed = False
        telemetry = None
        queue = asyncio.Queue(maxsize=64)
        try:
            cert = writer.get_extra_info("ssl_object").getpeercert(binary_form=True)
            allowed = json.loads((self.credentials / "controllers.json").read_text())
            if fingerprint(cert) not in allowed or self.active:
                raise ValueError("controller is unlisted or another session owns control")
            self.active = claimed = True
            key = secrets.token_bytes(32)
            writer.write(b"ID01" + key)
            await writer.drain()
            inbound = Codec(key)
            outbound = Codec(key, system=1, component=1, link=2)
            vehicle_codec = Codec(secrets.token_bytes(32), system=255, component=190, link=3)
            policy = Policy(self.timeout)
            self.vehicle.listeners.add(queue)

            async def relay_telemetry():
                parser = mav.MAVLink(None)
                parser.robust_parsing = True
                while True:
                    for msg in parser.parse_buffer(await queue.get()) or []:
                        if msg.get_type() in {"HEARTBEAT", "LOCAL_POSITION_NED", "COMMAND_ACK",
                                              "STATUSTEXT", "EXTENDED_SYS_STATE", "AUTOPILOT_VERSION"}:
                            await write_packet(writer, outbound.pack(msg))

            telemetry = asyncio.create_task(relay_telemetry())
            deadline = time.monotonic() + self.timeout
            while True:
                packet = await asyncio.wait_for(read_packet(reader), max(0.001, deadline - time.monotonic()))
                msg = inbound.unpack(packet)
                now = time.monotonic()
                if now >= deadline:
                    raise ValueError("controller session expired")
                policy.accept(msg, now)
                if msg.get_type() == "HEARTBEAT":
                    deadline = now + self.timeout
                self.vehicle.send(vehicle_codec.pack(msg))
                self.forwarded += 1
        except (ValueError, mav.MAVError, asyncio.IncompleteReadError, TimeoutError, ConnectionError, ssl.SSLError) as exc:
            self.rejected += 1
            LOG.info("controller session closed: %s", type(exc).__name__)
        finally:
            self.vehicle.listeners.discard(queue)
            if claimed:
                self.active = False
            if telemetry:
                telemetry.cancel()
                await asyncio.gather(telemetry, return_exceptions=True)
            writer.close()
            with contextlib.suppress(ConnectionError, ssl.SSLError, TimeoutError):
                await asyncio.wait_for(writer.wait_closed(), 1)
            self.handlers.discard(task)

    async def close(self):
        tasks = list(self.handlers)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def serve(credentials, host="127.0.0.1", port=8443, vehicle_port=14580):
    loop = asyncio.get_running_loop()
    transport, vehicle = await loop.create_datagram_endpoint(
        lambda: VehicleUDP(("127.0.0.1", vehicle_port)), local_addr=("127.0.0.1", 14540))
    gateway = Gateway(credentials, vehicle)
    try:
        server = await asyncio.start_server(gateway.handle, host, port,
                  ssl=context(credentials, "companion", server=True), ssl_handshake_timeout=2)
        async with server:
            await server.serve_forever()
    finally:
        await gateway.close()
        transport.close()
