import asyncio
import contextlib
import json
import os
import ssl
import struct

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import serialization

from drone_identity.controller import Controller
from drone_identity.gateway import Gateway, Policy
from drone_identity.identity import context, fingerprint, provision
from drone_identity.wire import Codec, command, heartbeat, mav, read_packet, setpoint, write_packet


@pytest.fixture
def identity(tmp_path):
    directory = tmp_path / "identity"
    provision(directory)
    return directory


class Vehicle:
    def __init__(self):
        self.listeners = set()
        self.sent = []

    def send(self, packet):
        self.sent.append(packet)


@contextlib.asynccontextmanager
async def gateway_server(identity, timeout=0.3):
    vehicle = Vehicle()
    gateway = Gateway(identity, vehicle, timeout)
    server = await asyncio.start_server(gateway.handle, "127.0.0.1", 0,
                                       ssl=context(identity, "companion", server=True))
    try:
        yield gateway, vehicle, server.sockets[0].getsockname()[1]
    finally:
        server.close()
        await server.wait_closed()
        await gateway.close()


def test_provisioning_is_private_and_cannot_overwrite(identity):
    assert os.stat(identity / "controller.key").st_mode & 0o777 == 0o600
    assert not (identity / "ca.key").exists()
    cert = x509.load_pem_x509_certificate((identity / "controller.pem").read_bytes())
    assert fingerprint(cert.public_bytes(serialization.Encoding.DER)) in json.loads(
        (identity / "controllers.json").read_text())
    with pytest.raises(FileExistsError):
        provision(identity)


def test_signed_wire_round_trip_and_replay_rejection():
    tx, rx = Codec(b"a" * 32), Codec(b"a" * 32)
    packet = tx.pack(heartbeat())
    assert packet[0] == 0xFD and packet[2] & 1
    assert rx.unpack(packet).get_signed()
    with pytest.raises(mav.MAVError):
        rx.unpack(packet)


@pytest.mark.parametrize("attack", ["wrong-key", "tamper", "unsigned", "v1", "truncated", "unknown"])
def test_reject_invalid_wire(attack):
    tx, rx = Codec(b"a" * 32), Codec(b"a" * 32)
    packet = bytearray(tx.pack(heartbeat()))
    if attack == "wrong-key":
        rx = Codec(b"b" * 32)
    elif attack == "tamper":
        packet[-1] ^= 1
    elif attack == "unsigned":
        tx.mav.signing.sign_outgoing = False
        packet = tx.pack(heartbeat())
    elif attack == "v1":
        packet[0] = 0xFE
    elif attack == "truncated":
        packet = packet[:-1]
    elif attack == "unknown":
        packet[7:10] = b"\xff\xff\xff"
    with pytest.raises((ValueError, mav.MAVError)):
        rx.unpack(packet)


def decoded(msg):
    return Codec(b"a" * 32).unpack(Codec(b"a" * 32).pack(msg))


def test_policy_requires_recent_heartbeat():
    policy = Policy()
    with pytest.raises(ValueError):
        policy.accept(decoded(setpoint()), 0)
    policy.accept(decoded(heartbeat()), 0)
    policy.accept(decoded(setpoint()), 0.1)
    with pytest.raises(ValueError):
        policy.accept(decoded(setpoint()), 0.75)


@pytest.mark.parametrize("attack", ["target", "source", "nan", "altitude", "frame", "mask", "force-arm", "shell", "heartbeat"])
def test_policy_rejects_unsafe_or_unexpected_commands(attack):
    msg = setpoint()
    if attack == "target": msg.target_system = 2
    if attack == "nan": msg.x = float("nan")
    if attack == "altitude": msg.z = -100
    if attack == "frame": msg.coordinate_frame = 8
    if attack == "mask": msg.type_mask = 0
    if attack == "force-arm": msg = command(mav.MAV_CMD_COMPONENT_ARM_DISARM, 1, 21196)
    if attack == "shell": msg = mav.MAVLink_serial_control_message(10, 0, 0, 0, 0, [0] * 70)
    if attack == "heartbeat":
        msg = heartbeat()
        msg.type = mav.MAV_TYPE_QUADROTOR
    policy = Policy()
    policy.accept(decoded(heartbeat()), 0)
    msg = decoded(msg)
    if attack == "source": msg._header.srcSystem = 42
    with pytest.raises(ValueError):
        policy.accept(msg, 0.1)


