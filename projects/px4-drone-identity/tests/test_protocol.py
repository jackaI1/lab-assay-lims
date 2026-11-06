import secrets

import pytest
from pymavlink.dialects.v20 import common as mav

from drone_identity.identity import SoftwareKeyStore, provision, Authority
from drone_identity.protocol import Codec, Session, Rejected


class FlightRecorder:
    def __init__(self):
        self.commands = []
        self.pulses = 0
        self.failure = None

    def pulse(self):
        self.pulses += 1

    def fail(self, reason):
        self.failure = reason

    def command(self, message):
        self.commands.append(message.command)


@pytest.fixture
def rig(tmp_path):
    provision(tmp_path)
    key = secrets.token_bytes(32)
    backend = FlightRecorder()
    def session(role='pilot'):
        return Session(Authority(tmp_path), SoftwareKeyStore(tmp_path / role).certificate(), key, backend)
    return session, Codec(key), backend, tmp_path


def test_valid_signed_frame_is_forwarded_and_heartbeat_renews_lease(rig):
    new_session, codec, backend, _ = rig
    session = new_session()
    session.accept(codec.heartbeat())
    session.accept(codec.command(mav.MAV_CMD_COMPONENT_ARM_DISARM, 1))
    assert backend.commands == [400]
    assert backend.pulses == 1
    assert backend.failure is None


@pytest.mark.parametrize('attack', ['bad_signature', 'replay', 'unsigned', 'truncated', 'wrong_key', 'wrong_source'])
def test_invalid_frames_latch_failsafe_and_never_reach_px4(rig, attack):
    new_session, codec, backend, _ = rig
    session = new_session()
    packet = codec.command(400, 1)
    if attack == 'bad_signature':
        packet = packet[:-1] + bytes([packet[-1] ^ 1])
    elif attack == 'replay':
        session.accept(packet)
        backend.commands.clear()
    elif attack == 'unsigned':
        packet = bytes(mav.MAVLink_command_long_message(1, 1, 400, 0, 1, 0, 0, 0, 0, 0, 0).pack(mav.MAVLink(None, srcSystem=42, srcComponent=190)))
    elif attack == 'truncated':
        packet = packet[:-3]
    elif attack == 'wrong_key':
        packet = Codec(secrets.token_bytes(32)).command(400, 1)
    elif attack == 'wrong_source':
        codec.encoder.srcSystem = 77
        packet = codec.command(400, 1)
    with pytest.raises(Rejected):
        session.accept(packet)
    with pytest.raises(Rejected):
        session.accept(codec.heartbeat())
    assert backend.commands == []
    assert backend.failure == 3


@pytest.mark.parametrize('role,command,param,alt', [
    ('observer', 400, 1, 0), ('pilot', 31000, 1, 0), ('pilot', 246, 1, 0),
    ('pilot', 22, 0, 100), ('pilot', 400, 2, 0), ('pilot', 22, 0, float('nan')),
])
def test_role_and_parameter_allowlist_denies_unsafe_commands(rig, role, command, param, alt):
    new_session, codec, backend, _ = rig
    with pytest.raises(Rejected):
        new_session(role).accept(codec.command(command, param, altitude=alt))
    assert backend.commands == []
    assert backend.failure == 4


def test_observer_can_send_signed_liveness_but_cannot_control(rig):
    new_session, codec, backend, _ = rig
    new_session('observer').accept(codec.heartbeat())
    assert backend.pulses == 1
    assert backend.commands == []


def test_revoking_live_controller_stops_accepted_commands(rig):
    new_session, codec, backend, root = rig
    session = new_session()
    session.accept(codec.heartbeat())
    Authority(root).revoke(SoftwareKeyStore(root / 'pilot').certificate())
    with pytest.raises(Rejected, match='revoked'):
        session.accept(codec.command(400, 1))
    assert backend.commands == []
    assert backend.failure == 2


def test_old_session_packet_cannot_be_used_after_reconnect(rig):
    new_session, codec, backend, root = rig
    packet = codec.command(400, 1)
    other = Session(Authority(root), SoftwareKeyStore(root / 'pilot').certificate(), secrets.token_bytes(32), backend)
    with pytest.raises(Rejected):
        other.accept(packet)
    assert backend.commands == []


def test_backend_failsafe_refusal_closes_the_authenticated_session(rig):
    new_session, codec, backend, _ = rig
    session = new_session()
    def unavailable(_):
        raise RuntimeError('vehicle watchdog latched')
    backend.command = unavailable
    with pytest.raises(Rejected, match='latched'):
        session.accept(codec.command(400, 1))
    with pytest.raises(Rejected, match='latched closed'):
        session.accept(codec.heartbeat())
    assert backend.failure == 5
