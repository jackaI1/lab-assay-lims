"""End-to-end experiments. These require real PX4 and Gazebo, never a fake flight."""
from __future__ import annotations

import json
import ssl
import tempfile
import time
from pathlib import Path

from pymavlink.dialects.v20 import common as mav

from .identity import Authority, SoftwareKeyStore, provision
from .px4 import Px4Link
from .simulator import Simulator, verify_loopback_listener
from .transport import Client, Gateway

SCENARIOS = ('healthy', 'lost_link', 'expired_certificate', 'revoked_certificate',
             'bad_signature', 'replayed_frame', 'unsigned_frame', 'observer_denied')


def _takeoff(link: Px4Link, client: Client) -> dict:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        reply = client.command(mav.MAV_CMD_COMPONENT_ARM_DISARM, 1)
        assert reply.get('accepted') == 'command', reply
        try:
            link.wait(lambda s: s['fresh'] and s['armed'] is True, 1.5, 'arm after estimator is ready')
            break
        except TimeoutError:
            continue
    else:
        raise TimeoutError(f'PX4 refused to arm: {link.snapshot()}')
    assert client.command(mav.MAV_CMD_NAV_TAKEOFF, altitude=2).get('accepted') == 'command'
    return link.wait(lambda s: s['flight_fresh'] and s['armed'] is True and s['landed'] is False
                     and s['altitude_m'] is not None and s['altitude_m'] > 1.0,
                     30, 'observed airborne vehicle above one metre')


def _landed(link: Px4Link) -> dict:
    return link.wait(lambda s: s['flight_fresh'] and s['landed'] is True and s['armed'] is False
                     and s['altitude_m'] is not None and abs(s['altitude_m']) < 0.3,
                     40, 'observed ground contact, near-zero altitude and automatic disarm')


def _attack(name: str, client: Client, root: Path, gateway: Gateway) -> int:
    if name == 'lost_link':
        # Leave TLS open but send no traffic. The PX4 watchdog, rather than a
        # socket disconnect callback, must detect this.
        return 21
    if name == 'expired_certificate':
        try:
            with Client(root, 'expired', gateway.address) as expired:
                expired.heartbeat()
        except (ssl.SSLError, OSError, EOFError):
            pass
        else:
            raise AssertionError('expired controller was authenticated')
        assert gateway.rejected.wait(3), 'gateway did not log the expired certificate'
        return 22
    if name == 'revoked_certificate':
        Authority(root).revoke(SoftwareKeyStore(root / 'pilot').certificate())
        reply = client.heartbeat()
        assert 'revoked' in reply.get('rejected', ''), reply
        return 22
    if name == 'bad_signature':
        packet = client.codec.command(400, 1)
        packet = packet[:-1] + bytes([packet[-1] ^ 1])
    elif name == 'replayed_frame':
        packet = client.codec.heartbeat()
        assert client.exchange(packet).get('accepted') == 'heartbeat'
    elif name == 'unsigned_frame':
        packet = bytes(mav.MAVLink_command_long_message(1, 1, 400, 0, 1, 0, 0, 0, 0, 0, 0).pack(mav.MAVLink(None, srcSystem=42, srcComponent=190)))
    else:
        raise ValueError(name)
    assert 'rejected' in client.exchange(packet), 'invalid frame was accepted'
    return 23


