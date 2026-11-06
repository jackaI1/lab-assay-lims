import socket
import time

import pytest
from pymavlink.dialects.v20 import common as mav

from drone_identity.px4 import Px4Link


def test_real_udp_telemetry_drives_status_and_private_command_output():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as autopilot:
        autopilot.bind(('127.0.0.1', 0))
        autopilot.settimeout(2)
        with Px4Link(local=('127.0.0.1', 0), remote=autopilot.getsockname()) as link:
            encoder = mav.MAVLink(None, srcSystem=1, srcComponent=1)
            heartbeat = mav.MAVLink_heartbeat_message(2, 12, 128, (4 << 16) | (6 << 24), 4, 3)
            autopilot.sendto(bytes(heartbeat.pack(encoder)), link.address)
            autopilot.sendto(bytes(mav.MAVLink_local_position_ned_message(1, 0, 0, -2.0, 0, 0, 0).pack(encoder)), link.address)
            autopilot.sendto(bytes(mav.MAVLink_named_value_float_message(1, b'id_guard', 23).pack(encoder)), link.address)
            link.wait(lambda s: s['guard'] == 23 and s['altitude_m'] == 2.0, 2, 'telemetry')
            assert link.snapshot()['armed'] is True
            assert link.snapshot()['mode'] == 'AUTO_LAND'
            assert link.snapshot()['flight_fresh'] is False  # no landing-state stream received
            with pytest.raises(RuntimeError, match='armed'):
                link.begin()
            link.fail(3)
            parser = mav.MAVLink(None)
            deadline = time.monotonic() + 2
            received = None
            while time.monotonic() < deadline:
                packet, _ = autopilot.recvfrom(4096)
                for msg in parser.parse_buffer(packet) or []:
                    if msg.get_type() == 'COMMAND_LONG':
                        received = msg
                        break
                if received:
                    break
            assert received.command == 31000
            assert received.param1 == 2
            assert received.param2 == 3
            assert received.get_srcSystem() == 42
            assert received.get_srcComponent() == 191
        assert not link.thread.is_alive()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.bind(link.address)


def test_wait_fails_with_observed_telemetry_instead_of_silently_passing():
    with Px4Link(local=('127.0.0.1', 0), remote=('127.0.0.1', 9)) as link:
        with pytest.raises(TimeoutError, match='no simulated heartbeat'):
            link.wait(lambda s: s['armed'] is True, 0.05, 'no simulated heartbeat')


def test_takeoff_adapter_keeps_current_position_and_converts_relative_height():
    import math
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as autopilot:
        autopilot.bind(('127.0.0.1', 0))
        autopilot.settimeout(2)
        with Px4Link(local=('127.0.0.1', 0), remote=autopilot.getsockname()) as link:
            encoder = mav.MAVLink(None, srcSystem=1, srcComponent=1)
            autopilot.sendto(bytes(mav.MAVLink_heartbeat_message(2, 12, 128, 0, 4, 3).pack(encoder)), link.address)
            autopilot.sendto(bytes(mav.MAVLink_named_value_float_message(1, b'id_guard', 10).pack(encoder)), link.address)
            position = mav.MAVLink_global_position_int_message(1, 473977420, 85455940, 488000, 0, 0, 0, 0, 0)
            autopilot.sendto(bytes(position.pack(encoder)), link.address)
            link.wait(lambda s: s.get('altitude_amsl_m') == 488, 2, 'global altitude')
            link.pulse()
            link.command(mav.MAVLink_command_long_message(1, 1, 22, 0, 0, 0, 0, 0, 0, 0, 2))
            parser = mav.MAVLink(None)
            while True:
                packet, _ = autopilot.recvfrom(4096)
                commands = [m for m in parser.parse_buffer(packet) or [] if m.get_type() == 'COMMAND_LONG' and m.command == 22]
                if commands:
                    takeoff = commands[0]
                    break
            assert takeoff.param7 == 490
            assert math.isnan(takeoff.param5) and math.isnan(takeoff.param6)


def test_rejection_latches_private_adapter_before_telemetry_catches_up():
    with Px4Link(local=('127.0.0.1', 0), remote=('127.0.0.1', 9)) as link:
        link.fail(2)
        with pytest.raises(RuntimeError, match='latched'):
            link.pulse()
        with pytest.raises(RuntimeError, match='latched'):
            link.command(mav.MAVLink_command_long_message(1, 1, 400, 0, 1, 0, 0, 0, 0, 0, 0))
        assert link.snapshot()['forwarded_commands'] == 0


def test_resumed_heartbeat_cannot_renew_expired_local_lease():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as autopilot:
        autopilot.bind(('127.0.0.1', 0))
        with Px4Link(local=('127.0.0.1', 0), remote=autopilot.getsockname()) as link:
            encoder = mav.MAVLink(None, srcSystem=1, srcComponent=1)
            autopilot.sendto(bytes(mav.MAVLink_heartbeat_message(2, 12, 128, 0, 4, 3).pack(encoder)), link.address)
            autopilot.sendto(bytes(mav.MAVLink_named_value_float_message(1, b'id_guard', 10).pack(encoder)), link.address)
            link.wait(lambda s: s['guard'] == 10 and s['fresh'], 2, 'active telemetry')
            link.pulse()
            time.sleep(2.05)
            with pytest.raises(RuntimeError, match='lease'):
                link.pulse()
            assert link.snapshot()['forwarded_commands'] == 0
