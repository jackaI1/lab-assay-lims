"""Private loopback MAVLink transport and observed PX4 flight state."""
from __future__ import annotations

import math
import socket
import threading
import time
from collections import deque

from pymavlink.dialects.v20 import common as mav


class _Writer:
    def __init__(self, sock, remote):
        self.sock, self.remote = sock, remote

    def write(self, data):
        return self.sock.sendto(data, self.remote)


class Px4Link:
    def __init__(self, local=('127.0.0.1', 14540), remote=('127.0.0.1', 14580)):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(local)
        self.socket.settimeout(0.1)
        self.address = self.socket.getsockname()
        self.remote = remote
        self.encoder = mav.MAVLink(_Writer(self.socket, remote), srcSystem=42, srcComponent=191)
        self.decoder = mav.MAVLink(None)
        self.lock = threading.RLock()
        self.operation_lock = threading.RLock()
        self.tx_lock = threading.Lock()
        self.stop = threading.Event()
        self.state = {'armed': None, 'altitude_m': None, 'landed': None, 'mode': None,
                      'guard': None, 'forwarded_commands': 0, 'altitude_amsl_m': None}
        self.times = {}
        self.latched = False
        self.last_pulse_time = 0
        self.messages = deque(maxlen=8)
        self.thread = threading.Thread(target=self._receive, name='px4-telemetry')

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stop.set()
        self.thread.join(timeout=2)
        self.socket.close()
        if self.thread.is_alive():
            raise RuntimeError('PX4 receiver failed to stop')

    def snapshot(self) -> dict:
        with self.lock:
            return {**self.state, 'fresh': time.monotonic() - self.times.get('heartbeat', 0) < 2,
                    'flight_fresh': all(time.monotonic() - self.times.get(k, 0) < 2
                                        for k in ('heartbeat', 'position', 'landed', 'guard')),
                    'stream_age_s': {k: round(time.monotonic() - v, 3) for k, v in self.times.items()},
                    'recent_status': list(self.messages)}

    def wait(self, predicate, timeout: float, description: str) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            snapshot = self.snapshot()
            if predicate(snapshot):
                return snapshot
            self.stop.wait(0.05)
        raise TimeoutError(f'{description}: {self.snapshot()}')

    def _send(self, message):
        with self.tx_lock:
            self.encoder.send(message)

    def _control(self, signal: int, reason: int = 0):
        self._send(mav.MAVLink_command_long_message(1, 1, 31000, 0, signal, reason, 0, 0, 0, 0, 0))

    def begin(self):
        with self.operation_lock:
            self._begin()

    def _begin(self):
        state = self.snapshot()
        if not state['fresh'] or state['armed'] is not False:
            raise RuntimeError('cannot start an identity session while armed or telemetry is stale')
        sent = time.monotonic()
        self._control(3)
        self.wait(lambda s: s['guard'] == 0 and self.times.get('guard', 0) > sent, 3, 'guard reset')
        with self.lock:
            self.latched = False
            self.last_pulse_time = 0
        self.pulse()
        self.wait(lambda s: s['guard'] == 10, 3, 'authenticated guard')

    def pulse(self):
        with self.operation_lock:
            self._pulse()

    def _pulse(self):
        with self.lock:
            if self.latched:
                raise RuntimeError('vehicle watchdog is latched closed')
            if self.last_pulse_time and time.monotonic() - self.last_pulse_time > 2:
                self.fail(1)
                raise RuntimeError('authenticated heartbeat lease expired')
            if time.monotonic() - self.times.get('heartbeat', 0) >= 2:
                raise RuntimeError('vehicle telemetry is stale')
        self._control(1)
        self.last_pulse_time = time.monotonic()

    def fail(self, reason: int):
        with self.operation_lock:
            with self.lock:
                self.latched = True
            self._control(2, reason)

    def command(self, message):
        with self.operation_lock:
            self._command(message)

    def _command(self, message):
        with self.lock:
            if self.latched:
                raise RuntimeError('vehicle watchdog is latched closed')
            if not self.last_pulse_time or time.monotonic() - self.last_pulse_time > 2:
                self.fail(1)
                raise RuntimeError('authenticated heartbeat lease expired')
            if (self.state['guard'] != 10 or time.monotonic() - self.times.get('guard', 0) >= 1
                    or time.monotonic() - self.times.get('heartbeat', 0) >= 2):
                raise RuntimeError('vehicle has no fresh authenticated watchdog state')
        if message.command == mav.MAV_CMD_NAV_TAKEOFF:
            with self.lock:
                altitude = self.state['altitude_amsl_m']
                fresh = time.monotonic() - self.times.get('global', 0) < 2
            if altitude is None or not fresh:
                raise RuntimeError('takeoff needs fresh global altitude')
            # The lab's signed takeoff request is bounded to 1-5 metres above
            # the current location. PX4 expects absolute sea-level altitude.
            message = mav.MAVLink_command_long_message(1, 1, 22, 0, 0, 0, 0,
                                                       math.nan, math.nan, math.nan, altitude + message.param7)
        elif message.command == mav.MAV_CMD_NAV_LAND:
            message = mav.MAVLink_command_long_message(1, 1, 21, 0, 0, 0, 0,
                                                       math.nan, math.nan, math.nan, math.nan)
        self._send(message)
        with self.lock:
            self.state['forwarded_commands'] += 1

    def _receive(self):
        last_gcs = 0
        while not self.stop.is_set():
            now = time.monotonic()
            if now - last_gcs > 0.5:
                self._send(mav.MAVLink_heartbeat_message(mav.MAV_TYPE_GCS, mav.MAV_AUTOPILOT_INVALID,
                           0, 0, mav.MAV_STATE_ACTIVE, 3))
                last_gcs = now
            try:
                packet, source = self.socket.recvfrom(4096)
                if source != self.remote:
                    continue
                messages = self.decoder.parse_buffer(packet) or []
            except socket.timeout:
                continue
            except (OSError, mav.MAVError):
                continue
            for msg in messages:
                if msg.get_srcSystem() != 1 or msg.get_srcComponent() != 1:
                    continue
                with self.lock:
                    kind = msg.get_type()
                    if kind == 'HEARTBEAT':
                        self.state['armed'] = bool(msg.base_mode & mav.MAV_MODE_FLAG_SAFETY_ARMED)
                        main, sub = (msg.custom_mode >> 16) & 0xFF, (msg.custom_mode >> 24) & 0xFF
                        self.state['mode'] = 'AUTO_LAND' if (main, sub) == (4, 6) else f'{main}:{sub}'
                        self.times['heartbeat'] = now
                    elif kind == 'LOCAL_POSITION_NED':
                        self.state['altitude_m'] = round(-msg.z, 3)
                        self.times['position'] = now
                    elif kind == 'GLOBAL_POSITION_INT':
                        self.state['altitude_amsl_m'] = msg.alt / 1000
                        self.times['global'] = now
                    elif kind == 'EXTENDED_SYS_STATE':
                        self.state['landed'] = msg.landed_state == mav.MAV_LANDED_STATE_ON_GROUND
                        self.times['landed'] = now
                    elif kind == 'NAMED_VALUE_FLOAT' and msg.name == 'id_guard':
                        self.state['guard'] = round(msg.value)
                        if self.state['guard'] >= 20:
                            self.latched = True
                        self.times['guard'] = now
                    elif kind == 'COMMAND_ACK' and msg.command != 31000:
                        self.messages.append(f'command {msg.command}: result {msg.result}')
                    elif kind == 'STATUSTEXT':
                        self.messages.append(msg.text[:160])
