import ssl
import threading

import pytest

from drone_identity.identity import Authority, SoftwareKeyStore, provision
from drone_identity.transport import Client, Gateway


class GroundVehicle:
    def __init__(self):
        self.reason = 0
        self.commands = []

    def begin(self):
        self.reason = 0

    def pulse(self):
        pass

    def fail(self, reason):
        self.reason = reason

    def command(self, msg):
        self.commands.append(msg.command)

    def snapshot(self):
        return {'armed': False, 'reason': self.reason}


@pytest.fixture
def endpoint(tmp_path):
    provision(tmp_path)
    vehicle = GroundVehicle()
    with Gateway(tmp_path, vehicle) as gateway:
        yield tmp_path, vehicle, gateway
    assert not gateway.thread.is_alive()
    assert all(not thread.is_alive() for thread in gateway.workers)


def test_real_mutual_tls_exchanges_signed_frames_and_cleans_threads(endpoint):
    root, vehicle, gateway = endpoint
    with Client(root, 'pilot', gateway.address) as client:
        assert client.heartbeat()['accepted'] == 'heartbeat'
        assert client.command(400, 1)['accepted'] == 'command'
    assert gateway.rejected.wait(2)
    assert vehicle.commands == [400]
    assert vehicle.reason == 5


def test_expired_certificate_fails_real_tls_and_requests_failsafe(endpoint):
    root, vehicle, gateway = endpoint
    with pytest.raises((ssl.SSLError, ConnectionError, EOFError)):
        with Client(root, 'expired', gateway.address) as client:
            client.heartbeat()
    assert gateway.rejected.wait(2)
    assert vehicle.reason == 2


def test_revoked_client_cannot_get_a_session_key(endpoint):
    root, vehicle, gateway = endpoint
    Authority(root).revoke(SoftwareKeyStore(root / 'pilot').certificate())
    with pytest.raises((ConnectionError, EOFError)):
        with Client(root, 'pilot', gateway.address):
            pass
    assert gateway.rejected.wait(2)
    assert vehicle.reason == 2


def test_observer_command_denied_over_real_tls(endpoint):
    root, vehicle, gateway = endpoint
    with Client(root, 'observer', gateway.address) as client:
        assert client.heartbeat()['accepted'] == 'heartbeat'
        assert 'denied' in client.command(400, 1)['rejected']
    assert vehicle.reason == 4
    assert vehicle.commands == []


def test_client_rejects_vehicle_from_another_ca(endpoint, tmp_path):
    root, _, gateway = endpoint
    other = tmp_path / 'other'
    provision(other)
    with pytest.raises(ssl.SSLCertVerificationError):
        with Client(other, 'pilot', gateway.address):
            pass


def test_slow_partial_tls_peer_does_not_leak_a_worker(endpoint):
    import socket
    _, _, gateway = endpoint
    with socket.create_connection(gateway.address) as peer:
        peer.sendall(b'\x16')
    assert gateway.rejected.wait(2)
    assert threading.active_count() < 30


def test_parallel_controller_calls_keep_signing_timestamps_in_send_order(endpoint):
    from concurrent.futures import ThreadPoolExecutor
    root, _, gateway = endpoint
    with Client(root, 'pilot', gateway.address) as client:
        with ThreadPoolExecutor(max_workers=4) as pool:
            replies = list(pool.map(lambda _: client.heartbeat(), range(24)))
        assert all(reply.get('accepted') == 'heartbeat' for reply in replies)


@pytest.mark.parametrize('length', [0, 281, 65535])
def test_invalid_framing_is_logged_as_a_frame_failure(endpoint, length):
    import json
    import struct
    from drone_identity.transport import read_frame
    root, vehicle, gateway = endpoint
    with Client(root, 'pilot', gateway.address) as client:
        client.socket.sendall(struct.pack('!H', length))
        assert 'rejected' in json.loads(read_frame(client.socket))
    assert vehicle.reason == 3
    assert vehicle.commands == []
