"""Reference ground controller, with authenticated telemetry and bounded flight demo."""
import asyncio
import contextlib

from .identity import context
from .wire import Codec, command, heartbeat, mav, read_packet, setpoint, write_packet


class Controller:
    async def connect(self, credentials, port=8443, role="controller"):
        self.reader, self.writer = await asyncio.open_connection(
            "127.0.0.1", port, ssl=context(credentials, role), server_hostname="localhost")
        try:
            hello = await asyncio.wait_for(self.reader.readexactly(36), 3)
            if hello[:4] != b"ID01":
                raise ValueError("unknown companion protocol")
        except BaseException:
            self.writer.close()
            with contextlib.suppress(ConnectionError):
                await self.writer.wait_closed()
            raise
        self.codec = Codec(hello[4:])
        self.latest = {}
        self.acks = []
        self.receiver = asyncio.create_task(self.receive())
        return self

    async def receive(self):
        while True:
            msg = self.codec.unpack(await read_packet(self.reader))
            self.latest[msg.get_type()] = msg
            if msg.get_type() == "COMMAND_ACK":
                self.acks.append((msg.command, msg.result))

    async def send(self, msg):
        await write_packet(self.writer, self.codec.pack(msg))

    async def stream(self):
        while True:
            await self.send(heartbeat())
            await self.send(setpoint())
            await asyncio.sleep(0.1)

    async def wait_for(self, predicate, timeout=30):
        try:
            async with asyncio.timeout(timeout):
                while not predicate():
                    if self.receiver.done():
                        self.receiver.result()
                    await asyncio.sleep(0.05)
        except TimeoutError as exc:
            raise TimeoutError(f"PX4 telemetry wait expired; received types: {sorted(self.latest)}") from exc

    async def execute(self, number, *params):
        self.acks.clear()
        for _ in range(5):
            await self.send(command(number, *params))
            try:
                await self.wait_for(lambda: any(c == number for c, _ in self.acks), timeout=2)
            except TimeoutError:
                continue
            result = next(r for c, r in self.acks if c == number)
            if result == mav.MAV_RESULT_ACCEPTED:
                return
            await asyncio.sleep(1)
        raise RuntimeError(f"PX4 did not accept command {number}; ACKs={self.acks}")

    async def close(self):
        self.receiver.cancel()
        with contextlib.suppress(asyncio.CancelledError, asyncio.IncompleteReadError, ConnectionError):
            await self.receiver
        self.writer.close()
        with contextlib.suppress(ConnectionError):
            await self.writer.wait_closed()


def is_offboard(client):
    msg = client.latest.get("HEARTBEAT")
    return msg is not None and (msg.custom_mode >> 16) & 255 == 6


def is_land(client):
    msg = client.latest.get("HEARTBEAT")
    return msg is not None and (msg.custom_mode >> 16) & 255 == 4 and (msg.custom_mode >> 24) & 255 == 6


async def fly(client):
    """Caller owns the streaming task, so link-loss tests can cancel it exactly."""
    await client.wait_for(lambda: "LOCAL_POSITION_NED" in client.latest, 60)
    await asyncio.sleep(4)  # pre-stream proof of life and settle the estimator
    await client.execute(mav.MAV_CMD_DO_SET_MODE, 1, 6)
    await client.wait_for(lambda: is_offboard(client), 10)
    await client.execute(mav.MAV_CMD_COMPONENT_ARM_DISARM, 1)
    await client.wait_for(lambda: client.latest["LOCAL_POSITION_NED"].z < -1, 30)


async def demo(credentials, port=8443):
    client = await Controller().connect(credentials, port)
    stream = asyncio.create_task(client.stream())
    try:
        await fly(client)
        print("Authenticated controller: PX4 is flying above 1 metre in Gazebo.")
        await asyncio.sleep(3)
        await client.execute(mav.MAV_CMD_DO_SET_MODE, 1, 4, 6)
        await client.wait_for(lambda: not (client.latest["HEARTBEAT"].base_mode & mav.MAV_MODE_FLAG_SAFETY_ARMED), 40)
        print("PX4 landed and disarmed.")
    finally:
        stream.cancel()
        with contextlib.suppress(asyncio.CancelledError, ConnectionError):
            await stream
        await client.close()