def test_mutual_tls_and_real_signed_forwarding(identity):
    async def run():
        async with gateway_server(identity) as (gateway, vehicle, port):
            client = await Controller().connect(identity, port)
            try:
                await client.send(heartbeat())
                await client.send(setpoint())
                await asyncio.sleep(0.05)
                assert gateway.forwarded == 2
                parser = mav.MAVLink(None)
                messages = [parser.decode(bytearray(p)) for p in vehicle.sent]
                assert [m.get_type() for m in messages] == ["HEARTBEAT", "SET_POSITION_TARGET_LOCAL_NED"]
                assert all(p[2] & 1 for p in vehicle.sent)
                # Simulated vehicle telemetry is signed by the companion on its way back.
                for queue in vehicle.listeners:
                    queue.put_nowait(mav.MAVLink_heartbeat_message(2, 12, 0, 0, 3, 3).pack(parser))
                await client.wait_for(lambda: "HEARTBEAT" in client.latest, 1)
                assert client.latest["HEARTBEAT"].get_signed()
            finally:
                await client.close()
    asyncio.run(run())


@pytest.mark.parametrize("role", ["unlisted", "no-cert", "foreign-ca", "wrong-usage"])
def test_failed_certificate_auth_sends_nothing(identity, tmp_path, role):
    async def run():
        async with gateway_server(identity) as (gateway, vehicle, port):
            ctx = context(identity, "unlisted")
            if role == "wrong-usage":
                ctx = context(identity, "companion")
            if role == "no-cert":
                ctx = ssl.create_default_context(cafile=str(identity / "ca.pem"))
            if role == "foreign-ca":
                other = tmp_path / "other"
                provision(other)
                ctx = context(other, "controller")
                ctx.load_verify_locations(identity / "ca.pem")
            writer = None
            try:
                with pytest.raises((ssl.SSLError, ConnectionError, asyncio.IncompleteReadError)):
                    reader, writer = await asyncio.open_connection("127.0.0.1", port, ssl=ctx, server_hostname="localhost")
                    await asyncio.wait_for(reader.readexactly(36), 1)
            finally:
                if writer:
                    writer.close()
                    with contextlib.suppress(ssl.SSLError, ConnectionError):
                        await writer.wait_closed()
            assert vehicle.sent == []
    asyncio.run(run())


@pytest.mark.parametrize("attack", ["unsigned", "wrong-key", "replay", "oversized", "stale-heartbeat", "second-controller"])
def test_session_failure_stops_forwarding(identity, attack):
    async def run():
        async with gateway_server(identity) as (gateway, vehicle, port):
            client = await Controller().connect(identity, port)
            try:
                packet = client.codec.pack(heartbeat())
                await write_packet(client.writer, packet)
                await asyncio.sleep(0.03)
                before = gateway.forwarded
                if attack == "second-controller":
                    with pytest.raises(asyncio.IncompleteReadError):
                        await Controller().connect(identity, port)
                    assert gateway.active
                elif attack == "oversized":
                    client.writer.write(struct.pack("!H", 65535))
                    await client.writer.drain()
                elif attack == "stale-heartbeat":
                    for _ in range(5):
                        with contextlib.suppress(ConnectionError):
                            await client.send(setpoint())
                        await asyncio.sleep(0.1)
                else:
                    if attack == "unsigned":
                        client.codec.mav.signing.sign_outgoing = False
                        packet = client.codec.pack(setpoint())
                    elif attack == "wrong-key": packet = Codec(b"z" * 32).pack(setpoint())
                    await write_packet(client.writer, packet)
                if attack != "second-controller":
                    await asyncio.sleep(0.08)
                    assert not gateway.active
                    if attack != "stale-heartbeat": assert gateway.forwarded == before
                    stopped = gateway.forwarded
                    await asyncio.sleep(0.1)
                    assert gateway.forwarded == stopped
            finally:
                await client.close()
    asyncio.run(run())


