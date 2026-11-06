"""Mutual TLS carries length-framed signed MAVLink and a fresh session key."""
from __future__ import annotations

import json
import secrets
import socket
import ssl
import struct
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .identity import Authority, IdentityError, SoftwareKeyStore
from .protocol import Codec, Rejected, Session


def _read_exact(sock: socket.socket, count: int) -> bytes:
    data = bytearray()
    while len(data) < count:
        chunk = sock.recv(count - len(data))
        if not chunk:
            raise EOFError('peer closed')
        data.extend(chunk)
    return bytes(data)


def read_frame(sock: socket.socket, limit: int = 4096) -> bytes:
    size, = struct.unpack('!H', _read_exact(sock, 2))
    if not 0 < size <= limit:
        raise ValueError('invalid frame size')
    return _read_exact(sock, size)


def send_frame(sock: socket.socket, data: bytes) -> None:
    if not 0 < len(data) <= 4096:
        raise ValueError('invalid frame size')
    sock.sendall(struct.pack('!H', len(data)) + data)


class Gateway:
    def __init__(self, root: Path, vehicle, address=('127.0.0.1', 0), audit: Path | None = None):
        self.root, self.vehicle, self.audit = Path(root), vehicle, audit
        self.context = SoftwareKeyStore(self.root / 'vehicle').tls_context(self.root / 'ca.pem', server=True)
        self.authority = Authority(self.root)
        self.listener = socket.socket()
        self.listener.bind(address)
        self.listener.listen(8)
        self.listener.settimeout(0.1)
        self.address = self.listener.getsockname()
        self.stop = threading.Event()
        self.rejected = threading.Event()
        self.session_lock = threading.Lock()
        self.lock = threading.Lock()
        self.connections = set()
        self.workers = []
        self.thread = threading.Thread(target=self._serve, name='identity-listener')

    def event(self, event: str, **fields):
        if self.audit:
            record = {'time': datetime.now(timezone.utc).isoformat(), 'event': event, **fields}
            with self.lock, self.audit.open('a') as stream:
                stream.write(json.dumps(record, allow_nan=False) + '\n')

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stop.set()
        self.listener.close()
        with self.lock:
            for connection in self.connections:
                try:
                    connection.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                connection.close()
        self.thread.join(timeout=4)
        for thread in self.workers:
            thread.join(timeout=4)
        if self.thread.is_alive() or any(thread.is_alive() for thread in self.workers):
            raise RuntimeError('gateway failed to stop owned threads')

    def _serve(self):
        while not self.stop.is_set():
            try:
                raw, _ = self.listener.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with self.lock:
                self.workers = [thread for thread in self.workers if thread.is_alive()]
                if len(self.workers) >= 8:
                    raw.close()
                    continue
                self.connections.add(raw)
                worker = threading.Thread(target=self._handle, args=(raw,), name='identity-session')
                self.workers.append(worker)
            worker.start()

    def _handle(self, raw):
        secure, session, locked = None, None, False
        try:
            raw.settimeout(3)
            # Track the SSLSocket before doing the handshake so shutdown can
            # interrupt a partial ClientHello as well as an established session.
            secure = self.context.wrap_socket(raw, server_side=True, do_handshake_on_connect=False)
            with self.lock:
                self.connections.discard(raw)
                self.connections.add(secure)
            secure.do_handshake()
            cert = ssl.DER_cert_to_PEM_cert(secure.getpeercert(binary_form=True)).encode()
            role = self.authority.validate(cert, 'client')
            locked = self.session_lock.acquire(blocking=False)
            if not locked:
                self.event('busy')
                return
            key = secrets.token_bytes(32)
            session = Session(self.authority, cert, key, self.vehicle)
            self.vehicle.begin()  # real backend permits reset only while disarmed
            send_frame(secure, key)
            secure.settimeout(10)
            self.event('authenticated', role=role)
            while not self.stop.is_set():
                try:
                    try:
                        packet = read_frame(secure, 280)
                    except ValueError:
                        packet = b''  # classify framing errors through the same latched rejection path
                    kind = session.accept(packet)
                except Rejected as exc:
                    self.rejected.set()
                    self.event('rejected', role=role, detail=str(exc))
                    send_frame(secure, json.dumps({'rejected': str(exc)}).encode())
                    return
                send_frame(secure, json.dumps({'accepted': kind, 'telemetry': self.vehicle.snapshot()},
                                             allow_nan=False).encode())
        except (ssl.SSLError, IdentityError) as exc:
            self.vehicle.fail(2)
            self.rejected.set()
            self.event('authentication_failed', detail=type(exc).__name__)
        except (OSError, EOFError, ValueError, RuntimeError) as exc:
            if session and not session.failed:
                self.vehicle.fail(5)
                self.rejected.set()
            self.event('connection_closed', detail=type(exc).__name__)
        finally:
            if locked:
                self.session_lock.release()
            with self.lock:
                self.connections.discard(raw)
                self.connections.discard(secure)
            if secure:
                secure.close()
            raw.close()


class Client:
    def __init__(self, root: Path, identity: str, address=('127.0.0.1', 8443)):
        self.root = Path(root)
        self.store = SoftwareKeyStore(self.root / identity)
        self.address = address
        self.lock = threading.RLock()
        self.socket = None

    def __enter__(self):
        raw = socket.create_connection(self.address, timeout=5)
        try:
            self.socket = self.store.tls_context(self.root / 'ca.pem').wrap_socket(raw, server_hostname='localhost')
            cert = ssl.DER_cert_to_PEM_cert(self.socket.getpeercert(binary_form=True)).encode()
            Authority(self.root).validate(cert, 'server')
            key = read_frame(self.socket, 32)
            if len(key) != 32:
                raise ValueError('invalid session key')
            self.codec = Codec(key)
            return self
        except BaseException:
            self.__exit__()
            raw.close()
            raise

    def __exit__(self, *_):
        if self.socket:
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.socket.close()

    def exchange(self, packet: bytes) -> dict:
        with self.lock:
            send_frame(self.socket, packet)
            return json.loads(read_frame(self.socket))

    def heartbeat(self) -> dict:
        with self.lock:
            return self.exchange(self.codec.heartbeat())

    def command(self, command: int, param1: float = 0, *, altitude: float = 0) -> dict:
        with self.lock:
            return self.exchange(self.codec.command(command, param1, altitude=altitude))

    @contextmanager
    def keepalive(self):
        """Own a bounded heartbeat thread; exceptions remain visible to the caller."""
        stop = threading.Event()
        errors = []
        def pump():
            while not stop.is_set():
                try:
                    response = self.heartbeat()
                    if 'rejected' in response:
                        raise Rejected(response['rejected'])
                except (OSError, ValueError, EOFError) as exc:
                    errors.append(str(exc))
                    return
                stop.wait(0.25)
        worker = threading.Thread(target=pump, name='controller-heartbeat')
        worker.start()
        try:
            yield errors
        finally:
            stop.set()
            worker.join(timeout=6)
            if worker.is_alive():
                raise RuntimeError('heartbeat thread failed to stop')
