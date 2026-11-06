"""One signed MAVLink 2 packet per bounded TLS record frame."""
import asyncio
import struct
import time

from pymavlink.dialects.v20 import common as mav


class Codec:
    def __init__(self, key: bytes, system: int = 255, component: int = 190, link: int = 1):
        if len(key) != 32:
            raise ValueError("MAVLink signing keys must be 32 bytes")
        self.mav = mav.MAVLink(None, srcSystem=system, srcComponent=component)
        self.mav.signing.secret_key = key
        self.mav.signing.sign_outgoing = True
        self.mav.signing.link_id = link
        self.mav.signing.timestamp = int((time.time() - 1420070400) * 100000)

    def pack(self, message):
        packet = message.pack(self.mav)
        self.mav.seq = (self.mav.seq + 1) % 256
        return packet

    def unpack(self, packet):
        if len(packet) < 25 or packet[0] != 0xFD or packet[2] != mav.MAVLINK_IFLAG_SIGNED:
            raise ValueError("signed MAVLink 2 required")
        message = self.mav.decode(bytearray(packet))
        if not message.get_signed():
            raise ValueError("unverified packet")
        return message


async def read_packet(reader):
    length = struct.unpack("!H", await reader.readexactly(2))[0]
    if not 25 <= length <= 280:
        raise ValueError("invalid frame size")
    return await reader.readexactly(length)


async def write_packet(writer, packet):
    writer.write(struct.pack("!H", len(packet)) + packet)
    await writer.drain()


def heartbeat():
    return mav.MAVLink_heartbeat_message(mav.MAV_TYPE_GCS, mav.MAV_AUTOPILOT_INVALID, 0, 0,
                                         mav.MAV_STATE_ACTIVE, 3)


def setpoint(z=-2.0):
    # Position only, NED means positive down, so -2 is two metres above origin.
    return mav.MAVLink_set_position_target_local_ned_message(
        0, 1, 1, mav.MAV_FRAME_LOCAL_NED, 0xDF8, 0, 0, z, 0, 0, 0, 0, 0, 0, 0, 0)


def command(number, *params):
    return mav.MAVLink_command_long_message(1, 1, number, 0, *(list(params) + [0] * (7 - len(params))))
