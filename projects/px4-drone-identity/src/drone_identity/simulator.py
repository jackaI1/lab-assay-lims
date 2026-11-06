"""Own exactly one simulator process group and prove it was cleaned up."""
from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import struct
import threading
import time
from pathlib import Path


def _group_members(pgid: int) -> list[int]:
    rows = subprocess.check_output(['ps', '-eo', 'pid,pgid,stat'], text=True).splitlines()[1:]
    return [int(pid) for row in rows if len(parts := row.split()) == 3
            for pid, group, status in [parts] if int(group) == pgid and not status.startswith('Z')]


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            probe.bind(('127.0.0.1', port))
            return True
        except OSError:
            return False


class Simulator:
    def __init__(self, output: Path, command=None, cwd=Path('/opt/PX4'), log_limit=10 * 1024 * 1024):
        self.output, self.cwd = Path(output), Path(cwd)
        self.command = command or ['make', 'px4_sitl', 'gz_x500']
        self.ports = [14580] if command is None else []
        self.log_limit = log_limit
        self.log_bytes_received = 0
        self.log_error = None

    def __enter__(self):
        self.output.mkdir(parents=True, exist_ok=True)
        for port in self.ports:
            if not _port_free(port):
                raise RuntimeError(f'owned simulator port {port} is already occupied')
        self.log = (self.output / 'px4.log').open('wb')
        try:
            self.process = subprocess.Popen(self.command, cwd=self.cwd, stdin=subprocess.PIPE,
                                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                            start_new_session=True,
                                            env={**os.environ, 'HEADLESS': '1', 'MAVLINK20': '1'})
            self.log_thread = threading.Thread(target=self._drain_log, name='simulator-log')
            self.log_thread.start()
            pid = self.process.pid
            start = subprocess.check_output(['ps', '-p', str(pid), '-o', 'lstart='], text=True).strip()
            resource = {'owner': 'drone-identity experiments', 'pid': pid, 'process_group': pid,
                        'start_time': start, 'ports_udp': self.ports, 'command': self.command,
                        'cleanup_command': f'kill -TERM -- -{pid} (owned process group only)'}
            (self.output / 'resource.json').write_text(json.dumps(resource, indent=2) + '\n')
            return self
        except BaseException:
            if hasattr(self, 'process'):
                self.__exit__()
            else:
                self.log.close()
            raise

    def _drain_log(self):
        try:
            while chunk := self.process.stdout.read1(4096):
                remaining = max(0, self.log_limit - self.log_bytes_received)
                self.log.write(chunk[:remaining])
                self.log_bytes_received += len(chunk)
        except OSError as exc:
            self.log_error = str(exc)
        finally:
            self.process.stdout.close()

    def __exit__(self, *_):
        group = self.process.pid
        members = _group_members(group)
        if members:
            try:
                os.killpg(group, signal.SIGTERM)
            except ProcessLookupError:
                pass
        try:
            self.process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            pass
        deadline = time.monotonic() + 3
        while (members := _group_members(group)) and time.monotonic() < deadline:
            time.sleep(0.1)
        if members:
            os.killpg(group, signal.SIGKILL)
        self.process.wait(timeout=3)
        self.process.stdin.close()
        self.log_thread.join(timeout=3)
        if self.log_thread.is_alive():
            raise RuntimeError('owned log reader failed to stop')
        self.log.close()
        deadline = time.monotonic() + 3
        while _group_members(group) and time.monotonic() < deadline:
            time.sleep(0.1)
        remaining = _group_members(group)
        ports = {str(port): _port_free(port) for port in self.ports}
        report = {'process_group_alive': bool(remaining), 'remaining_owned_pids': remaining,
                  'udp_ports_free': ports, 'exit_code': self.process.returncode,
                  'log_bytes_received': self.log_bytes_received,
                  'log_truncated': self.log_bytes_received > self.log_limit}
        (self.output / 'cleanup.json').write_text(json.dumps(report, indent=2) + '\n')
        if remaining or not all(ports.values()) or self.log_error:
            raise RuntimeError(f'simulator cleanup incomplete: {report}')


def verify_loopback_listener(port: int) -> str:
    """Verify the real Linux socket binding, not just the remote destination."""
    bindings = []
    for row in Path('/proc/net/udp').read_text().splitlines()[1:]:
        address, encoded_port = row.split()[1].split(':')
        if int(encoded_port, 16) == port:
            bindings.append(socket.inet_ntoa(struct.pack('=I', int(address, 16))))
    if bindings != ['127.0.0.1']:
        raise RuntimeError(f'PX4 UDP listener must bind only loopback: {bindings}')
    return f'127.0.0.1:{port}'