def test_new_session_has_new_key_and_old_packets_fail(identity):
    async def run():
        async with gateway_server(identity) as (gateway, vehicle, port):
            first = await Controller().connect(identity, port)
            packet = first.codec.pack(heartbeat())
            await first.close()
            await asyncio.sleep(0.05)
            second = await Controller().connect(identity, port)
            try:
                assert second.codec.mav.signing.secret_key != first.codec.mav.signing.secret_key
                await write_packet(second.writer, packet)
                await asyncio.sleep(0.05)
                assert gateway.forwarded == 0
            finally:
                await second.close()
    asyncio.run(run())


def test_server_hostname_is_checked(identity):
    async def run():
        async with gateway_server(identity) as (gateway, vehicle, port):
            with pytest.raises(ssl.SSLCertVerificationError):
                await asyncio.open_connection("127.0.0.1", port, ssl=context(identity, "controller"),
                                              server_hostname="different-companion.invalid")
            assert vehicle.sent == []
    asyncio.run(run())


def test_expired_certificates_are_rejected(tmp_path, monkeypatch):
    from datetime import datetime, timedelta, timezone
    import drone_identity.identity as identity_module
    class Past(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.now(timezone.utc) - timedelta(days=10)
    monkeypatch.setattr(identity_module, "datetime", Past)
    directory = tmp_path / "expired"
    provision(directory)
    async def run():
        async with gateway_server(directory) as (gateway, vehicle, port):
            with pytest.raises(ssl.SSLCertVerificationError):
                await asyncio.open_connection("127.0.0.1", port, ssl=context(directory, "controller"),
                                              server_hostname="localhost")
            assert vehicle.sent == []
    asyncio.run(run())


def test_late_heartbeat_cannot_resurrect_session():
    policy = Policy()
    policy.accept(decoded(heartbeat()), 0)
    with pytest.raises(ValueError):
        policy.accept(decoded(heartbeat()), 0.75)


def test_telemetry_error_does_not_strand_session(identity, monkeypatch):
    original = Codec.pack
    def broken_telemetry(codec, msg):
        if codec.mav.srcSystem == 1:
            raise ValueError("injected telemetry encoder failure")
        return original(codec, msg)
    monkeypatch.setattr(Codec, "pack", broken_telemetry)
    async def run():
        async with gateway_server(identity) as (gateway, vehicle, port):
            client = await Controller().connect(identity, port)
            try:
                raw = heartbeat().pack(mav.MAVLink(None))
                for queue in vehicle.listeners:
                    queue.put_nowait(raw)
                await asyncio.sleep(0.4)
                assert not gateway.active
                assert not gateway.handlers
            finally:
                await client.close()
    asyncio.run(run())


def test_unknown_vehicle_dialect_does_not_break_telemetry(identity):
    async def run():
        async with gateway_server(identity) as (gateway, vehicle, port):
            client = await Controller().connect(identity, port)
            try:
                raw = bytearray(heartbeat().pack(mav.MAVLink(None)))
                raw[7:10] = b"\xff\xff\xff"  # message absent from the common dialect
                for queue in vehicle.listeners:
                    queue.put_nowait(raw)
                    queue.put_nowait(heartbeat().pack(mav.MAVLink(None)))
                await client.wait_for(lambda: "HEARTBEAT" in client.latest, 1)
            finally:
                await client.close()
    asyncio.run(run())
