"""These tests observe the real PX4/Gazebo process, never a simulated autopilot stub."""
import asyncio
import contextlib
import json
import os
import time

import pytest

from drone_identity.controller import Controller, fly, is_offboard
from drone_identity.gateway import Gateway, VehicleUDP
from drone_identity.identity import context, provision
from drone_identity.wire import Codec, mav, write_packet

pytestmark = [pytest.mark.sitl, pytest.mark.skipif(os.getenv("RUN_SITL") != "1", reason="start PX4 Gazebo via scripts/sitl_check.py")]


@pytest.mark.parametrize("failure", ["link-loss", "bad-signature"])
def test_real_gazebo_authenticated_flight_and_failsafe(tmp_path, failure):
    async def run():
        credentials = tmp_path / "identity"
        provision(credentials)
        loop = asyncio.get_running_loop()
        transport, vehicle = await loop.create_datagram_endpoint(
            lambda: VehicleUDP(("127.0.0.1", 14580)), local_addr=("127.0.0.1", 14540))
        gateway = Gateway(credentials, vehicle)
        observer = asyncio.Queue(maxsize=512)
        vehicle.listeners.add(observer)
        server = await asyncio.start_server(gateway.handle, "127.0.0.1", 0,
                                           ssl=context(credentials, "companion", server=True))
        port = server.sockets[0].getsockname()[1]
        client = None
        stream = None
        try:
            # A valid CA-issued certificate without explicit permission gets no session key.
            with pytest.raises(asyncio.IncompleteReadError):
                await Controller().connect(credentials, port, "unlisted")
            assert gateway.forwarded == 0
            client = await Controller().connect(credentials, port)
            stream = asyncio.create_task(client.stream())
            await fly(client)
            assert is_offboard(client)
            assert client.latest["HEARTBEAT"].base_mode & mav.MAV_MODE_FLAG_SAFETY_ARMED
            altitude = -client.latest["LOCAL_POSITION_NED"].z
            before = gateway.forwarded
            with pytest.raises(asyncio.IncompleteReadError):
                await Controller().connect(credentials, port, "unlisted")
            assert gateway.active
            # Stop new valid traffic, then inject the selected failure.
            stream.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await stream
            while not observer.empty():
                observer.get_nowait()
            start = time.monotonic()
            if failure == "bad-signature":
                from drone_identity.wire import setpoint
                await write_packet(client.writer, Codec(b"wrong-key-for-controller-link!!!!"[:32]).pack(setpoint()))
            async with asyncio.timeout(3):
                while gateway.active:
                    await asyncio.sleep(0.02)
            stopped_count = gateway.forwarded
            parser = mav.MAVLink(None)
            landed_mode = False
            disarmed = False
            loss_to_land = None
            async with asyncio.timeout(45):
                while not (landed_mode and disarmed):
                    for msg in parser.parse_buffer(await observer.get()) or []:
                        if msg.get_type() != "HEARTBEAT":
                            continue
                        main = (msg.custom_mode >> 16) & 255
                        sub = (msg.custom_mode >> 24) & 255
                        if (main, sub) == (4, 6) and not landed_mode:
                            landed_mode = True
                            loss_to_land = round(time.monotonic() - start, 3)
                        if landed_mode and not (msg.base_mode & mav.MAV_MODE_FLAG_SAFETY_ARMED):
                            disarmed = True
            assert gateway.forwarded == stopped_count, "gateway forwarded traffic after revoking control"
            assert loss_to_land < 10, "PX4 took too long to enter configured Land failsafe"
            result = {"failure": failure, "authenticated_offboard_flight": True,
                      "altitude_metres": round(altitude, 3), "forwarded_before_loss": before,
                      "land_mode_after_seconds": loss_to_land, "landed_and_disarmed": disarmed,
                      "unlisted_certificate_rejected": True}
            artifact_dir = os.getenv("SITL_ARTIFACTS")
            if artifact_dir:
                from pathlib import Path
                Path(artifact_dir, f"{failure}.json").write_text(json.dumps(result, indent=2) + "\n")
            print(json.dumps(result))
        finally:
            if stream:
                stream.cancel()
                with contextlib.suppress(asyncio.CancelledError, ConnectionError):
                    await stream
            if client:
                await client.close()
            server.close()
            await server.wait_closed()
            await gateway.close()
            vehicle.listeners.discard(observer)
            transport.close()
            await asyncio.sleep(0)
    asyncio.run(run())