def run_scenario(name: str, link: Px4Link, output: Path) -> dict:
    started = time.monotonic()
    record = {'scenario': name, 'status': 'FAIL'}
    with tempfile.TemporaryDirectory(prefix='simulation-identities-') as directory:
        root = Path(directory)
        provision(root)
        with Gateway(root, link, audit=output / 'audit.jsonl') as gateway:
            role = 'observer' if name == 'observer_denied' else 'pilot'
            with Client(root, role, gateway.address) as client:
                if name == 'observer_denied':
                    assert client.heartbeat().get('accepted') == 'heartbeat'
                    before = link.snapshot()['forwarded_commands']
                    assert 'denied' in client.command(400, 1).get('rejected', '')
                    result = link.wait(lambda s: s['guard'] == 24, 5, 'observer policy failsafe')
                    assert result['armed'] is False
                    assert result['forwarded_commands'] == before
                    record.update(after=result, expected_guard=24)
                else:
                    with client.keepalive() as errors:
                        record['airborne'] = _takeoff(link, client)
                        if name == 'healthy':
                            assert client.command(21).get('accepted') == 'command'
                            link.wait(lambda s: s['mode'] == 'AUTO_LAND', 8, 'commanded landing')
                            record['after'] = _landed(link)
                            assert record['after']['guard'] == 10, 'healthy link falsely failed'
                            assert not errors, errors
                        elif name == 'expired_certificate':
                            trigger = time.monotonic()
                            expected = _attack(name, client, root, gateway)
                            record.update(_assert_failsafe(link, trigger, expected,
                                                         record['airborne']['forwarded_commands'], client))
                    if name not in ('healthy', 'expired_certificate'):
                        trigger = time.monotonic()
                        before = link.snapshot()['forwarded_commands']
                        expected = _attack(name, client, root, gateway)
                        record.update(_assert_failsafe(link, trigger, expected, before, client))
        record.update(status='PASS', elapsed_s=round(time.monotonic() - started, 3))
    return record


def _assert_failsafe(link, trigger, expected, forwarded_before, client):
    failure = link.wait(lambda s: s['guard'] == expected, 8, f'PX4 uORB failsafe {expected}')
    elapsed = time.monotonic() - trigger
    assert elapsed < 6, f'failsafe took {elapsed:.3f} seconds'
    assert failure['forwarded_commands'] == forwarded_before, 'rejected traffic reached PX4'
    try:
        resumed = client.command(400, 1)
        assert 'rejected' in resumed, 'old authenticated session resumed after failsafe'
    except (OSError, EOFError):
        pass  # A previously rejected session may already be closed.
    assert link.snapshot()['forwarded_commands'] == forwarded_before
    landing = link.wait(lambda s: s['flight_fresh'] and s['mode'] == 'AUTO_LAND' and s['armed'] is True,
                        8, 'PX4 actually entered landing mode while airborne')
    after = _landed(link)
    assert after['guard'] == expected, 'failsafe did not stay latched'
    return {'expected_guard': expected, 'failsafe_s': round(elapsed, 3),
            'resumed_traffic_denied': True, 'landing': landing, 'after': after}


def experiments(output: Path, scenarios=SCENARIOS):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    results = output / 'experiments.jsonl'
    if results.exists():
        raise FileExistsError('use a fresh output directory to preserve earlier experiments')
    with Simulator(output) as simulator, Px4Link() as link:
        def ready(state):
            if simulator.process.poll() is not None:
                raise RuntimeError('simulator exited during startup; inspect px4.log')
            return state['fresh'] and state['guard'] is not None and state['landed'] is True
        link.wait(ready, 120, 'Gazebo/PX4 startup with identity module telemetry')
        listener = verify_loopback_listener(14580)
        (output / 'network.json').write_text(json.dumps({'px4_listener': listener}) + '\n')
        for name in scenarios:
            try:
                record = run_scenario(name, link, output)
            except BaseException as exc:
                record = {'scenario': name, 'status': 'FAIL', 'error': str(exc), 'observed': link.snapshot()}
                with results.open('a') as stream:
                    stream.write(json.dumps(record) + '\n')
                print(json.dumps(record), flush=True)
                raise
            with results.open('a') as stream:
                stream.write(json.dumps(record) + '\n')
            print(json.dumps({'scenario': name, 'status': record['status'],
                              'failsafe_s': record.get('failsafe_s'), 'elapsed_s': record['elapsed_s']}), flush=True)
