"""Strict one-frame MAVLink 2 signing and per-certificate command policy."""
from __future__ import annotations

import math
import time
from typing import Protocol

from pymavlink.dialects.v20 import common as mav

from .identity import Authority, IdentityError


class Vehicle(Protocol):
    def pulse(self) -> None: ...
    def fail(self, reason: int) -> None: ...
    def command(self, message: mav.MAVLink_command_long_message) -> None: ...


class Rejected(ValueError):
    pass


def _mavlink(key: bytes) -> mav.MAVLink:
    if len(key) != 32:
        raise ValueError('MAVLink signing requires a 32-byte key')
    link = mav.MAVLink(None, srcSystem=42, srcComponent=190)
    link.signing.secret_key = key
    link.signing.sign_outgoing = True
    link.signing.link_id = 1
    # MAVLink timestamps count 10-microsecond ticks since 2015-01-01.
    link.signing.timestamp = int((time.time() - 1420070400) * 100_000)
    return link


class Codec:
    def __init__(self, key: bytes):
        self.encoder = _mavlink(key)

    def pack(self, message: mav.MAVLink_message) -> bytes:
        packet = bytes(message.pack(self.encoder))
        self.encoder.seq = (self.encoder.seq + 1) % 256
        return packet

    def heartbeat(self) -> bytes:
        return self.pack(mav.MAVLink_heartbeat_message(mav.MAV_TYPE_GCS, mav.MAV_AUTOPILOT_INVALID,
                         0, 0, mav.MAV_STATE_ACTIVE, 3))

    def command(self, command: int, param1: float = 0, *, altitude: float = 0) -> bytes:
        return self.pack(mav.MAVLink_command_long_message(1, 1, command, 0, param1, 0, 0, 0, 0, 0, altitude))


class Session:
    def __init__(self, authority: Authority, certificate: bytes, key: bytes, vehicle: Vehicle):
        self.authority, self.certificate, self.vehicle = authority, certificate, vehicle
        self.role = authority.validate(certificate, 'client')
        self.decoder = _mavlink(key)
        self.failed = False

    def _reject(self, reason: int, detail: str):
        self.failed = True
        self.vehicle.fail(reason)
        raise Rejected(detail)

    def accept(self, packet: bytes) -> str:
        if self.failed:
            raise Rejected('session is latched closed')
        try:
            self.authority.validate(self.certificate, 'client')
        except (IdentityError, ValueError) as exc:
            self._reject(2, str(exc))
        try:
            # Reject unknown messages before pymavlink's unknown-message shortcut.
            # One TLS record payload must contain exactly one signed MAVLink frame.
            if (len(packet) < 25 or len(packet) > 280 or packet[0] != 0xFD
                    or packet[2] != 1 or packet[5:7] != bytes([42, 190])
                    or packet[-13] != 1 or int.from_bytes(packet[7:10], 'little') not in (0, 76)):
                raise ValueError('requires a signed MAVLink 2 controller frame')
            message = self.decoder.decode(bytearray(packet))
            if not message.get_signed():
                raise ValueError('unsigned message')
        except (ValueError, mav.MAVError, IndexError) as exc:
            self._reject(3, f'bad signature, replay or malformed frame: {exc}')
        if message.get_type() == 'HEARTBEAT':
            try:
                self.vehicle.pulse()
            except RuntimeError as exc:
                self._reject(5, str(exc))
            return 'heartbeat'
        if not self._allowed(message):
            self._reject(4, 'role, command, target or parameters denied')
        try:
            self.vehicle.command(message)
        except RuntimeError as exc:
            self._reject(5, str(exc))
        return 'command'

    def _allowed(self, msg: mav.MAVLink_command_long_message) -> bool:
        if self.role != 'pilot' or (msg.target_system, msg.target_component) != (1, 1):
            return False
        params = [msg.param1, msg.param2, msg.param3, msg.param4, msg.param5, msg.param6, msg.param7]
        if not all(math.isfinite(v) for v in params) or msg.confirmation != 0:
            return False
        if msg.command == mav.MAV_CMD_COMPONENT_ARM_DISARM:
            return msg.param1 in (0, 1) and all(v == 0 for v in params[1:])
        if msg.command == mav.MAV_CMD_NAV_TAKEOFF:
            return all(v == 0 for v in params[:6]) and 1 <= msg.param7 <= 5
        if msg.command == mav.MAV_CMD_NAV_LAND:
            return all(v == 0 for v in params)
        return False
